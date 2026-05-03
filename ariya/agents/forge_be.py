from ariya.agents.base import BaseAgent
from ariya.models import Signal


class ForgeBeAgent(BaseAgent):
    AGENT_ID = "FORGE-BE"
    SYSTEM_PROMPT = (
        "You are FORGE-BE, a senior backend engineer. Implement server-side code, APIs, "
        "DB migrations, and unit tests strictly per the spec. Output a single fenced code "
        "block per file with a header comment 'FILE: <path>'."
    )

    async def handle(self, signal: Signal):
        spec = signal.payload.get("spec", "")
        prompt = (
            f"Implement only [BE]-tagged tasks from this spec:\n{spec}\n\n"
            "Default stack: Node.js + TypeScript + Express + PostgreSQL unless spec says otherwise."
        )
        code = await self.think(prompt)
        return self.reply(
            signal, "SENTINEL",
            {"title": "be_pr", "code": code, "spec": spec},
            priority=0.6,
        )
