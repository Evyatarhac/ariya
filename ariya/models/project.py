from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class ProjectPhase(str, Enum):
    INTAKE = "INTAKE"
    RESEARCH = "RESEARCH"
    ARCHITECTURE = "ARCHITECTURE"
    REVIEW = "REVIEW"
    DEVELOPMENT = "DEVELOPMENT"
    TESTING = "TESTING"
    SELF_HEALING = "SELF_HEALING"
    FINAL_REVIEW = "FINAL_REVIEW"
    DEPLOYMENT = "DEPLOYMENT"
    DONE = "DONE"


class TaskStatus(str, Enum):
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str
    description: str = ""
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.QUEUED
    priority: int = 3  # 1..5
    depends_on: list[str] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    brief: str
    phase: ProjectPhase = ProjectPhase.INTAKE
    tasks: list[Task] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    approvals: dict[str, bool] = Field(default_factory=dict)  # gate -> approved?
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
