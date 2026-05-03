const AGENTS = ["ARIYA","SCOUT","ARCHITECT","SENTINEL","FORGE-BE","FORGE-FE","PROBE","GUARDIAN","PHOENIX"];
const GATES = ["design","architecture","code","qa","deploy"];

const $ = (id) => document.getElementById(id);
const TOKEN = localStorage.getItem("ariya_token") || "";

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (TOKEN) opts.headers.Authorization = `Bearer ${TOKEN}`;
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

function renderAgents(agents) {
  const known = Object.fromEntries(agents.map(a => [a.agent_id, a]));
  $("agents").innerHTML = AGENTS.map(id => {
    const a = known[id] || { status: "idle", current_task: "" };
    return `<div class="agent ${a.status}">
      <div class="dot"></div>
      <div class="name">${id}</div>
      <div class="task">${a.current_task || "—"}</div>
    </div>`;
  }).join("");
}

// Neural Flow Map — radial layout with edges drawn from recent signals
const POS = {};
function layoutGraph() {
  const cx = 300, cy = 160, r = 120;
  AGENTS.forEach((id, i) => {
    if (id === "ARIYA") { POS[id] = { x: cx, y: cy }; return; }
    const a = (i - 1) / (AGENTS.length - 1) * Math.PI * 2;
    POS[id] = { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
  });
}
layoutGraph();

function renderGraph(activity, agentStatus) {
  const svg = $("graph");
  const known = Object.fromEntries((agentStatus||[]).map(a => [a.agent_id, a]));
  const recent = activity.slice(-25);
  const counts = {};
  recent.forEach(s => {
    const k = `${s.from}|${s.to}`;
    counts[k] = (counts[k] || 0) + 1;
  });

  let edges = "";
  Object.entries(counts).forEach(([k, c]) => {
    const [from, to] = k.split("|");
    if (!POS[from] || !POS[to] || from === to) return;
    const a = POS[from], b = POS[to];
    const w = Math.min(4, 0.6 + c * 0.4);
    edges += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="rgba(0,212,255,${0.25 + Math.min(c, 5) * 0.12})" stroke-width="${w}" />`;
  });

  let nodes = "";
  AGENTS.forEach(id => {
    const p = POS[id];
    const busy = (known[id]?.status === "processing");
    const fill = id === "ARIYA" ? "#00d4ff" : (busy ? "#4ad6ff" : "rgba(0,212,255,0.18)");
    const stroke = busy ? "#00d4ff" : "rgba(0,212,255,0.5)";
    const r = id === "ARIYA" ? 22 : 14;
    nodes += `<g>
      <circle cx="${p.x}" cy="${p.y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="1.5">
        ${busy ? '<animate attributeName="r" values="'+(r-2)+';'+(r+3)+';'+(r-2)+'" dur="1.2s" repeatCount="indefinite"/>' : ""}
      </circle>
      <text x="${p.x}" y="${p.y + r + 12}" fill="#9ad" font-size="10" text-anchor="middle">${id}</text>
    </g>`;
  });

  svg.innerHTML = edges + nodes;
}

function renderActivity(items) {
  $("activity").innerHTML = items.slice(-80).reverse().map(it =>
    `<div class="activity-row">
       <span>${(it.t||"").substr(11,8)}</span>
       <span class="from">${it.from}</span>
       →
       <span class="to">${it.to}</span>
       <span class="type">${it.type}</span>
       <span class="title">${it.title||""}</span>
     </div>`
  ).join("");
}

function renderProjects(projects) {
  $("projects").innerHTML = projects.map(p => {
    const approvals = p.approvals || {};
    const gates = GATES.map(g =>
      `<button class="gate-btn ${approvals[g] ? "approved" : ""}"
               onclick="approveGate('${p.project_id}','${g}')">${g}</button>`
    ).join("");
    return `<div class="project">
      <div class="name">${p.name} <span class="phase">· ${p.phase}</span></div>
      <div class="gates">${gates}</div>
      <div class="links">
        <a href="#" onclick="viewFiles('${p.project_id}');return false;">files</a>
        <a href="#" onclick="viewStandup('${p.project_id}');return false;">standup</a>
      </div>
    </div>`;
  }).join("") || "<div style='color:var(--dim)'>No projects yet — launch one above.</div>";
}

function renderCost(snap) {
  if (!snap) return;
  $("cost-in").textContent = snap.tokens_in;
  $("cost-out").textContent = snap.tokens_out;
  $("cost-usd").textContent = "$" + (snap.total_usd || 0).toFixed(4);
}

async function approveGate(pid, gate) { await api("POST", `/api/projects/${pid}/approve/${gate}`); refresh(); }
async function viewFiles(pid) {
  const r = await api("GET", `/api/projects/${pid}/files`);
  alert("Project files:\n" + (r.files || []).map(f => `${f.path} (${f.size}B)`).join("\n"));
}
async function viewStandup(pid) {
  const r = await api("GET", `/api/projects/${pid}/standup`);
  alert("Standup:\n" + JSON.stringify(r, null, 2));
}
window.approveGate = approveGate;
window.viewFiles = viewFiles;
window.viewStandup = viewStandup;

async function refresh() {
  const [agents, projects, activity, cost] = await Promise.all([
    api("GET","/api/agents"),
    api("GET","/api/projects"),
    api("GET","/api/activity?limit=80"),
    api("GET","/api/cost"),
  ]);
  renderAgents(agents);
  renderProjects(projects);
  renderActivity(activity);
  renderGraph(activity, agents);
  renderCost(cost);
}

$("launch").addEventListener("click", async () => {
  const brief = $("brief").value.trim();
  const name = $("pname").value.trim() || "Untitled Project";
  const template = $("template").value;
  if (!brief) { $("reply").textContent = "Brief is required."; return; }
  $("reply").textContent = "Routing through ARIYA…";
  const res = await api("POST","/api/projects",{ name, brief, template });
  if (res.error) { $("reply").textContent = "Error: " + res.error; return; }
  $("reply").textContent = `Project ${res.project_id?.slice(0,8)} initiated → phase: ${res.phase}`;
  $("brief").value = ""; $("pname").value = "";
  refresh();
});

function connectWS() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/api/ws`);
  ws.onopen = () => { $("status").classList.add("live"); $("status").textContent = "● neural link active"; };
  ws.onclose = () => { $("status").classList.remove("live"); $("status").textContent = "disconnected"; setTimeout(connectWS, 2000); };
  ws.onmessage = () => refresh();
}

refresh();
setInterval(refresh, 4000);
connectWS();
