# ARIYA — VS Code Extension (scaffold)

Connects VS Code to a running ARIYA orchestrator and surfaces live agent state and signal flow inside the editor.

## Install (dev)
```bash
cd vscode-extension
npm i
npm run compile
```
Then in VS Code: `Run > Start Debugging` (or F5) to launch the extension host.

## Settings
- `ariya.endpoint` — default `http://127.0.0.1:8000`
- `ariya.token` — bearer token if `ARIYA_API_TOKEN` is set on the server

## Commands
- `ARIYA: Open Dashboard`
- `ARIYA: Launch Project`

## Status
This is a scaffold (FIXES.md §7). It polls REST every 3s. Next steps:
- WebSocket subscription instead of polling
- Live code-streaming overlay
- Branch indicator per agent
- Inline agent comments via decorations
