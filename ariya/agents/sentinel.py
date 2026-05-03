from ariya.agents.base import BaseAgent
from ariya.bus import bus
from ariya.models import Signal, SignalType

MAX_REVIEW_ITERATIONS = 3


class SentinelAgent(BaseAgent):
    AGENT_ID = "SENTINEL"
    SYSTEM_PROMPT = (
        "You are SENTINEL, a staff-level reviewer. Audit specs and code for quality, "
        "security (OWASP), performance, standards, test coverage, and accessibility. "
        "End your response with a single line: VERDICT: APPROVE | REQUEST_CHANGES | ESCALATE"
    )

    async def handle(self, signal: Signal):
        title = signal.payload.get("title", "")

        if title == "architecture_review":
            spec = signal.payload.get("spec", "")
            review = await self.think(f"Review this architecture spec:\n{spec}")
            verdict = self._verdict(review)
            if verdict == "APPROVE":
                await self._fanout_dev(signal, signal.payload)
                return self.reply(
                    signal, "ARIYA",
                    {"title": "arch_approved", "review": review, "verdict": verdict},
                    signal_type=SignalType.APPROVAL, priority=0.8,
                )
            return self.reply(
                signal, "ARCHITECT",
                {"title": "arch_changes", "review": review, "verdict": verdict,
                 "spec": spec, "brief": signal.payload.get("brief", "")},
                signal_type=SignalType.FEEDBACK, priority=0.8,
            )

        if title in ("be_pr", "fe_pr", "fix_pr"):
            code = signal.payload.get("code", "")
            iteration = signal.payload.get("iteration", 0)
            review = await self.think(f"Review this PR ({title}):\n{code}")
            verdict = self._verdict(review)

            # Multi-iteration loop: if changes requested and we have budget left,
            # bounce back to the originator instead of straight to ARIYA.
            if verdict == "REQUEST_CHANGES" and iteration < MAX_REVIEW_ITERATIONS:
                origin = {"be_pr": "FORGE-BE", "fe_pr": "FORGE-FE", "fix_pr": "PHOENIX"}[title]
                return self.reply(
                    signal, origin,
                    {
                        "title": "implement",
                        "iteration": iteration + 1,
                        "spec": signal.payload.get("spec", ""),
                        "prior_review": review,
                        "scope_marker": "[BE]" if title == "be_pr" else ("[FE]" if title == "fe_pr" else ""),
                        "bug_report": signal.payload.get("bug_report", ""),
                    },
                    signal_type=SignalType.FEEDBACK, priority=0.7,
                )

            return self.reply(
                signal, "ARIYA",
                {"title": "pr_reviewed", "source": title, "review": review,
                 "verdict": verdict, "iteration": iteration,
                 "original_payload": signal.payload},
                signal_type=SignalType.APPROVAL if verdict == "APPROVE" else SignalType.FEEDBACK,
                priority=0.7,
            )

        return None

    async def _fanout_dev(self, parent: Signal, payload: dict):
        # Send a synthetic CONTRACT for FE so it knows the BE shape up front
        spec = payload.get("spec", "")
        contract = self._extract_contract(spec)
        for agent_id, marker in (("FORGE-BE", "[BE]"), ("FORGE-FE", "[FE]")):
            extra = {"api_contract": contract} if agent_id == "FORGE-FE" else {}
            await bus.publish(self.reply(
                parent, agent_id,
                {"title": "implement", "spec": spec,
                 "scope_marker": marker, "iteration": 0,
                 "brief": payload.get("brief", ""), **extra},
                priority=0.6,
            ))

    @staticmethod
    def _extract_contract(spec: str) -> str:
        # naive — pull lines that look like API contracts
        keep = []
        capture = False
        for line in spec.splitlines():
            low = line.lower()
            if any(t in low for t in ("api contract", "endpoints", "rest", "graphql")):
                capture = True
            if capture:
                keep.append(line)
            if capture and len(keep) > 60:
                break
        return "\n".join(keep)

    @staticmethod
    def _verdict(text: str) -> str:
        last = (text.strip().splitlines() or [""])[-1].upper()
        for v in ("APPROVE", "REQUEST_CHANGES", "ESCALATE"):
            if v in last:
                return v
        return "APPROVE"
