"""ARIYA — the orchestrator brain (spec §5).

Responsibilities (MVP scope):
  - Project intake (parse brief, persist project)
  - Kick off the workflow (publish first TASK signal to SCOUT)
  - Receive APPROVAL/FEEDBACK signals from SENTINEL & friends
  - Manage approval gates (mark project state, optionally auto-advance in DEV mode)
  - Track agent state and signal history for the dashboard
  - Conflict resolution stub (FIXES.md: needs richer logic)
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from ariya.bus import bus
from ariya.gateway import gateway
from ariya.models import Project, ProjectPhase, Signal, SignalType
from ariya.state import store
from ariya.agents import ALL_AGENT_CLASSES

log = logging.getLogger("ariya.brain")

GATES = ["design", "architecture", "code", "qa", "deploy"]


class AriyaBrain:
    AGENT_ID = "ARIYA"
    SYSTEM_PROMPT = (
        "You are ARIYA, the orchestrator brain. Decompose, route, resolve conflicts, "
        "and communicate with the human operator in clear, brief status updates."
    )

    def __init__(self):
        self._agents = []
        self._tasks: list[asyncio.Task] = []
        self._activity: list[dict] = []
        # ARIYA also subscribes to its own topic for replies from agents
        bus.subscribe(self.AGENT_ID, self._receive)
        bus.add_listener(self._on_signal_for_log)

    # ---------- lifecycle ----------
    async def boot(self) -> None:
        for cls in ALL_AGENT_CLASSES:
            agent = cls()
            self._agents.append(agent)
            self._tasks.append(asyncio.create_task(agent.run()))
        store.update_agent(self.AGENT_ID, "idle")
        log.info("ARIYA booted with %d agents", len(self._agents))

    # ---------- intake ----------
    async def intake(self, name: str, brief: str, auto_approve: bool = True) -> Project:
        project = Project(name=name, brief=brief, phase=ProjectPhase.RESEARCH)
        store.save_project(project)
        # Project decomposition (logged, not yet driving execution beyond high level)
        try:
            plan = await gateway.complete(
                self.AGENT_ID,
                f"Decompose this project brief into epics + tasks (markdown):\n{brief}",
                system=self.SYSTEM_PROMPT,
            )
            project.artifacts["plan"] = plan
            store.save_project(project)
        except Exception:
            log.exception("decomposition failed")

        # Kick the pipeline: first TASK signal to SCOUT
        await bus.publish(Signal(
            from_agent=self.AGENT_ID,
            to_agent="SCOUT",
            signal_type=SignalType.TASK,
            priority=0.8,
            payload={"title": "research", "brief": brief, "project_name": name},
            project_id=project.project_id,
            context_window={"auto_approve": auto_approve},
        ))
        return project

    # ---------- signal handling ----------
    async def _receive(self, signal: Signal) -> None:
        """ARIYA's own inbox — process replies from agents."""
        title = signal.payload.get("title", "")
        project = store.get_project(signal.project_id) if signal.project_id else None
        if not project:
            return

        auto = bool(signal.context_window.get("auto_approve", True))

        if title == "arch_approved":
            project.phase = ProjectPhase.DEVELOPMENT
            project.approvals["architecture"] = True
            store.save_project(project)
            store.set_approval(project.project_id, "architecture", True, "auto")

        elif title == "pr_reviewed":
            verdict = signal.payload.get("verdict", "APPROVE")
            source = signal.payload.get("source", "")
            if verdict == "APPROVE" and source in ("be_pr", "fe_pr"):
                # Once both BE and FE approved we advance to TESTING; for MVP fire on each
                project.phase = ProjectPhase.TESTING
                store.save_project(project)
                # Kick PROBE + GUARDIAN
                code = signal.payload.get("original_payload", {}).get("code", "")
                for tester in ("PROBE", "GUARDIAN"):
                    await bus.publish(Signal(
                        from_agent=self.AGENT_ID, to_agent=tester,
                        signal_type=SignalType.TASK, priority=0.6,
                        payload={"title": "test", "artifacts": code},
                        project_id=project.project_id,
                    ))
            elif verdict == "APPROVE" and source == "fix_pr":
                project.phase = ProjectPhase.FINAL_REVIEW
                project.approvals["code"] = True
                project.approvals["qa"] = True
                store.save_project(project)
                store.set_approval(project.project_id, "code", True, "auto")
                store.set_approval(project.project_id, "qa", True, "auto")

        elif title == "test_suite":
            project.artifacts.setdefault("tests", []).append(signal.payload.get("suite", ""))
            store.save_project(project)

        elif title == "bug_report":
            project.artifacts.setdefault("bugs", []).append(signal.payload.get("bug_report", ""))
            store.save_project(project)

        elif title == "arch_changes":
            project.phase = ProjectPhase.ARCHITECTURE
            store.save_project(project)

    def _on_signal_for_log(self, signal: Signal) -> None:
        self._activity.append({
            "t": signal.timestamp,
            "from": signal.from_agent,
            "to": signal.to_agent,
            "type": signal.signal_type,
            "title": signal.payload.get("title", ""),
            "project_id": signal.project_id,
        })
        if len(self._activity) > 500:
            self._activity = self._activity[-500:]

    def activity(self, limit: int = 100) -> list[dict]:
        return self._activity[-limit:]

    # ---------- approvals (human-in-the-loop) ----------
    async def approve_gate(self, project_id: str, gate: str, note: str = "") -> None:
        store.set_approval(project_id, gate, True, note)
        project = store.get_project(project_id)
        if project:
            project.approvals[gate] = True
            if gate == "deploy":
                project.phase = ProjectPhase.DONE
            store.save_project(project)


brain = AriyaBrain()
