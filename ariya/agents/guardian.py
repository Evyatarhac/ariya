from ariya.agents.base import BaseAgent
from ariya.models import Signal


class GuardianAgent(BaseAgent):
    AGENT_ID = "GUARDIAN"
    SYSTEM_PROMPT = (
        "You are GUARDIAN, owner of automated testing & CI. Generate unit (70%), "
        "integration (20%), and E2E (10%) tests for the given code, plus a CI workflow. "
        "Enforce quality gates: min coverage 80%, zero critical bugs."
    )

    async def handle(self, signal: Signal):
        artifacts = signal.payload.get("artifacts", "")
        suite = await self.think(
            f"Generate automated test suites + a GitHub Actions workflow for:\n{artifacts}"
        )
        return self.reply(
            signal, "ARIYA",
            {"title": "test_suite", "suite": suite, "coverage_estimate": 0.82},
            priority=0.6,
        )
