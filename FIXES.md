# ARIYA — First Fix Report

Status: **MVP foundation built**. The orchestrator + 9 agents + neural bus + skills DB + model gateway + dashboard run end-to-end. The list below is everything from the v1.0 spec that is **not yet** in this repo, organized by spec section. Each item is a real follow-up, not a polish task.

Legend: 🟥 critical · 🟧 important · 🟨 nice-to-have

---

## §3 Communication Layer
- 🟥 **Replace in-memory bus with Redis Streams or Kafka.** Current `MessageBus` is process-local — agents can't run in separate containers. The `publish/subscribe/history` API is the only thing that needs to stay; swap the implementation.
- 🟧 **Persistent DLQ.** Failed signals live only in memory. Should be persisted to PostgreSQL with a re-drive endpoint.
- 🟧 **Context injection by ARIYA.** Spec calls for ARIYA to enrich every signal before delivery. Today we just propagate `context_window` verbatim. Add a hook in `MessageBus.publish` that calls `brain.inject_context(signal)`.
- 🟨 **Signal TTL enforcement** with auto-escalation to ARIYA when a target doesn't ack.

## §4 Agents
- 🟥 **Real tool-use loops.** Every agent currently calls the LLM once. SCOUT needs web-fetch tools, FORGE-* need filesystem/Git tools, GUARDIAN needs a CI runner, PHOENIX needs a sandboxed test runner. Wire Anthropic tool-use / OpenAI function calling.
- 🟥 **FORGE agents must actually write files** to `projects/<id>/repo` and create real git commits. Today they only return code as text in the signal payload.
- 🟧 **CONTRACT_UPDATE protocol** between FORGE-BE ↔ FORGE-FE for API contract sync. The signal type is defined; no agent emits it yet.
- 🟧 **PROBE browser automation** (Playwright). Today PROBE only generates test scenarios — it doesn't run them.
- 🟧 **GUARDIAN actual CI integration** with GitHub Actions / local act runner.
- 🟨 **Agent-level retry policy** with backoff and circuit breaker.

## §5 ARIYA Brain
- 🟧 **Weighted decision matrix** for routing (skill match × current load × priority × deps × historical perf). Today routing is hardcoded into the agent reply chain.
- 🟧 **Conflict resolution** — `ARIYA.handle_conflict(a,b)` exists conceptually only; implement when two FORGE agents touch the same file.
- 🟧 **Sprint engine** — sprint planning, daily standup digest, retro analytics.
- 🟨 **Natural-language command parsing** beyond "create project" (e.g. "pause SCOUT", "switch FORGE-BE to GPT-4o", "show me the wireframes").

## §6 Skills DB
- 🟧 **Migrate to MongoDB.** Currently a JSON file. Schema is already document-shaped.
- 🟧 **Few-shot example storage** with embeddings + retrieval at prompt time.
- 🟧 **Prompt auto-refinement** based on success_rate trends.
- 🟨 **Skill versioning UI + rollback.**

## §7 IDE Integration
- 🟥 **VS Code extension** — entirely missing. Need: sidebar panel, file watcher, live code stream, branch viewer, conflict markers. Scaffold under `vscode-extension/` (TypeScript).
- 🟧 **WebSocket events** spec-defined (`file_changed`, `agent_started`, …) — only `signals` + `agents` are emitted today. Map the rest.
- 🟨 **LSP hooks** for inline agent comments.

## §8 Monitoring Dashboard
- 🟧 **Neural Flow Map** — animated graph (D3 / Cytoscape) showing live signal traversal. Today only a list.
- 🟧 **Project Gantt / burndown** view.
- 🟧 **Cost tracker** — token usage per agent/model. Hook into `gateway.complete` and persist.
- 🟨 **Alerting system** (stuck agent, quality drop, cost spike, conflict).

## §9 Model Gateway
- 🟧 **Google Gemini provider** (used by SCOUT in spec).
- 🟧 **Mistral / Codestral provider** (FORGE-BE secondary).
- 🟧 **Self-hosted Llama** support (privacy mode).
- 🟧 **Dynamic model routing** by task complexity / context length / cost budget — today we always use the agent's primary.
- 🟨 **Streaming responses** to the dashboard for "live code typing" effect.

## §10 Workflow
- 🟧 **Branch-per-task git workflow** with PR creation against the project repo (not the agent repo).
- 🟧 **Multi-iteration review loop** — SENTINEL feedback should re-enter FORGE; today it stops at the first verdict.
- 🟧 **Deploy stage** — only a gate exists; no deployer agent action.

## §11 State & Artifacts
- 🟧 **PostgreSQL** for production state (SQLite is MVP-only).
- 🟧 **Object storage for artifacts** (S3-compatible) — wireframes/screenshots/PDFs. Today everything is JSON in SQLite.
- 🟨 **Snapshots** of project state at each phase transition.

## §12 Security
- 🟥 **Agent sandboxing.** Agents run in-process today. Need Docker-per-agent runtime with FS + network restrictions.
- 🟥 **HashiCorp Vault / AWS Secrets Manager** integration. Today secrets live in `.env`.
- 🟧 **Audit log** of every file operation per agent.
- 🟧 **Auth on the API** — anyone on the host can hit `/api/projects`.
- 🟧 **Human-authorization gates** for prod deploy / DB migrations / external API calls — only the data model exists; enforcement TBD.

## §13 Deployment
- 🟧 **Dockerfile + docker-compose** with services per layer.
- 🟧 **Helm chart** for Kubernetes deployment.
- 🟧 **Multi-tenant isolation** (per-org namespacing of projects, agents, skills).

## §14 Tech Stack
- 🟧 **Prometheus + Grafana** wiring.
- 🟧 **ELK / Loki** log aggregation.

## §15 Roadmap (Phase 2+)
- 🟨 Project templates (SaaS / E-commerce / Mobile API) — easy seed once pipeline is solid.
- 🟨 Agent marketplace / SDK for custom agents.
- 🟨 Multi-project concurrency (today nothing prevents it but there's no scheduler).
- 🟨 SSO + audit logs (enterprise).

---

## Repo / DX still missing
- 🟧 `Dockerfile` + `docker-compose.yml`
- 🟧 GitHub Actions CI for this repo (lint + tests)
- 🟧 More test coverage — currently only smoke tests
- 🟨 Pre-commit hooks (ruff, black, mypy)
