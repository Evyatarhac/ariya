"""Base agent — every neuron in the network derives from this."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from ariya.bus import bus
from ariya.gateway import gateway
from ariya.models import Signal, SignalType
from ariya.skills import registry
from ariya.state import store

log = logging.getLogger("ariya.agent")


class BaseAgent:
    AGENT_ID: str = "BASE"
    SYSTEM_PROMPT: str = "You are a senior engineer agent."

    def __init__(self):
        self.queue: asyncio.Queue[Signal] = asyncio.Queue()
        self.busy: bool = False
        self.current_task: str = ""
        bus.subscribe(self.AGENT_ID, self._receive)
        store.update_agent(self.AGENT_ID, "idle")

    async def _receive(self, signal: Signal) -> None:
        await self.queue.put(signal)

    async def run(self) -> None:
        """Main loop — process signals as they arrive."""
        while True:
            sig = await self.queue.get()
            self.busy = True
            self.current_task = sig.payload.get("title", sig.signal_type)
            store.update_agent(self.AGENT_ID, "processing", self.current_task)
            try:
                result = await self.handle(sig)
                if result is not None:
                    await bus.publish(result)
            except Exception:
                log.exception("%s handle failed", self.AGENT_ID)
                await bus.publish(Signal(
                    from_agent=self.AGENT_ID,
                    to_agent="ARIYA",
                    signal_type=SignalType.ALERT,
                    priority=0.95,
                    payload={"error": "handler crash", "origin": sig.signal_id},
                    parent_signal=sig.signal_id,
                    project_id=sig.project_id,
                ))
            finally:
                self.busy = False
                self.current_task = ""
                store.update_agent(self.AGENT_ID, "idle")

    async def handle(self, signal: Signal) -> Optional[Signal]:
        """Override: process the signal, optionally emit a reply."""
        raise NotImplementedError

    async def think(self, prompt: str, *, system: Optional[str] = None) -> str:
        return await gateway.complete(
            self.AGENT_ID, prompt, system=system or self.SYSTEM_PROMPT
        )

    def skills(self):
        return registry.for_agent(self.AGENT_ID)

    def reply(self, sig: Signal, to_agent: str, payload: dict, *,
              signal_type: SignalType = SignalType.TASK,
              priority: float = 0.5) -> Signal:
        return Signal(
            from_agent=self.AGENT_ID,
            to_agent=to_agent,
            signal_type=signal_type,
            priority=priority,
            payload=payload,
            parent_signal=sig.signal_id,
            context_window=sig.context_window,
            project_id=sig.project_id,
        )
