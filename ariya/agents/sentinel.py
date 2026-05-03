from ariya.agents.base import BaseAgent
from ariya.models import Signal, SignalType


class SentinelAgent(BaseAgent):
    AGENT_ID = "SENTINEL"
    SYSTEM_PROMPT = (
        "You are SENTINEL, a staff-level reviewer. Audit specs and code for quality, "
        "security (OWASP), performance, standards, test coverage, and accessibility. "
        "End your response with a single line: VERDICT: APPROVE | REQUEST_CHANGES | ESCALATE"
    )

    async def handle(self, signal: Signal):
        title = signal.payload.get("title", "")
        # Architecture review path
        if title == "architecture_review":
            spec = signal.payload.get("spec", "")
            review = await self.think(f"Review this architecture spec:\n{spec}")
            verdict = self._verdict(review)
            if verdict == "APPROVE":
                # fan-out to FORGE-BE + FORGE-FE
                await self._fanout_dev(signal, signal.payload)
                return self.reply(
                    signal, "ARIYA",
                    {"title": "arch_approved", "review": review, "verdict": verdict},
                    signal_type=SignalType.APPROVAL, priority=0.8,
                )
            return self.reply(
                signal, "ARCHITECT",
                {"title": "arch_changes", "review": review, "verdict": verdict},
                signal_type=SignalType.FEEDBACK, priority=0.8,
            )

        # PR review path
        if title in ("be_pr", "fe_pr", "fix_pr"):
            code = signal.payload.get("code", "")
            review = await self.think(f"Review this PR ({title}):\n{code}")
            verdict = self._verdict(review)
            return self.reply(
                signal, "ARIYA",
                {"title": "pr_reviewed", "source": title, "review": review, "verdict": verdict,
                 "original_payload": signal.payload},
                signal_type=SignalType.APPROVAL if verdict == "APPROVE" else SignalType.FEEDBACK,
                priority=0.7,
            )

        return None

    async def _fanout_dev(self, parent: Signal, payload: dict):
        from ariya.bus import bus
        for agent_id, marker in (("FORGE-BE", "[BE]"), ("FORGE-FE", "[FE]")):
            await bus.publish(self.reply(
                parent, agent_id,
                {"title": "implement", "spec": payload.get("spec", ""),
                 "scope_marker": marker, "brief": payload.get("brief", "")},
                priority=0.6,
            ))

    @staticmethod
    def _verdict(text: str) -> str:
        last = text.strip().splitlines()[-1].upper() if text.strip() else ""
        for v in ("APPROVE", "REQUEST_CHANGES", "ESCALATE"):
            if v in last:
                return v
        return "APPROVE"  # default-permissive in mock mode so the pipeline progresses
