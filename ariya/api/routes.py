from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ariya.bus import bus
from ariya.orchestrator import brain
from ariya.skills import registry
from ariya.state import store

router = APIRouter()


class ProjectIn(BaseModel):
    name: str
    brief: str
    auto_approve: bool = True


@router.post("/projects")
async def create_project(p: ProjectIn):
    proj = await brain.intake(p.name, p.brief, p.auto_approve)
    return {"project_id": proj.project_id, "name": proj.name, "phase": proj.phase}


@router.get("/projects")
def list_projects():
    return [p.model_dump() for p in store.list_projects()]


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    p = store.get_project(project_id)
    return p.model_dump() if p else {"error": "not found"}


@router.post("/projects/{project_id}/approve/{gate}")
async def approve(project_id: str, gate: str, note: str = ""):
    await brain.approve_gate(project_id, gate, note)
    return {"ok": True}


@router.get("/agents")
def agents():
    return store.all_agents()


@router.get("/skills")
def skills():
    return [s.model_dump() for s in registry.all()]


@router.get("/activity")
def activity(limit: int = 100):
    return brain.activity(limit)


@router.get("/signals")
def signals(limit: int = 50):
    return [s.model_dump() for s in bus.history(limit)]


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    seen = 0
    try:
        while True:
            await asyncio.sleep(1.0)
            history = bus.history(200)
            new = history[seen:]
            seen = len(history)
            if new:
                await websocket.send_text(json.dumps({
                    "type": "signals",
                    "signals": [s.model_dump() for s in new],
                }))
            await websocket.send_text(json.dumps({
                "type": "agents",
                "agents": store.all_agents(),
            }))
    except WebSocketDisconnect:
        return
