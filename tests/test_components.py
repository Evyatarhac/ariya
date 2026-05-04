import os
os.environ["ARIYA_MOCK_MODE"] = "true"
os.environ["ARIYA_DB_PATH"] = ":memory:"


def test_signal_schema():
    from ariya.models import Signal, SignalType
    s = Signal(from_agent="ARIYA", to_agent="SCOUT", signal_type=SignalType.TASK)
    assert s.signal_id and s.timestamp


def test_workspace_parse_files():
    from ariya.workspace import parse_files_from_text
    text = """
Here is the code:
```ts
// FILE: src/server.ts
console.log("hi");
```
And another:
```py
# FILE: app/main.py
print("py")
```
"""
    files = parse_files_from_text(text)
    paths = [p for p, _ in files]
    assert "src/server.ts" in paths
    assert "app/main.py" in paths


def test_workspace_rejects_traversal():
    from ariya.workspace import parse_files_from_text
    text = "```ts\n// FILE: ../../etc/passwd\nbad\n```"
    assert parse_files_from_text(text) == []


def test_router_scoring():
    from ariya.orchestrator.router import best_agent
    r = best_agent(["SCOUT", "ARCHITECT"], ["market", "research", "feature"], priority=4)
    assert r.agent_id in ("SCOUT", "ARCHITECT")
    assert 0.0 <= r.score <= 1.0


def test_cost_tracker():
    from ariya.gateway.model_gateway import CostTracker
    c = CostTracker()
    c.record(agent="ARIYA", model="claude-opus-4-7", project="p1",
             in_tokens=1000, out_tokens=500)
    snap = c.snapshot()
    assert snap["total_usd"] > 0
    assert snap["by_agent"]["ARIYA"] > 0


def test_templates():
    from ariya.templates import expand_brief, TEMPLATES
    out = expand_brief("Build it", "saas")
    assert "TEMPLATE" in out and TEMPLATES["saas"]["stack"] in out


def test_skill_plasticity():
    from ariya.skills import registry
    skills = registry.all()
    assert len(skills) >= 15
    s0 = skills[0]
    before = s0.proficiency
    registry.record_use(s0.skill_id, success=True)
    s1 = registry.get(s0.skill_id)
    assert s1.uses >= 1
    assert s1.proficiency >= before
