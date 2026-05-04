# ARIYA — Fix Report

Tracks the gap between the v1.0 spec and the current implementation.
✅ = done in `ARIYA0.1` branch · 🟥 critical · 🟧 important · 🟨 nice-to-have

---

## §3 Communication Layer
- ✅ **Redis Streams backend** with in-memory fallback (`ariya/bus/message_bus.py`). Toggle via `ARIYA_BUS=redis`.
- ✅ **Context injection by ARIYA** — `bus.set_context_injector(brain._inject_context)` enriches every signal with project context before delivery.
- 🟧 **Persistent DLQ to PostgreSQL** + re-drive endpoint. (DLQ now exposed at `/api/dlq` but lives in memory.)
- 🟨 **Signal TTL enforcement** with auto-escalation.

## §4 Agents
- ✅ **Real file writes + git commits** — `ariya/workspace/repo.py` parses LLM output, writes safe files, creates branches per task, commits with the agent as author. Used by FORGE-BE, FORGE-FE, PHOENIX.
- ✅ **CONTRACT_UPDATE protocol** — when FORGE-BE PR is approved, ARIYA emits `CONTRACT_UPDATE` to FORGE-FE; FORGE-FE accepts an `api_contract` payload at implement time.
- 🟥 **Real tool-use loops** (Anthropic tool-use / OpenAI function calling) — agents still do single-shot completions. Web fetch for SCOUT, real test runner for GUARDIAN, sandboxed exec for PHOENIX.
- 🟧 **PROBE Playwright integration** — currently text-only test scenarios.
- 🟧 **GUARDIAN actual CI runner** integration.
- 🟨 Per-agent retry policy with circuit breaker.

## §5 ARIYA Brain
- ✅ **Weighted decision matrix** routing — `ariya/orchestrator/router.py` (skill match + load + priority + history).
- ✅ **Multi-iteration review loop** — SENTINEL bounces REQUEST_CHANGES back to FORGE/PHOENIX with prior_review until `MAX_REVIEW_ITERATIONS=3`.
- ✅ **Sprint engine** — standup digest + velocity (`ariya/orchestrator/sprint.py`, `/api/projects/{id}/standup`, `/velocity`).
- 🟧 **Conflict resolution agent action** when two FORGE agents touch the same file (data path exists, decision logic is stub).
- 🟨 NL command parsing beyond intake.

## §6 Skills DB
- 🟧 MongoDB migration (still JSON file).
- 🟧 Few-shot retrieval with embeddings.
- 🟧 Auto prompt refinement from `success_rate` trend.
- 🟨 Skill versioning UI.

## §7 IDE Integration
- ✅ **VS Code extension scaffold** (`vscode-extension/`) — agent + signal tree views, launch-project command, configurable endpoint+token.
- 🟧 WebSocket subscription instead of polling.
- 🟧 Live code-streaming overlay (gateway already supports `on_token` streaming hook).
- 🟨 LSP hooks for inline agent comments.

## §8 Monitoring Dashboard
- ✅ **Neural Flow Map** (animated SVG node graph with live edge weighting).
- ✅ **Cost tracker** (`/api/cost`) — by agent, model, project; surfaced on the dashboard.
- 🟧 Project Gantt / burndown.
- 🟨 Alerting system (stuck agent / cost spike / quality drop).

## §9 Model Gateway
- ✅ **Cost accounting** integrated in `gateway.complete()` for both providers + mock.
- ✅ **Dynamic model routing** by complexity / context length / cost-priority (`select_model()`).
- ✅ **Streaming responses** — `on_token` async callback, wired through Anthropic streaming API.
- 🟧 Google Gemini provider.
- 🟧 Mistral / Codestral provider.
- 🟧 Self-hosted Llama support.

## §10 Workflow
- ✅ **Branch-per-task git workflow** in the project repo (`feat/be-*`, `feat/fe-*`, `fix/phoenix-*`).
- ✅ **Project templates** — `saas`, `ecommerce`, `mobile-api` (`ariya/templates/`), exposed in dashboard dropdown.
- ✅ **Multi-iteration review** (see §5).
- 🟧 Real PR-against-main flow with merge-on-approve.
- 🟧 Deployer agent action.

## §11 State & Artifacts
- 🟧 PostgreSQL prod store.
- 🟧 S3-compatible artifact storage.
- 🟨 Phase snapshots.

## §12 Security
- ✅ **API auth** — bearer token via `ARIYA_API_TOKEN`. Dashboard reads `localStorage.ariya_token`.
- 🟥 **Agent sandboxing** in Docker per agent (still in-process).
- 🟥 **Vault / Secrets Manager** integration.
- 🟧 File-operation audit log per agent.
- 🟧 Human-authorization enforcement on prod-deploy / DB migrations / external APIs.

## §13 Deployment
- ✅ **Dockerfile** + **docker-compose.yml** (with Redis service).
- 🟧 Helm chart.
- 🟧 Multi-tenant isolation.

## §14 Tech Stack / Ops
- 🟧 Prometheus + Grafana wiring.
- 🟧 ELK / Loki log aggregation.

## Repo / DX
- ✅ **GitHub Actions CI** (`.github/workflows/ci.yml`) — lint+test on push & PR.
- ✅ **Test coverage expanded** — schema, workspace parser, traversal sanitizer, router scoring, cost tracker, templates, skill plasticity, full pipeline smoke. (9 tests, all green.)
- 🟨 Pre-commit hooks (ruff, black, mypy).
