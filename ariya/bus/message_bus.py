"""Neural message bus.

Two backends:
  - InMemoryBackend (default, dev)
  - RedisStreamsBackend (production, set ARIYA_BUS=redis + REDIS_URL)

Both implement: subscribe / publish / history. ARIYA's brain registers a
context-injection hook that runs before each delivery (spec §3.3).
"""
from __future__ import annotations
import asyncio
import json
import logging
import os
from collections import defaultdict, deque
from typing import Awaitable, Callable, Optional

from ariya.models import Signal

log = logging.getLogger("ariya.bus")

Handler = Callable[[Signal], Awaitable[None]]
ContextInjector = Callable[[Signal], Signal]


class _Backend:
    async def publish(self, signal: Signal) -> None: ...
    def subscribe(self, agent_id: str, handler: Handler) -> None: ...
    def history(self, limit: int = 100) -> list[Signal]: ...
    def dlq(self) -> list[tuple[Signal, str]]: ...


class InMemoryBackend(_Backend):
    def __init__(self, history_size: int = 2000):
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._history: deque[Signal] = deque(maxlen=history_size)
        self._dlq: list[tuple[Signal, str]] = []

    def subscribe(self, agent_id: str, handler: Handler) -> None:
        self._subscribers[agent_id].append(handler)

    async def publish(self, signal: Signal) -> None:
        self._history.append(signal)
        targets = (
            list(self._subscribers.keys())
            if signal.to_agent == "broadcast"
            else [signal.to_agent]
        )
        for tgt in sorted(targets, key=lambda t: -signal.priority):
            for handler in self._subscribers.get(tgt, []):
                asyncio.create_task(self._deliver(handler, signal))

    async def _deliver(self, handler: Handler, signal: Signal, attempt: int = 0) -> None:
        try:
            await handler(signal)
        except Exception as e:
            if attempt < 3:
                await asyncio.sleep(2 ** attempt)
                await self._deliver(handler, signal, attempt + 1)
            else:
                log.error("DLQ: %s -> %s : %s", signal.from_agent, signal.to_agent, e)
                self._dlq.append((signal, str(e)))

    def history(self, limit: int = 100) -> list[Signal]:
        return list(self._history)[-limit:]

    def dlq(self) -> list[tuple[Signal, str]]:
        return list(self._dlq)


class RedisStreamsBackend(_Backend):
    """Redis Streams backend. Requires `pip install redis>=5`.

    Stream key layout: ariya:agent:<AGENT_ID> per inbox.
    History stream:    ariya:history (capped via XADD MAXLEN ~).
    DLQ stream:        ariya:dlq
    """
    def __init__(self, url: str):
        try:
            import redis.asyncio as redis  # type: ignore
        except ImportError as e:
            raise RuntimeError("install redis>=5 to use the RedisStreamsBackend") from e
        self._redis = redis.from_url(url, decode_responses=True)
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._consumer_tasks: dict[str, asyncio.Task] = {}
        self._dlq: list[tuple[Signal, str]] = []

    def subscribe(self, agent_id: str, handler: Handler) -> None:
        self._subscribers[agent_id].append(handler)
        if agent_id not in self._consumer_tasks:
            self._consumer_tasks[agent_id] = asyncio.create_task(self._consume(agent_id))

    async def _consume(self, agent_id: str) -> None:
        last_id = "$"
        key = f"ariya:agent:{agent_id}"
        while True:
            try:
                resp = await self._redis.xread({key: last_id}, block=5000, count=10)
                for _stream, msgs in resp or []:
                    for mid, fields in msgs:
                        last_id = mid
                        sig = Signal.model_validate_json(fields["payload"])
                        for h in self._subscribers.get(agent_id, []):
                            try:
                                await h(sig)
                            except Exception as e:
                                self._dlq.append((sig, str(e)))
                                await self._redis.xadd("ariya:dlq", {"payload": sig.model_dump_json(), "err": str(e)})
            except Exception:
                log.exception("redis consume failed for %s", agent_id)
                await asyncio.sleep(2)

    async def publish(self, signal: Signal) -> None:
        payload = {"payload": signal.model_dump_json()}
        await self._redis.xadd("ariya:history", payload, maxlen=5000, approximate=True)
        targets = (
            list(self._subscribers.keys())
            if signal.to_agent == "broadcast"
            else [signal.to_agent]
        )
        for tgt in targets:
            await self._redis.xadd(f"ariya:agent:{tgt}", payload)

    def history(self, limit: int = 100) -> list[Signal]:
        # Sync wrapper would block — for the dashboard we read in-memory cache
        return []  # see MessageBus._history mirror below

    def dlq(self) -> list[tuple[Signal, str]]:
        return list(self._dlq)


class MessageBus:
    """Public facade. Holds an in-memory mirror of recent signals so the
    dashboard always has a fast read path regardless of backend."""

    def __init__(self):
        backend_kind = os.getenv("ARIYA_BUS", "memory").lower()
        if backend_kind == "redis":
            self._backend: _Backend = RedisStreamsBackend(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        else:
            self._backend = InMemoryBackend()
        self._mirror: deque[Signal] = deque(maxlen=2000)
        self._listeners: list[Callable[[Signal], None]] = []
        self._injector: Optional[ContextInjector] = None

    def set_context_injector(self, fn: ContextInjector) -> None:
        self._injector = fn

    def subscribe(self, agent_id: str, handler: Handler) -> None:
        self._backend.subscribe(agent_id, handler)

    def add_listener(self, fn: Callable[[Signal], None]) -> None:
        self._listeners.append(fn)

    async def publish(self, signal: Signal) -> None:
        if self._injector:
            try:
                signal = self._injector(signal)
            except Exception:
                log.exception("context injector failed")
        self._mirror.append(signal)
        for l in self._listeners:
            try:
                l(signal)
            except Exception:
                log.exception("listener failed")
        await self._backend.publish(signal)

    def history(self, limit: int = 100) -> list[Signal]:
        return list(self._mirror)[-limit:]

    def dlq(self) -> list[tuple[Signal, str]]:
        return self._backend.dlq()


bus = MessageBus()
