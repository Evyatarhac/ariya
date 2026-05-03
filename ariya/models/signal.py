"""Neural signal protocol — spec §3.1."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class SignalType(str, Enum):
    TASK = "TASK"
    FEEDBACK = "FEEDBACK"
    APPROVAL = "APPROVAL"
    ALERT = "ALERT"
    QUERY = "QUERY"
    CONTRACT_UPDATE = "CONTRACT_UPDATE"


class Signal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    from_agent: str
    to_agent: str  # agent id, or "broadcast"
    signal_type: SignalType
    priority: float = 0.5  # 0..1
    payload: dict[str, Any] = Field(default_factory=dict)
    context_window: dict[str, Any] = Field(default_factory=dict)
    requires_ack: bool = False
    parent_signal: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl: int = 3600  # seconds
    project_id: Optional[str] = None
