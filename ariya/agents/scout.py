from ariya.agents.base import BaseAgent
from ariya.models import Signal, SignalType


class ScoutAgent(BaseAgent):
    AGENT_ID = "SCOUT"
    SYSTEM_PROMPT = (
        "You are SCOUT, a senior product researcher. Conduct market research, "
        "competitor analysis, identify feature opportunities, and produce wireframe "
        "outlines. Be concise; output structured markdown."
    )

    async def handle(self, signal: Signal):
        brief = signal.payload.get("brief", "")
        prompt = (
            f"Project brief:\n{brief}\n\n"
            "Produce: (1) competitor scan, (2) feature priority matrix (P0/P1/P2), "
            "(3) target user personas, (4) low-fi wireframe outlines (markdown)."
        )
        report = await self.think(prompt)
        return self.reply(
            signal, "ARCHITECT",
            {"title": "research_report", "brief": brief, "research_report": report},
            priority=0.7,
        )
