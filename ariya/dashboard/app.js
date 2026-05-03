const AGENTS = ["ARIYA","SCOUT","ARCHITECT","SENTINEL","FORGE-BE","FORGE-FE","PROBE","GUARDIAN","PHOENIX"];
const GATES = ["design","architecture","code","qa","deploy"];

const $ = (id) => document.getElementById(id);

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
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
      <div class="name">${p.name}</div>
      <div class="phase">phase: ${p.phase}</div>
      <div class="gates">${gates}</div>
    </div>`;
  }).join("") || "<div style='color:var(--dim)'>No projects yet — launch one above.</div>";
}

async function approveGate(pid, gate) {
  await api("POST", `/api/projects/${pid}/approve/${gate}`);
  refresh();
}
window.approveGate = approveGate;

async function refresh() {
  const [agents, projects, activity] = await Promise.all([
    api("GET","/api/agents"),
    api("GET","/api/projects"),
    api("GET","/api/activity?limit=80"),
  ]);
  renderAgents(agents);
  renderProjects(projects);
  renderActivity(activity);
}

$("launch").addEventListener("click", async () => {
  const brief = $("brief").value.trim();
  const name = $("pname").value.trim() || "Untitled Project";
  if (!brief) { $("reply").textContent = "Brief is required."; return; }
  $("reply").textContent = "Routing through ARIYA…";
  const res = await api("POST","/api/projects",{ name, brief });
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
