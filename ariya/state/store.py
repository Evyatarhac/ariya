"""SQLite-backed shared state store — spec §11.

Domains modeled: project, task, signal-history, agent-state, approvals.
Replace with PostgreSQL for production (FIXES.md item).
"""
from __future__ import annotations
import json
import sqlite3
from typing import Any, Optional
from threading import Lock

from ariya.config import settings
from ariya.models import Project, Task

_DDL = """
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  name TEXT,
  brief TEXT,
  phase TEXT,
  data TEXT,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  project_id TEXT,
  data TEXT,
  status TEXT
);
CREATE TABLE IF NOT EXISTS agent_state (
  agent_id TEXT PRIMARY KEY,
  status TEXT,
  current_task TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
  project_id TEXT,
  gate TEXT,
  approved INTEGER,
  note TEXT,
  PRIMARY KEY (project_id, gate)
);
"""


class StateStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or settings.db_path
        self._lock = Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ---------- projects ----------
    def save_project(self, p: Project) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?, ?)",
                (p.project_id, p.name, p.brief, p.phase.value, p.model_dump_json(), p.created_at),
            )
            self._conn.commit()

    def get_project(self, project_id: str) -> Optional[Project]:
        cur = self._conn.execute(
            "SELECT data FROM projects WHERE project_id=?", (project_id,)
        )
        row = cur.fetchone()
        return Project.model_validate_json(row[0]) if row else None

    def list_projects(self) -> list[Project]:
        cur = self._conn.execute("SELECT data FROM projects ORDER BY created_at DESC")
        return [Project.model_validate_json(r[0]) for r in cur.fetchall()]

    # ---------- tasks ----------
    def save_task(self, t: Task) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO tasks VALUES (?, ?, ?, ?)",
                (t.task_id, t.project_id, t.model_dump_json(), t.status.value),
            )
            self._conn.commit()

    def list_tasks(self, project_id: str) -> list[Task]:
        cur = self._conn.execute(
            "SELECT data FROM tasks WHERE project_id=?", (project_id,)
        )
        return [Task.model_validate_json(r[0]) for r in cur.fetchall()]

    # ---------- agent state ----------
    def update_agent(self, agent_id: str, status: str, current_task: str = "") -> None:
        from datetime import datetime, timezone
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO agent_state VALUES (?, ?, ?, ?)",
                (agent_id, status, current_task, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def all_agents(self) -> list[dict[str, Any]]:
        cur = self._conn.execute("SELECT agent_id, status, current_task, updated_at FROM agent_state")
        return [
            {"agent_id": r[0], "status": r[1], "current_task": r[2], "updated_at": r[3]}
            for r in cur.fetchall()
        ]

    # ---------- approvals ----------
    def set_approval(self, project_id: str, gate: str, approved: bool, note: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO approvals VALUES (?, ?, ?, ?)",
                (project_id, gate, 1 if approved else 0, note),
            )
            self._conn.commit()

    def get_approvals(self, project_id: str) -> dict[str, bool]:
        cur = self._conn.execute(
            "SELECT gate, approved FROM approvals WHERE project_id=?", (project_id,)
        )
        return {g: bool(a) for g, a in cur.fetchall()}


store = StateStore()
