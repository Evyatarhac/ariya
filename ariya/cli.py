"""Command-line entry. Usage:

    python -m ariya.cli new "Build a SaaS dashboard for restaurants"
    python -m ariya.cli status
    python -m ariya.cli approve <project_id> <gate>
"""
from __future__ import annotations
import asyncio
import json
import sys

import httpx
import typer
from rich.console import Console
from rich.table import Table

from ariya.config import settings

app = typer.Typer(no_args_is_help=True, help="ARIYA CLI")
console = Console()
BASE = f"http://{settings.host}:{settings.port}"


def _api(method: str, path: str, **kw):
    try:
        r = httpx.request(method, BASE + path, timeout=30.0, **kw)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        console.print(f"[red]Cannot reach ARIYA at {BASE}. Start it first: python -m ariya.main[/red]")
        sys.exit(1)


@app.command()
def new(brief: str, name: str = typer.Option("Untitled Project", help="Project name")):
    """Submit a new project brief to ARIYA."""
    res = _api("POST", "/api/projects", json={"name": name, "brief": brief})
    console.print(f"[green]Project created:[/green] {res['project_id']}  (phase: {res['phase']})")


@app.command()
def status():
    """Show projects + agent state."""
    projects = _api("GET", "/api/projects")
    agents = _api("GET", "/api/agents")

    t = Table(title="Projects")
    for col in ("id", "name", "phase", "tasks"):
        t.add_column(col)
    for p in projects:
        t.add_row(p["project_id"][:8], p["name"], p["phase"], str(len(p.get("tasks", []))))
    console.print(t)

    t2 = Table(title="Agents")
    for col in ("agent", "status", "current_task", "updated_at"):
        t2.add_column(col)
    for a in agents:
        t2.add_row(a["agent_id"], a["status"], a.get("current_task") or "-", a["updated_at"])
    console.print(t2)


@app.command()
def approve(project_id: str, gate: str, note: str = ""):
    """Approve a gate (design / architecture / code / qa / deploy)."""
    res = _api("POST", f"/api/projects/{project_id}/approve/{gate}", params={"note": note})
    console.print(f"[green]Approved gate '{gate}' for project {project_id[:8]}[/green]")


@app.command()
def activity(limit: int = 30):
    """Recent inter-agent signals."""
    items = _api("GET", "/api/activity", params={"limit": limit})
    for it in items:
        console.print(f"[dim]{it['t'][11:19]}[/dim] [cyan]{it['from']:>9}[/cyan] -> [magenta]{it['to']:<9}[/magenta] {it['type']:<10} {it.get('title','')}")


if __name__ == "__main__":
    app()
