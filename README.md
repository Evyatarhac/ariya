# ARIYA — Autonomous R&D Intelligence Yielding Architecture

> *"The future of software development is not writing code faster — it's orchestrating intelligence."*

ARIYA is a multi-agent AI development ecosystem. A central "brain" (ARIYA) routes work to a network of specialized agents (SCOUT, ARCHITECT, SENTINEL, FORGE-BE, FORGE-FE, PROBE, GUARDIAN, PHOENIX) that together cover the full R&D lifecycle — from market research to deployment.

This repository contains the **MVP foundation** built from the v1.0 system specification.
For a list of what's implemented vs. still TODO, see [FIXES.md](FIXES.md).

---

## Quick start

```bash
# 1. Install
python -m venv .venv
. .venv/Scripts/activate     # Windows
# source .venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# 2. Configure (optional — without keys, agents run in MOCK mode)
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY / OPENAI_API_KEY

# 3. Run the orchestrator (FastAPI + dashboard at http://localhost:8000)
python -m ariya.main

# 4. Or use the CLI to kick off a project
python -m ariya.cli new "Build a SaaS dashboard for restaurant orders, React + Node + PostgreSQL"
python -m ariya.cli status
```

Open `http://localhost:8000` for the Jarvis-style dashboard.

---

## How it works (the flow)

```
   Human ──prompt──▶  ARIYA Brain
                          │
                          ▼
            ┌─────── Task Router ───────┐
            │                            │
   ┌────────┴────────┐         ┌─────────┴────────┐
   │ SCOUT (research)│         │ ARCHITECT (specs)│
   └────────┬────────┘         └─────────┬────────┘
            │                            │
            └──────► Neural Bus ◄────────┘
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
        FORGE-BE      FORGE-FE       SENTINEL
            │             │             │
            └──────► Neural Bus ◄───────┘
                          │
                  ┌───────┴───────┐
                  ▼               ▼
                PROBE          GUARDIAN
                  │               │
                  └──► PHOENIX (self-heal) ──► SENTINEL ──► Deploy gate (human)
```

Every signal between agents follows a standard schema (see [`ariya/models/signal.py`](ariya/models/signal.py)) — the same shape described in spec §3.1.

---

## Repo layout

```
ariya/
  main.py             FastAPI app + dashboard mount
  cli.py              command-line entry
  orchestrator/       ARIYA brain, task router, workflow engine
  agents/             9 specialized agents (base + 8 specialists + ARIYA)
  bus/                Neural message bus (in-memory pub/sub, Redis-ready)
  gateway/            Model gateway (Anthropic / OpenAI / Mock)
  skills/             Skills DB + seed skills
  state/              SQLite state store
  api/                REST + WebSocket endpoints
  dashboard/          Static HTML/JS Jarvis-style UI
docs/                 Architecture notes
tests/                Smoke tests
FIXES.md              First fix-report — what's left to build
```
