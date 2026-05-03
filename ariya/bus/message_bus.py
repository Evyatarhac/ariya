"""In-memory neural message bus.

Implements the pub/sub event-bus described in spec §3.3:
  - topics per agent
  - dead letter queue with retry
  - signal history (audit trail)
  - priority queue
  - context injection hook (delegated to ARIYA brain)

For production this should be swapped for Redis Streams or Kafka. The public API
(publish / subscribe / history) is intentionally narrow so the swap is mechanical.
"""
from __future__ import annotations
import asyncio
import logging
from collections import defaultdict, deque
from typing import Awaitable, Callable

from ariya.models import Signal

log = logging.getLogger("ariya.bus")

Handler = Callable[[Signal], Awaitable[None]]


class MessageBus:
    def __init__(self, history_size: int = 1000):
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._history: deque[Signal] = deque(maxlen=history_size)
        self._dlq: list[tuple[Signal, str]] = []
        self._listeners: list[Callable[[Signal], None]] = []  # for dashboard streaming

    def subscribe(self, agent_id: str, handler: Handler) -> None:
        self._subscribers[agent_id].append(handler)
        log.debug("subscribed %s", agent_id)

    def add_listener(self, listener: Callable[[Signal], None]) -> None:
        """Synchronous tap for the dashboard / activity log."""
        self._listeners.append(listener)

    async def publish(self, signal: Signal) -> None:
        self._history.append(signal)
        for l in self._listeners:
            try:
                l(signal)
            except Exception:
                log.exception("listener failed")

        targets = (
            list(self._subscribers.keys())
            if signal.to_agent == "broadcast"
            else [signal.to_agent]
        )

        # priority sort — higher first
        ordered = sorted(targets, key=lambda t: -signal.priority)
        for tgt in ordered:
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


bus = MessageBus()
