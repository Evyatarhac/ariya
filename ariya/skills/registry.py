"""Skills DB — spec §6.

For MVP this is an in-process registry persisted to JSON. Production target is
MongoDB (per spec §13.1) — see FIXES.md.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ariya.models import Skill, SkillCategory

SEED_PATH = Path(__file__).parent / "seed_skills.json"
PERSIST_PATH = Path(__file__).parent / "_skills_runtime.json"


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._load()

    def _load(self):
        path = PERSIST_PATH if PERSIST_PATH.exists() else SEED_PATH
        if not path.exists():
            return
        for raw in json.loads(path.read_text(encoding="utf-8")):
            s = Skill.model_validate(raw)
            self._skills[s.skill_id] = s

    def _save(self):
        PERSIST_PATH.write_text(
            json.dumps([s.model_dump() for s in self._skills.values()], indent=2),
            encoding="utf-8",
        )

    def add(self, skill: Skill) -> Skill:
        self._skills[skill.skill_id] = skill
        self._save()
        return skill

    def get(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    def for_agent(self, agent_id: str) -> list[Skill]:
        return [s for s in self._skills.values() if s.agent_id == agent_id]

    def by_category(self, cat: SkillCategory) -> list[Skill]:
        return [s for s in self._skills.values() if s.category == cat]

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def record_use(self, skill_id: str, success: bool) -> None:
        s = self._skills.get(skill_id)
        if not s:
            return
        s.uses += 1
        if success:
            s.successes += 1
        s.success_rate = s.successes / max(s.uses, 1)
        s.last_used = datetime.now(timezone.utc).isoformat()
        # plasticity — small proficiency drift
        delta = 0.02 if success else -0.03
        s.proficiency = max(0.0, min(1.0, s.proficiency + delta))
        self._save()


registry = SkillRegistry()
