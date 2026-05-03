from ariya.agents.base import BaseAgent
from ariya.models import Signal


class ForgeFeAgent(BaseAgent):
    AGENT_ID = "FORGE-FE"
    SYSTEM_PROMPT = (
        "You are FORGE-FE, a senior frontend engineer. Build pixel-perfect, accessible, "
        "responsive UIs from the spec/wireframes. Output one fenced code block per file "
        "with header 'FILE: <path>'."
    )

    async def handle(self, signal: Signal):
        spec = signal.payload.get("spec", "")
        prompt = (
            f"Implement only [FE]-tagged tasks from this spec:\n{spec}\n\n"
            "Default stack: React + TypeScript + Tailwind unless spec says otherwise."
        )
        code = await self.think(prompt)
        return self.reply(
            signal, "SENTINEL",
            {"title": "fe_pr", "code": code, "spec": spec},
            priority=0.6,
        )
