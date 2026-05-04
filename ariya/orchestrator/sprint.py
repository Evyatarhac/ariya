"""Sprint engine — spec §10.2."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from ariya.bus import bus
from ariya.state import store


def standup_digest(project_id: str) -> dict:
    """Generate a daily standup digest from signal history + agent state."""
    history = bus.history(500)
    project_signals = [s for s in history if s.project_id == project_id]
    by_agent: dict[str, list[str]] = {}
    for s in project_signals[-200:]:
        by_agent.setdefault(s.from_agent, []).append(
            s.payload.get("title") or s.signal_type
        )
    project = store.get_project(project_id)
    return {
        "project": project.name if project else project_id,
        "phase": project.phase if project else "?",
        "yesterday": {a: list(set(items))[:5] for a, items in by_agent.items()},
        "blockers": [
            {"from": s.from_agent, "title": s.payload.get("title", s.signal_type)}
            for s in project_signals if s.signal_type == "ALERT"
        ][-10:],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def velocity(project_id: str) -> dict:
    """Tasks completed in the last 7 days."""
    tasks = store.list_tasks(project_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    completed = [t for t in tasks if t.status == "COMPLETED"]
    recent = [t for t in completed
              if datetime.fromisoformat(t.updated_at.replace("Z", "+00:00")) > cutoff]
    return {
        "completed_total": len(completed),
        "completed_7d": len(recent),
        "open": sum(1 for t in tasks if t.status in ("QUEUED", "IN_PROGRESS")),
    }
