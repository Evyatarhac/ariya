from ariya.agents.base import BaseAgent
from ariya.models import Signal, SignalType
from ariya.workspace import ProjectWorkspace, parse_files_from_text


class ForgeBeAgent(BaseAgent):
    AGENT_ID = "FORGE-BE"
    SYSTEM_PROMPT = (
        "You are FORGE-BE, a senior backend engineer. Implement server-side code, APIs, "
        "DB migrations, and unit tests strictly per the spec. Output ONE markdown fenced "
        "code block per file, with the FIRST LINE inside the block being:  // FILE: <path>\n"
        "Default to TypeScript+Express+PostgreSQL unless the spec says otherwise."
    )

    async def handle(self, signal: Signal):
        spec = signal.payload.get("spec", "")
        iteration = signal.payload.get("iteration", 0)
        prior_review = signal.payload.get("prior_review", "")
        prompt = (
            f"Implement only [BE]-tagged tasks from this spec:\n{spec}\n\n"
            + (f"Previous SENTINEL feedback to address:\n{prior_review}\n\n" if prior_review else "")
            + "Produce real source files. Each file as: ```ts\\n// FILE: path/to/file.ts\\n<code>\\n```"
        )
        text = await self.think(prompt)

        files = parse_files_from_text(text)
        commit_sha = ""
        if signal.project_id and files:
            ws = ProjectWorkspace(signal.project_id)
            ws.branch(f"feat/be-{signal.signal_id[:8]}")
            commit_sha = ws.commit_files(files, f"FORGE-BE: implement (iter {iteration})", self.AGENT_ID)

        return self.reply(
            signal, "SENTINEL",
            {
                "title": "be_pr",
                "code": text,
                "files": [p for p, _ in files],
                "commit": commit_sha,
                "spec": spec,
                "iteration": iteration,
            },
            priority=0.6,
        )
