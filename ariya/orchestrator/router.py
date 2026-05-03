"""Weighted decision matrix for task routing — spec §4.2.

score = w1*skill_match + w2*(1-load) + w3*(priority/5) + w4*history_perf
"""
from __future__ import annotations
from dataclasses import dataclass

from ariya.skills import registry
from ariya.state import store


@dataclass
class RouteScore:
    agent_id: str
    score: float
    reasons: dict


WEIGHTS = {"skill": 0.45, "load": 0.20, "priority": 0.15, "history": 0.20}


def _load_for(agent_id: str) -> float:
    """0..1 — higher = busier."""
    agents = {a["agent_id"]: a for a in store.all_agents()}
    a = agents.get(agent_id)
    if not a:
        return 0.0
    return 1.0 if a.get("status") == "processing" else 0.0


def _skill_match(agent_id: str, task_keywords: list[str]) -> float:
    skills = registry.for_agent(agent_id)
    if not skills:
        return 0.0
    text = " ".join(s.name.lower() + " " + (s.prompt_template or "").lower() for s in skills)
    hits = sum(1 for k in task_keywords if k.lower() in text)
    return min(1.0, hits / max(len(task_keywords), 1))


def _history(agent_id: str) -> float:
    skills = registry.for_agent(agent_id)
    if not skills:
        return 0.7
    rates = [s.success_rate for s in skills if s.uses > 0]
    return sum(rates) / len(rates) if rates else 0.7


def score_agent(agent_id: str, task_keywords: list[str], priority: int) -> RouteScore:
    skill = _skill_match(agent_id, task_keywords)
    load = 1.0 - _load_for(agent_id)
    pri = priority / 5.0
    hist = _history(agent_id)
    s = (
        WEIGHTS["skill"] * skill
        + WEIGHTS["load"] * load
        + WEIGHTS["priority"] * pri
        + WEIGHTS["history"] * hist
    )
    return RouteScore(
        agent_id=agent_id, score=round(s, 3),
        reasons={"skill": round(skill, 2), "load_inv": load,
                 "priority": pri, "history": round(hist, 2)},
    )


def best_agent(candidates: list[str], task_keywords: list[str], priority: int = 3) -> RouteScore:
    return max((score_agent(a, task_keywords, priority) for a in candidates),
               key=lambda r: r.score)
