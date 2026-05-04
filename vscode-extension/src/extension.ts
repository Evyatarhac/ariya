import * as vscode from "vscode";
import * as http from "http";

const cfg = () => vscode.workspace.getConfiguration("ariya");

function get(path: string): Promise<any> {
  const base: string = cfg().get("endpoint") || "http://127.0.0.1:8000";
  const token: string = cfg().get("token") || "";
  return new Promise((resolve, reject) => {
    const url = new URL(base + path);
    http.get(
      { hostname: url.hostname, port: url.port, path: url.pathname + url.search,
        headers: token ? { Authorization: `Bearer ${token}` } : {} },
      (res) => {
        let body = "";
        res.on("data", (c) => (body += c));
        res.on("end", () => {
          try { resolve(JSON.parse(body)); } catch (e) { reject(e); }
        });
      }
    ).on("error", reject);
  });
}

class AgentTreeProvider implements vscode.TreeDataProvider<any> {
  private _emitter = new vscode.EventEmitter<any>();
  onDidChangeTreeData = this._emitter.event;
  refresh() { this._emitter.fire(undefined); }
  getTreeItem(el: any) {
    const item = new vscode.TreeItem(`${el.agent_id}  ·  ${el.status}`);
    item.description = el.current_task || "";
    item.iconPath = new vscode.ThemeIcon(el.status === "processing" ? "sync~spin" : "circle-outline");
    return item;
  }
  async getChildren() {
    try { return await get("/api/agents"); } catch { return []; }
  }
}

class SignalTreeProvider implements vscode.TreeDataProvider<any> {
  private _emitter = new vscode.EventEmitter<any>();
  onDidChangeTreeData = this._emitter.event;
  refresh() { this._emitter.fire(undefined); }
  getTreeItem(el: any) {
    const t = (el.t || "").substr(11, 8);
    const item = new vscode.TreeItem(`${t}  ${el.from} → ${el.to}`);
    item.description = `${el.type}  ${el.title || ""}`;
    return item;
  }
  async getChildren() {
    try { const a = await get("/api/activity?limit=50"); return a.reverse(); } catch { return []; }
  }
}

export function activate(ctx: vscode.ExtensionContext) {
  const agents = new AgentTreeProvider();
  const signals = new SignalTreeProvider();
  vscode.window.registerTreeDataProvider("ariya.agents", agents);
  vscode.window.registerTreeDataProvider("ariya.signals", signals);

  setInterval(() => { agents.refresh(); signals.refresh(); }, 3000);

  ctx.subscriptions.push(
    vscode.commands.registerCommand("ariya.openDashboard", () => {
      vscode.env.openExternal(vscode.Uri.parse(cfg().get("endpoint") || "http://127.0.0.1:8000"));
    }),
    vscode.commands.registerCommand("ariya.launchProject", async () => {
      const name = await vscode.window.showInputBox({ prompt: "Project name" });
      if (!name) return;
      const brief = await vscode.window.showInputBox({ prompt: "Project brief" });
      if (!brief) return;
      const base: string = cfg().get("endpoint") || "http://127.0.0.1:8000";
      const token: string = cfg().get("token") || "";
      const url = new URL(base + "/api/projects");
      const data = JSON.stringify({ name, brief });
      const req = http.request({
        hostname: url.hostname, port: url.port, path: url.pathname,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(data),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }, (res) => {
        let body = "";
        res.on("data", (c) => (body += c));
        res.on("end", () => vscode.window.showInformationMessage("ARIYA: " + body));
      });
      req.on("error", (e) => vscode.window.showErrorMessage("ARIYA error: " + e.message));
      req.write(data); req.end();
    }),
  );
}

export function deactivate() {}
