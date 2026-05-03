from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    DESIGN = "DESIGN"
    QA = "QA"
    DEVOPS = "DEVOPS"
    SECURITY = "SECURITY"
    ARCHITECTURE = "ARCHITECTURE"
    RESEARCH = "RESEARCH"


class Skill(BaseModel):
    skill_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    category: SkillCategory
    agent_id: str
    proficiency: float = 0.7  # 0..1
    version: str = "1.0.0"
    prompt_template: str = ""
    examples: list[dict[str, Any]] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    last_used: Optional[str] = None
    success_rate: float = 1.0
    uses: int = 0
    successes: int = 0
