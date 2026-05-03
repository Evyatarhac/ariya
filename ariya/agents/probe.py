from ariya.agents.base import BaseAgent
from ariya.models import Signal, SignalType


class ProbeAgent(BaseAgent):
    AGENT_ID = "PROBE"
    SYSTEM_PROMPT = (
        "You are PROBE, a creative senior QA. Generate exploratory test scenarios, "
        "edge-cases, accessibility issues, and UX validations. Output a markdown "
        "bug report with: ID, severity (critical/high/medium/low), repro steps, suggested fix."
    )

    async def handle(self, signal: Signal):
        artifacts = signal.payload.get("artifacts", "")
        report = await self.think(
            f"Test the following implementation artifacts:\n{artifacts}\n\n"
            "Return a bug report in markdown."
        )
        # Forward bugs to PHOENIX for self-healing
        return self.reply(
            signal, "PHOENIX",
            {"title": "bug_report", "bug_report": report, "artifacts": artifacts},
            priority=0.7,
        )
