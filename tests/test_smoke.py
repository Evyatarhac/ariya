"""Smoke tests — verify the pipeline boots and a brief flows through agents in mock mode."""
import asyncio
import os
os.environ["ARIYA_MOCK_MODE"] = "true"
os.environ["ARIYA_DB_PATH"] = ":memory:"


def test_imports():
    from ariya.orchestrator import brain
    from ariya.agents import ALL_AGENT_CLASSES
    assert brain is not None
    assert len(ALL_AGENT_CLASSES) == 8


def test_pipeline_end_to_end():
    from ariya.orchestrator import brain
    from ariya.bus import bus

    async def run():
        await brain.boot()
        proj = await brain.intake("Smoke", "Build a tiny todo app, React + Node.")
        # let the bus drain a few ticks
        for _ in range(20):
            await asyncio.sleep(0.05)
        history = bus.history(200)
        froms = {s.from_agent for s in history}
        # at minimum ARIYA should have spoken; agents should have responded
        assert "ARIYA" in froms
        assert proj.project_id

    asyncio.run(run())
