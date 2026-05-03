from ariya.agents.base import BaseAgent
from ariya.models import Signal


class PhoenixAgent(BaseAgent):
    AGENT_ID = "PHOENIX"
    SYSTEM_PROMPT = (
        "You are PHOENIX, the self-healing engine. Given a bug report and the related code, "
        "produce a candidate patch with a confidence score (0-1) and a brief regression check note. "
        "End with a line: CONFIDENCE: <0..1>"
    )

    async def handle(self, signal: Signal):
        bug = signal.payload.get("bug_report", "")
        artifacts = signal.payload.get("artifacts", "")
        patch = await self.think(
            f"Bug report:\n{bug}\n\nCode artifacts:\n{artifacts}\n\n"
            "Produce a candidate fix as a unified diff or full file. End with CONFIDENCE: <0..1>."
        )
        confidence = 0.7
        for line in patch.splitlines()[::-1]:
            if "CONFIDENCE" in line.upper():
                try:
                    confidence = float(line.split(":")[-1].strip())
                except Exception:
                    pass
                break
        return self.reply(
            signal, "SENTINEL",
            {"title": "fix_pr", "code": patch, "confidence": confidence, "bug_report": bug},
            priority=0.75,
        )
