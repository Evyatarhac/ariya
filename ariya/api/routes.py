from __future__ import annotations
import asyncio
import json
import os
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ariya.api.auth import auth_router, integration_status
from ariya.bus import bus
from ariya.gateway import gateway
from ariya.gateway.model_gateway import cost
from ariya.orchestrator import brain
from ariya.orchestrator.sprint import standup_digest, velocity
from ariya.skills import registry
from ariya.state import store
from ariya.workspace.repo import ROOT as PROJECTS_ROOT

router = APIRouter()

API_TOKEN = os.getenv("ARIYA_API_TOKEN", "")


def auth(authorization: str | None = Header(default=None)):
    """If ARIYA_API_TOKEN is set, require Bearer token. Otherwise open."""
    if not API_TOKEN:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    if authorization.split(" ", 1)[1].strip() != API_TOKEN:
        raise HTTPException(403, "bad token")


class ProjectIn(BaseModel):
    name: str
    brief: str
    auto_approve: bool = True
    template: str = ""


@router.post("/projects", dependencies=[Depends(auth)])
async def create_project(p: ProjectIn):
    proj = await brain.intake(p.name, p.brief, p.auto_approve, p.template)
    return {"project_id": proj.project_id, "name": proj.name, "phase": proj.phase}


@router.get("/projects")
def list_projects():
    return [p.model_dump() for p in store.list_projects()]


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    p = store.get_project(project_id)
    return p.model_dump() if p else {"error": "not found"}


@router.get("/projects/{project_id}/files")
def get_files(project_id: str):
    repo = PROJECTS_ROOT / project_id / "repo"
    if not repo.exists():
        return {"files": []}
    files = []
    for path in repo.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        rel = path.relative_to(repo)
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        files.append({"path": str(rel).replace("\\", "/"), "size": size})
    return {"files": files}


@router.get("/projects/{project_id}/file")
def get_file(project_id: str, path: str):
    repo = PROJECTS_ROOT / project_id / "repo"
    target = (repo / path).resolve()
    if not str(target).startswith(str(repo.resolve())):
        raise HTTPException(400, "bad path")
    if not target.is_file():
        raise HTTPException(404, "not found")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}


@router.get("/projects/{project_id}/standup")
def get_standup(project_id: str):
    return standup_digest(project_id)


@router.get("/projects/{project_id}/velocity")
def get_velocity(project_id: str):
    return velocity(project_id)


@router.post("/projects/{project_id}/approve/{gate}", dependencies=[Depends(auth)])
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


@router.get("/cost")
def get_cost():
    return cost.snapshot()


@router.get("/dlq")
def get_dlq():
    return [{"signal": s.model_dump(), "error": err} for s, err in bus.dlq()]


# ── ARIYA conversational chat ───────────────────────────────────
class ChatIn(BaseModel):
    text: str

ARIYA_SYSTEM_PROMPT = (
    "You are ARIYA — the orchestrator brain of an autonomous multi-agent "
    "engineering studio. You command nine specialist agents: SCOUT (research), "
    "ARCHITECT (specs), SENTINEL (review/security), FORGE-BE (backend), "
    "FORGE-FE (frontend), PROBE (manual QA), GUARDIAN (automated tests), "
    "PHOENIX (self-healing), and HERALD (delivery). "
    "Speak in a calm, confident, slightly formal tone — think Jarvis. "
    "Answers should be 1–3 short sentences unless the user asks for depth. "
    "When the user describes a project to build, briefly acknowledge and say "
    "you're routing it to SCOUT — do NOT actually create the project yourself "
    "in chat (the orchestrator handles that separately). "
    "When asked status/cost/repos questions, answer from the live context "
    "the user provides."
)

def _classify_intent(text: str) -> str:
    """Classify user input → 'project' (build something) | 'command' | 'chat'."""
    t = text.lower().strip()
    if t in ("status", "report", "מה המצב", "סטטוס", "דוח"): return "command"
    if t.startswith("approve ") or t.startswith("אשר "): return "command"
    # English build verbs
    en_triggers = ["build ", "create ", "make ", "develop ", "design ",
                   "ship ", "launch a ", "i want to build", "i need an app",
                   "a website", "a system that"]
    # Hebrew build verbs (no .lower() effect on Hebrew, but kept consistent)
    he_triggers = ["תבנה", "תפתח", "תעצב", "תקים", "תעלה", "בנה ",
                   "פתח פרוייקט", "צור פרוייקט", "פרוייקט חדש",
                   "אני רוצה לבנות", "אני צריך אפליקציה", "אני צריך מערכת"]
    triggers = en_triggers + he_triggers
    if any(tr in t for tr in triggers) and len(text.split()) >= 3:
        return "project"
    return "chat"

@router.post("/chat")
async def chat(c: ChatIn):
    """ARIYA's conversational endpoint. Returns reply + detected intent."""
    intent = _classify_intent(c.text)

    if intent == "command":
        # Caller (frontend) handles status/approve directly via existing endpoints.
        return {"intent": "command", "reply": ""}

    # Build live context for ARIYA
    projects = store.list_projects()
    cost_snap = cost.snapshot()
    integ = integration_status()
    context = (
        f"Active projects: {len(projects)} "
        f"({', '.join(p.name + '/' + p.phase for p in projects[:5]) or 'none'}). "
        f"Total spend: ${cost_snap.get('total_usd', 0):.4f}. "
        f"GitHub: {'connected as ' + integ['github']['user'] if integ['github']['connected'] else 'not connected'}. "
        f"ClickUp: {'connected as ' + integ['clickup']['user'] if integ['clickup']['connected'] else 'not connected'}."
    )
    prompt = f"Live system state: {context}\n\nUser: {c.text}\n\nReply as ARIYA:"

    try:
        reply = await gateway.complete(
            agent_id="ARIYA",
            prompt=prompt,
            system=ARIYA_SYSTEM_PROMPT,
            max_tokens=400,
        )
        # Strip mock prefix if in mock mode for cleaner UX
        if reply.startswith("[MOCK::") or "Set ANTHROPIC_API_KEY" in reply:
            t = c.text.lower()
            if any(g in t for g in ["hello", "hi", "שלום", "היי"]):
                reply = "Greetings, Sir. The agent network is online and standing by."
            elif intent == "project":
                reply = "Acknowledged. Decomposing the brief — routing to SCOUT."
            elif "status" in t or "מצב" in t or len(projects) > 0:
                reply = (f"Tracking {len(projects)} project(s). "
                         f"Total spend ${cost_snap.get('total_usd', 0):.4f}. "
                         f"Network nominal.")
            else:
                reply = ("Mock mode — language core offline. "
                         "Add ANTHROPIC_API_KEY to .env for live conversation. "
                         "Pipeline orchestration still works fully.")
    except Exception as e:
        reply = f"My language core is offline ({type(e).__name__}). Falling back to command mode."

    return {"intent": intent, "reply": reply.strip()}


@router.get("/integrations")
def integrations():
    return integration_status()


class TokenIn(BaseModel):
    token: str

@router.post("/integrations/github/token")
async def set_github_token(t: TokenIn):
    from ariya.api.auth import _tokens
    import httpx
    _tokens["github"]["token"] = t.token
    try:
        async with httpx.AsyncClient(headers={"Authorization": f"token {t.token}", "Accept": "application/json"}) as c:
            u = (await c.get("https://api.github.com/user")).json()
            repos_r = (await c.get("https://api.github.com/user/repos?per_page=30&sort=pushed")).json()
        _tokens["github"]["user"] = u.get("login", "")
        _tokens["github"]["repos"] = [r["full_name"] for r in (repos_r if isinstance(repos_r, list) else [])]
    except Exception:
        pass
    return {"ok": True, "user": _tokens["github"]["user"]}

@router.post("/integrations/clickup/token")
async def set_clickup_token(t: TokenIn):
    from ariya.api.auth import _tokens
    import httpx
    _tokens["clickup"]["token"] = t.token
    try:
        async with httpx.AsyncClient(headers={"Authorization": t.token}) as c:
            u = (await c.get("https://api.clickup.com/api/v2/user")).json()
            teams = (await c.get("https://api.clickup.com/api/v2/team")).json()
        _tokens["clickup"]["user"] = u.get("user", {}).get("username", "")
        _tokens["clickup"]["teams"] = [tm["name"] for tm in teams.get("teams", [])]
    except Exception:
        pass
    return {"ok": True, "user": _tokens["clickup"]["user"]}

router.include_router(auth_router)

@router.get("/health")
def health():
    return {"ok": True, "agents": len(store.all_agents()), "mock": gateway.__class__.__name__}


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
                "cost": cost.snapshot(),
            }))
    except WebSocketDisconnect:
        return
