from ariya.agents.base import BaseAgent
from ariya.models import Signal
from ariya.workspace import ProjectWorkspace, parse_files_from_text


class PhoenixAgent(BaseAgent):
    AGENT_ID = "PHOENIX"
    SYSTEM_PROMPT = (
        "You are PHOENIX, the self-healing engine. Given a bug report and the related code, "
        "produce candidate fixes as ```ts blocks with `// FILE: <path>` first line. "
        "End with: CONFIDENCE: <0..1>"
    )

    async def handle(self, signal: Signal):
        bug = signal.payload.get("bug_report", "")
        artifacts = signal.payload.get("artifacts", "")
        patch = await self.think(
            f"Bug report:\n{bug}\n\nRelated code:\n{artifacts}\n\n"
            "Emit fixed file(s) as fenced blocks with // FILE: header. "
            "End with CONFIDENCE: <0..1>."
        )
        confidence = 0.7
        for line in patch.splitlines()[::-1]:
            if "CONFIDENCE" in line.upper():
                try:
                    confidence = float(line.split(":")[-1].strip())
                except Exception:
                    pass
                break

        files = parse_files_from_text(patch)
        commit_sha = ""
        if signal.project_id and files:
            ws = ProjectWorkspace(signal.project_id)
            ws.branch(f"fix/phoenix-{signal.signal_id[:8]}")
            commit_sha = ws.commit_files(files, "PHOENIX: candidate fix", self.AGENT_ID)

        return self.reply(
            signal, "SENTINEL",
            {"title": "fix_pr", "code": patch, "confidence": confidence,
             "bug_report": bug, "files": [p for p, _ in files], "commit": commit_sha},
            priority=0.75,
        )
