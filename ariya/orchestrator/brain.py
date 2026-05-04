"""ARIYA — orchestrator brain (spec §5)."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional

from ariya.bus import bus
from ariya.gateway import gateway
from ariya.models import Project, ProjectPhase, Signal, SignalType
from ariya.state import store
from ariya.agents import ALL_AGENT_CLASSES
from ariya.orchestrator.router import best_agent

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
        self._project_context: dict[str, dict] = {}  # project_id → enriched ctx
        bus.subscribe(self.AGENT_ID, self._receive)
        bus.add_listener(self._on_signal_for_log)
        bus.set_context_injector(self._inject_context)

    # ---------- lifecycle ----------
    async def boot(self) -> None:
        for cls in ALL_AGENT_CLASSES:
            agent = cls()
            self._agents.append(agent)
            self._tasks.append(asyncio.create_task(agent.run()))
        store.update_agent(self.AGENT_ID, "idle")
        log.info("ARIYA booted with %d agents", len(self._agents))

    # ---------- context injection (spec §3.3) ----------
    def _inject_context(self, signal: Signal) -> Signal:
        if not signal.project_id:
            return signal
        ctx = self._project_context.get(signal.project_id, {})
        if ctx:
            merged = {**ctx, **(signal.context_window or {})}
            signal = signal.model_copy(update={"context_window": merged})
        return signal

    def update_project_context(self, project_id: str, **kv) -> None:
        self._project_context.setdefault(project_id, {}).update(kv)

    # ---------- intake ----------
    async def intake(self, name: str, brief: str, auto_approve: bool = True,
                     template: str = "") -> Project:
        if template:
            from ariya.templates import expand_brief
            brief = expand_brief(brief, template)
        project = Project(name=name, brief=brief, phase=ProjectPhase.RESEARCH)
        store.save_project(project)
        self.update_project_context(project.project_id,
                                    project_name=name, template=template,
                                    auto_approve=auto_approve)
        try:
            plan = await gateway.complete(
                self.AGENT_ID,
                f"Decompose this project brief into epics + tasks (markdown):\n{brief}",
                system=self.SYSTEM_PROMPT,
                project_id=project.project_id,
            )
            project.artifacts["plan"] = plan
            store.save_project(project)
        except Exception:
            log.exception("decomposition failed")

        # weighted route — research candidates
        chosen = best_agent(["SCOUT", "ARCHITECT"], task_keywords=["research", "market", "feature"], priority=4)
        log.info("intake routed to %s (score=%s)", chosen.agent_id, chosen.score)

        await bus.publish(Signal(
            from_agent=self.AGENT_ID,
            to_agent=chosen.agent_id,
            signal_type=SignalType.TASK,
            priority=0.85,
            payload={"title": "research", "brief": brief, "project_name": name,
                     "route_score": chosen.score, "route_reasons": chosen.reasons},
            project_id=project.project_id,
        ))
        return project

    # ---------- reply handling ----------
    async def _receive(self, signal: Signal) -> None:
        title = signal.payload.get("title", "")
        project = store.get_project(signal.project_id) if signal.project_id else None
        if not project:
            return
        auto = bool(signal.context_window.get("auto_approve", True))

        if title == "arch_approved":
            project.phase = ProjectPhase.DEVELOPMENT
            project.approvals["architecture"] = True
            store.save_project(project)
            store.set_approval(project.project_id, "architecture", True, "auto" if auto else "")

        elif title == "pr_reviewed":
            verdict = signal.payload.get("verdict", "APPROVE")
            source = signal.payload.get("source", "")
            if verdict == "APPROVE" and source in ("be_pr", "fe_pr"):
                project.phase = ProjectPhase.TESTING
                store.save_project(project)
                # CONTRACT_UPDATE: BE → FE
                if source == "be_pr":
                    await bus.publish(Signal(
                        from_agent=self.AGENT_ID, to_agent="FORGE-FE",
                        signal_type=SignalType.CONTRACT_UPDATE, priority=0.6,
                        payload={"title": "contract_update",
                                 "files": signal.payload.get("original_payload", {}).get("files", [])},
                        project_id=project.project_id,
                    ))
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
        if len(self._activity) > 1000:
            self._activity = self._activity[-1000:]

    def activity(self, limit: int = 100) -> list[dict]:
        return self._activity[-limit:]

    async def approve_gate(self, project_id: str, gate: str, note: str = "") -> None:
        store.set_approval(project_id, gate, True, note)
        project = store.get_project(project_id)
        if project:
            project.approvals[gate] = True
            if gate == "deploy":
                project.phase = ProjectPhase.DONE
            store.save_project(project)


brain = AriyaBrain()
