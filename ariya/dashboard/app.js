const AGENTS = ["SCOUT","ARCHITECT","SENTINEL","FORGE-BE","FORGE-FE","PROBE","GUARDIAN","PHOENIX"];
const GATES = ["design","architecture","code","qa","deploy"];
const TOKEN = localStorage.getItem("ariya_token") || "";

const $ = (id) => document.getElementById(id);
const orb = () => document.querySelector(".orb");

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (TOKEN) opts.headers.Authorization = `Bearer ${TOKEN}`;
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  return r.json();
}

// ─── Conversation ───────────────────────────────────────────
let lastSeenSignal = 0;
const conv = $("conv");

function speak(text, who = "ariya") {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  div.textContent = text;
  conv.appendChild(div);
  conv.scrollTop = conv.scrollHeight;
  if (who === "ariya") {
    orb().classList.add("speaking");
    setTimeout(() => orb().classList.remove("speaking"), 700);
  }
  // keep last 30
  while (conv.children.length > 40) conv.removeChild(conv.firstChild);
}

function event(html) {
  const div = document.createElement("div");
  div.className = "msg event";
  div.innerHTML = html;
  conv.appendChild(div);
  conv.scrollTop = conv.scrollHeight;
  while (conv.children.length > 40) conv.removeChild(conv.firstChild);
}

// ─── Constellation (SVG) ────────────────────────────────────
const NODES = {};
function buildConstellation() {
  const svg = $("constellation");
  const W = svg.clientWidth || 600, H = svg.clientHeight || 600;
  const cx = W / 2, cy = H / 2;
  const r = Math.min(W, H) * 0.42;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  // ARIYA at center (invisible — represented by the orb DOM element)
  NODES["ARIYA"] = { x: cx, y: cy };
  AGENTS.forEach((id, i) => {
    const ang = (i / AGENTS.length) * Math.PI * 2 - Math.PI / 2;
    NODES[id] = { x: cx + r * Math.cos(ang), y: cy + r * Math.sin(ang) };
  });

  let html = "";
  // halo ring
  html += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(95,220,255,0.07)" stroke-dasharray="2 6"/>`;
  // edges placeholder
  html += `<g id="edges"></g>`;
  // nodes
  for (const id of AGENTS) {
    const p = NODES[id];
    html += `<g class="node" data-id="${id}">
      <circle cx="${p.x}" cy="${p.y}" r="6" fill="rgba(95,220,255,0.18)" stroke="rgba(95,220,255,0.4)"/>
      <text x="${p.x}" y="${p.y + 22}" text-anchor="middle" fill="rgba(216,238,248,0.45)"
            font-size="10" letter-spacing="1.5">${id}</text>
    </g>`;
  }
  svg.innerHTML = html;
}

function flashEdge(from, to) {
  const a = NODES[from], b = NODES[to];
  if (!a || !b) return;
  const svg = $("constellation");
  const ns = "http://www.w3.org/2000/svg";
  const line = document.createElementNS(ns, "line");
  line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
  line.setAttribute("x2", a.x); line.setAttribute("y2", a.y);
  line.setAttribute("stroke", "rgba(95,220,255,0.85)");
  line.setAttribute("stroke-width", "1.5");
  line.setAttribute("stroke-linecap", "round");
  svg.appendChild(line);
  // animate the line drawing
  const start = performance.now();
  const dur = 600;
  function step(t) {
    const k = Math.min(1, (t - start) / dur);
    line.setAttribute("x2", a.x + (b.x - a.x) * k);
    line.setAttribute("y2", a.y + (b.y - a.y) * k);
    line.setAttribute("opacity", String(1 - k * 0.7));
    if (k < 1) requestAnimationFrame(step);
    else setTimeout(() => line.remove(), 400);
  }
  requestAnimationFrame(step);

  // briefly light up the target node
  const target = svg.querySelector(`g.node[data-id="${to}"] circle`);
  if (target) {
    target.setAttribute("fill", "rgba(182,244,255,0.9)");
    target.setAttribute("r", "9");
    setTimeout(() => {
      target.setAttribute("fill", "rgba(95,220,255,0.18)");
      target.setAttribute("r", "6");
    }, 700);
  }
}

function updateNodeStatuses(agents) {
  const known = Object.fromEntries(agents.map(a => [a.agent_id, a]));
  const svg = $("constellation");
  for (const id of AGENTS) {
    const target = svg.querySelector(`g.node[data-id="${id}"] circle`);
    if (!target) continue;
    if (known[id]?.status === "processing") {
      target.setAttribute("stroke", "rgba(182,244,255,1)");
      target.setAttribute("fill", "rgba(95,220,255,0.4)");
    } else {
      target.setAttribute("stroke", "rgba(95,220,255,0.4)");
      target.setAttribute("fill", "rgba(95,220,255,0.18)");
    }
  }
}

// ─── Polling ────────────────────────────────────────────────
async function tick() {
  try {
    const [agents, activity, projects, cost] = await Promise.all([
      api("GET","/api/agents"),
      api("GET","/api/activity?limit=120"),
      api("GET","/api/projects"),
      api("GET","/api/cost"),
    ]);

    updateNodeStatuses(agents);

    // Flash edges + narrate each new signal
    const newOnes = activity.slice(lastSeenSignal);
    lastSeenSignal = activity.length;
    for (const s of newOnes) {
      flashEdge(s.from, s.to);
      narrate(s);
    }

    // Update drawer panes
    renderDrawer(agents, activity, projects, cost);

    // Reflect "thinking" on the orb when any agent is processing
    const busy = agents.some(a => a.status === "processing");
    orb().classList.toggle("thinking", busy);
  } catch (e) { /* silent */ }
}

function narrate(s) {
  if (s.from === "ARIYA" && s.type === "TASK") {
    event(`<b>${s.from}</b> → ${s.to}  ·  ${s.title || s.type}`);
  } else if (s.type === "APPROVAL") {
    event(`<b>${s.from}</b> approved → ${s.to}  ·  ${s.title || ""}`);
  } else if (s.type === "FEEDBACK") {
    event(`<b>${s.from}</b> requested changes → ${s.to}`);
  } else if (s.type === "ALERT") {
    event(`<b>${s.from}</b> ALERT → ${s.to}`);
  } else if (s.type === "CONTRACT_UPDATE") {
    event(`contract sync: <b>${s.from}</b> → ${s.to}`);
  } else {
    event(`${s.from} → ${s.to}  ·  ${s.title || s.type}`);
  }
}

// ─── Drawer ─────────────────────────────────────────────────
function renderDrawer(agents, activity, projects, cost) {
  $("pane-agents").innerHTML = agents.map(a =>
    `<div class="agent-row">
      <span class="name">${a.agent_id}</span>
      <span class="status-tag ${a.status}">${a.status}</span>
      <div style="color:var(--dim);font-size:11px;margin-top:2px">${a.current_task || "—"}</div>
    </div>`
  ).join("") || "<div style='color:var(--dim)'>no agents online</div>";

  $("pane-signals").innerHTML = activity.slice(-50).reverse().map(s =>
    `<div class="signal-row">
      <span>${(s.t||"").substr(11,8)}</span>
      <span class="from">${s.from}</span> →
      <span class="to">${s.to}</span>
      &nbsp;<span style="color:var(--warn)">${s.type}</span>
      &nbsp;${s.title || ""}
    </div>`
  ).join("") || "<div style='color:var(--dim)'>no signals yet</div>";

  $("pane-projects").innerHTML = projects.map(p => {
    const ap = p.approvals || {};
    const gates = GATES.map(g =>
      `<button class="gate-btn ${ap[g] ? "approved" : ""}"
               onclick="approveGate('${p.project_id}','${g}')">${g}</button>`
    ).join("");
    return `<div class="project-row">
      <div class="pname">${p.name}</div>
      <div class="phase">${p.phase}</div>
      <div class="gates">${gates}</div>
    </div>`;
  }).join("") || "<div style='color:var(--dim)'>no projects yet</div>";

  $("pane-cost").innerHTML = `
    <div class="cost-row">total <b style="color:var(--accent)">$${(cost.total_usd||0).toFixed(4)}</b></div>
    <div class="cost-row">tokens in: ${cost.tokens_in}</div>
    <div class="cost-row">tokens out: ${cost.tokens_out}</div>
    <div style="margin-top:12px;color:var(--dim);font-size:11px;letter-spacing:2px">BY AGENT</div>
    ${Object.entries(cost.by_agent || {}).map(([k,v]) =>
      `<div class="cost-row">${k} · <span style="color:var(--accent)">$${v.toFixed(4)}</span></div>`).join("")}
  `;
}

window.approveGate = async (pid, gate) => {
  await api("POST", `/api/projects/${pid}/approve/${gate}`);
  speak(`Gate "${gate}" approved.`);
};

// ─── Tabs ───────────────────────────────────────────────────
document.querySelectorAll(".drawer-tabs .tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".drawer-tabs .tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    $(`pane-${btn.dataset.tab}`).classList.add("active");
  });
});
$("openDrawer").onclick = () => $("drawer").classList.add("open");
$("closeDrawer").onclick = () => $("drawer").classList.remove("open");

// ─── Conversation entry ─────────────────────────────────────
async function handleUserInput(text) {
  $("hint").classList.add("hide");
  speak(text, "user");

  // Light intent parsing — anything that looks like a brief becomes a project.
  const lower = text.toLowerCase();
  if (lower.startsWith("approve ")) {
    // approve <gate> [<projectId>]
    const parts = text.split(/\s+/);
    const gate = parts[1];
    const projects = await api("GET", "/api/projects");
    const p = parts[2] ? projects.find(x => x.project_id.startsWith(parts[2])) : projects[0];
    if (!p) { speak("I don't see a matching project."); return; }
    await api("POST", `/api/projects/${p.project_id}/approve/${gate}`);
    speak(`Approved "${gate}" on ${p.name}.`);
    return;
  }
  if (lower === "status" || lower === "מה המצב" || lower === "report") {
    const projects = await api("GET","/api/projects");
    const cost = await api("GET","/api/cost");
    speak(
      `${projects.length} project(s) in flight.\n` +
      projects.slice(0,5).map(p => `• ${p.name} — ${p.phase}`).join("\n") +
      `\nSpend so far: $${(cost.total_usd||0).toFixed(4)}.`
    );
    return;
  }

  // Default: treat as a brief
  const guessName = text.split(/[.,\n]/)[0].slice(0, 40) || "New Project";
  orb().classList.add("thinking");
  speak("Acknowledged. Decomposing the brief and waking the agent network.");
  const res = await api("POST", "/api/projects", { name: guessName, brief: text });
  if (res.error) { speak("Something went wrong: " + res.error); return; }
  speak(`Project ${res.project_id.slice(0,8)} initiated. Routing to SCOUT now.`);
}

$("send").onclick = () => {
  const v = $("input").value.trim();
  if (!v) return;
  $("input").value = "";
  handleUserInput(v);
};
$("input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("send").click();
});

orb().addEventListener("click", () => $("input").focus());

// ─── WebSocket connection state ─────────────────────────────
function connectWS() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  try {
    const ws = new WebSocket(`${proto}//${location.host}/api/ws`);
    ws.onopen = () => $("status").classList.add("live");
    ws.onclose = () => { $("status").classList.remove("live"); setTimeout(connectWS, 2000); };
    ws.onmessage = () => tick();
  } catch (_) {}
}

// ─── Boot ───────────────────────────────────────────────────
function boot() {
  buildConstellation();
  window.addEventListener("resize", buildConstellation);
  speak("ARIYA online. Speak when ready.", "ariya");
  tick();
  setInterval(tick, 3000);
  connectWS();
}
boot();
