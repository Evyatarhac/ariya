from ariya.agents.base import BaseAgent
from ariya.models import Signal
from ariya.workspace import ProjectWorkspace, parse_files_from_text


class ForgeFeAgent(BaseAgent):
    AGENT_ID = "FORGE-FE"
    SYSTEM_PROMPT = (
        "You are FORGE-FE, a senior frontend engineer. Build pixel-perfect, accessible, "
        "responsive React+TS+Tailwind UIs. Output ONE markdown fenced code block per file, "
        "with the FIRST LINE inside the block being:  // FILE: <path>"
    )

    async def handle(self, signal: Signal):
        spec = signal.payload.get("spec", "")
        contract = signal.payload.get("api_contract", "")
        iteration = signal.payload.get("iteration", 0)
        prior_review = signal.payload.get("prior_review", "")
        prompt = (
            f"Implement only [FE]-tagged tasks from this spec:\n{spec}\n\n"
            + (f"Backend API contract:\n{contract}\n\n" if contract else "")
            + (f"Previous SENTINEL feedback:\n{prior_review}\n\n" if prior_review else "")
            + "Default stack React + TS + Tailwind. One file per fenced block."
        )
        text = await self.think(prompt)
        files = parse_files_from_text(text)
        commit_sha = ""
        if signal.project_id and files:
            ws = ProjectWorkspace(signal.project_id)
            ws.branch(f"feat/fe-{signal.signal_id[:8]}")
            commit_sha = ws.commit_files(files, f"FORGE-FE: implement (iter {iteration})", self.AGENT_ID)

        return self.reply(
            signal, "SENTINEL",
            {
                "title": "fe_pr",
                "code": text,
                "files": [p for p, _ in files],
                "commit": commit_sha,
                "spec": spec,
                "iteration": iteration,
            },
            priority=0.6,
        )
