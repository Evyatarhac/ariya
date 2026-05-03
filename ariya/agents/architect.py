from ariya.agents.base import BaseAgent
from ariya.models import Signal, SignalType


class ArchitectAgent(BaseAgent):
    AGENT_ID = "ARCHITECT"
    SYSTEM_PROMPT = (
        "You are ARCHITECT, a senior solutions architect. Translate research/requirements "
        "into a complete technical spec: stack choice, system diagram (text), API contracts, "
        "DB schema (ERD-like), infra/CI plan, and a numbered task breakdown for backend & frontend."
    )

    async def handle(self, signal: Signal):
        brief = signal.payload.get("brief", "")
        research = signal.payload.get("research_report", "")
        prompt = (
            f"Brief:\n{brief}\n\nResearch:\n{research}\n\n"
            "Produce: stack, components, REST contracts, DB schema, infra plan, "
            "and a numbered task list with [BE]/[FE] tags."
        )
        spec = await self.think(prompt)
        return self.reply(
            signal, "SENTINEL",
            {"title": "architecture_review", "brief": brief, "spec": spec, "research_report": research},
            priority=0.7,
        )
