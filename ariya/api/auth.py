"""OAuth 2.0 flows for GitHub and ClickUp — spec §7 IDE integration.

GitHub App:  https://github.com/settings/developers → OAuth App
             Callback URL: http://localhost:8765/api/auth/github/callback

ClickUp App: https://app.clickup.com/settings/apps
             Callback URL: http://localhost:8765/api/auth/clickup/callback

Tokens are stored in-process (in-memory + config) for the MVP.
For production, persist in HashiCorp Vault (FIXES.md §12).
"""
from __future__ import annotations
import logging
import os
import secrets
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

log = logging.getLogger("ariya.auth")
auth_router = APIRouter(prefix="/auth")

# ── Config (set in .env) ──────────────────────────────────
GH_CLIENT_ID     = os.getenv("GITHUB_CLIENT_ID", "")
GH_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
GH_SCOPES        = "repo read:org"

CU_CLIENT_ID     = os.getenv("CLICKUP_CLIENT_ID", "")
CU_CLIENT_SECRET = os.getenv("CLICKUP_CLIENT_SECRET", "")

# ── In-memory token store ─────────────────────────────────
_tokens: dict[str, dict] = {
    "github":  {"token": os.getenv("GITHUB_TOKEN", ""),  "user": "", "repos": []},
    "clickup": {"token": os.getenv("CLICKUP_TOKEN", ""), "user": "", "teams": []},
}
_states: dict[str, str] = {}   # state → provider (CSRF protection)


def get_token(provider: str) -> str:
    return _tokens.get(provider, {}).get("token", "")


def integration_status() -> dict:
    gh = _tokens["github"]
    cu = _tokens["clickup"]
    return {
        "github":  {
            "connected": bool(gh["token"]),
            "oauth_configured": bool(GH_CLIENT_ID),
            "user": gh["user"],
            "repos": gh["repos"][:5],
        },
        "clickup": {
            "connected": bool(cu["token"]),
            "oauth_configured": bool(CU_CLIENT_ID),
            "user": cu["user"],
            "teams": cu["teams"],
        },
    }


# ── GitHub ────────────────────────────────────────────────
@auth_router.get("/github")
def github_login():
    if not GH_CLIENT_ID:
        return HTMLResponse(_oauth_error("GITHUB_CLIENT_ID is not set in .env"))
    state = secrets.token_urlsafe(16)
    _states[state] = "github"
    params = urlencode({"client_id": GH_CLIENT_ID, "scope": GH_SCOPES, "state": state})
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@auth_router.get("/github/callback")
async def github_callback(code: str = "", state: str = "", error: str = ""):
    if error or _states.pop(state, None) != "github":
        return HTMLResponse(_oauth_error(error or "Invalid state"))
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://github.com/login/oauth/access_token",
            json={"client_id": GH_CLIENT_ID, "client_secret": GH_CLIENT_SECRET, "code": code},
            headers={"Accept": "application/json"},
        )
    data = r.json()
    token = data.get("access_token", "")
    if not token:
        return HTMLResponse(_oauth_error(str(data)))
    _tokens["github"]["token"] = token
    # Fetch user + repos
    async with httpx.AsyncClient(headers={"Authorization": f"token {token}", "Accept": "application/json"}) as c:
        u = (await c.get("https://api.github.com/user")).json()
        repos_r = (await c.get("https://api.github.com/user/repos?per_page=30&sort=pushed")).json()
    _tokens["github"]["user"] = u.get("login", "")
    _tokens["github"]["repos"] = [r["full_name"] for r in (repos_r if isinstance(repos_r, list) else [])]
    log.info("GitHub connected: %s (%d repos)", _tokens["github"]["user"], len(_tokens["github"]["repos"]))
    return HTMLResponse(_oauth_success("GitHub", _tokens["github"]["user"]))


# ── ClickUp ───────────────────────────────────────────────
@auth_router.get("/clickup")
def clickup_login():
    if not CU_CLIENT_ID:
        return HTMLResponse(_oauth_error("CLICKUP_CLIENT_ID is not set in .env"))
    state = secrets.token_urlsafe(16)
    _states[state] = "clickup"
    params = urlencode({"client_id": CU_CLIENT_ID, "redirect_uri": _callback_url("clickup"), "state": state})
    return RedirectResponse(f"https://app.clickup.com/api?{params}")


@auth_router.get("/clickup/callback")
async def clickup_callback(code: str = "", state: str = "", error: str = ""):
    if error or _states.pop(state, None) != "clickup":
        return HTMLResponse(_oauth_error(error or "Invalid state"))
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://api.clickup.com/api/v2/oauth/token",
            json={"client_id": CU_CLIENT_ID, "client_secret": CU_CLIENT_SECRET,
                  "code": code, "redirect_uri": _callback_url("clickup")},
        )
    data = r.json()
    token = data.get("access_token", "")
    if not token:
        return HTMLResponse(_oauth_error(str(data)))
    _tokens["clickup"]["token"] = token
    async with httpx.AsyncClient(headers={"Authorization": token}) as c:
        u = (await c.get("https://api.clickup.com/api/v2/user")).json()
        teams = (await c.get("https://api.clickup.com/api/v2/team")).json()
    _tokens["clickup"]["user"] = u.get("user", {}).get("username", "")
    _tokens["clickup"]["teams"] = [t["name"] for t in teams.get("teams", [])]
    log.info("ClickUp connected: %s", _tokens["clickup"]["user"])
    return HTMLResponse(_oauth_success("ClickUp", _tokens["clickup"]["user"]))


# ── Helpers ───────────────────────────────────────────────
def _callback_url(provider: str) -> str:
    host = os.getenv("ARIYA_HOST", "127.0.0.1")
    port = os.getenv("ARIYA_PORT", "8765")
    return f"http://{host}:{port}/api/auth/{provider}/callback"


def _oauth_success(provider: str, user: str) -> str:
    return f"""<!DOCTYPE html><html><head>
<style>body{{background:#000508;color:#5fd8ff;font:14px/2 monospace;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}</style>
</head><body>
<div style="text-align:center">
  <div style="font-size:28px;margin-bottom:8px">✓</div>
  <div>{provider} connected as <b>{user}</b></div>
  <div style="color:#3d6070;margin-top:12px">You can close this window.</div>
</div>
<script>
  window.opener && window.opener.postMessage({{type:"oauth_success",provider:"{provider.lower()}",user:"{user}"}}, "*");
  setTimeout(() => window.close(), 2000);
</script></body></html>"""


def _oauth_error(msg: str) -> str:
    return f"""<!DOCTYPE html><html><head>
<style>body{{background:#000508;color:#ff6b6b;font:14px/2 monospace;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}</style>
</head><body>
<div style="text-align:center">
  <div style="font-size:28px;margin-bottom:8px">✗</div>
  <div>OAuth error: {msg}</div>
  <div style="color:#3d6070;margin-top:12px">Check your .env configuration.</div>
</div></body></html>"""
