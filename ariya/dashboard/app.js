"use strict";

// ═══════════════════════════════════════════════════
//  ARIYA — Jarvis-style dashboard
// ═══════════════════════════════════════════════════

const TOKEN = localStorage.getItem("ariya_token") || "";
const $ = (id) => document.getElementById(id);

// ── API ──────────────────────────────────────────────
async function api(method, path, body) {
  const h = { "Content-Type": "application/json" };
  if (TOKEN) h.Authorization = `Bearer ${TOKEN}`;
  const r = await fetch(path, {
    method, headers: h,
    body: body ? JSON.stringify(body) : undefined,
  });
  return r.json();
}

// ══════════════════════════════════════════════════════
//  SOUND ENGINE  (Jarvis-style — all synthesised, no files)
// ══════════════════════════════════════════════════════
let actx = null;
function getACtx() {
  if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)();
  return actx;
}
function tone(freq, dur = 0.08, vol = 0.12, type = "sine", delay = 0) {
  try {
    const ctx = getACtx();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.connect(g); g.connect(ctx.destination);
    o.type = type; o.frequency.value = freq;
    const t = ctx.currentTime + delay;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(vol, t + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.start(t); o.stop(t + dur + 0.01);
  } catch (_) {}
}
const SFX = {
  boot:     () => { tone(220,0.15,0.1,"sine",0); tone(330,0.12,0.09,"sine",0.14); tone(440,0.18,0.12,"sine",0.26); tone(660,0.22,0.1,"sine",0.38); },
  receive:  () => { tone(880,0.06,0.08,"sine",0); tone(660,0.08,0.07,"sine",0.07); },
  send:     () => { tone(440,0.06,0.1,"sine",0); tone(660,0.08,0.1,"sine",0.06); },
  agent:    () => { tone(528,0.05,0.07,"triangle",0); },
  alert:    () => { tone(300,0.1,0.12,"sawtooth",0); tone(200,0.12,0.1,"sawtooth",0.12); },
  approve:  () => { tone(660,0.06,0.09,"sine",0); tone(880,0.1,0.1,"sine",0.07); tone(1100,0.12,0.09,"sine",0.16); },
  click:    () => tone(720,0.04,0.06,"sine"),
};

// ══════════════════════════════════════════════════════
//  TEXT-TO-SPEECH
// ══════════════════════════════════════════════════════
let ttsEnabled = true;
let ttsVoice = null;
function initTTS() {
  if (!window.speechSynthesis) return;
  const load = () => {
    const voices = speechSynthesis.getVoices();
    ttsVoice = (
      voices.find(v => v.name.toLowerCase().includes("google uk english male")) ||
      voices.find(v => v.name.toLowerCase().includes("samantha")) ||
      voices.find(v => v.lang === "en-GB") ||
      voices.find(v => v.lang.startsWith("en")) ||
      null
    );
  };
  speechSynthesis.onvoiceschanged = load;
  load();
}
function speak_tts(text) {
  if (!ttsEnabled || !window.speechSynthesis) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.slice(0, 280));
  u.voice = ttsVoice;
  u.pitch = 0.88; u.rate = 0.95; u.volume = 0.85;
  speechSynthesis.speak(u);
}
$("ttsToggle").addEventListener("click", () => {
  ttsEnabled = !ttsEnabled;
  $("ttsToggle").classList.toggle("muted", !ttsEnabled);
  $("ttsToggle").title = ttsEnabled ? "Voice on" : "Voice off";
  SFX.click();
});

// ══════════════════════════════════════════════════════
//  CLAP DETECTOR  (ambient microphone — always-on)
//
//  Clap = sharp transient: RMS spikes above threshold in
//  < 40 ms then drops. We look for two such spikes within
//  600 ms to confirm a "clap" (avoids false positives from
//  single thuds). On detection → ARIYA greets.
// ══════════════════════════════════════════════════════
let clapStream = null;
let lastClapTime = 0;
const CLAP_THRESHOLD = 0.18;   // RMS amplitude 0-1
const CLAP_WINDOW    = 600;    // ms between two spikes = double-clap (single clap fires on first)

async function startClapListener() {
  try {
    clapStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    const ctx   = getACtx();
    const src   = ctx.createMediaStreamSource(clapStream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    const buf = new Float32Array(analyser.fftSize);

    let triggered = false;
    function loop() {
      analyser.getFloatTimeDomainData(buf);
      let rms = 0;
      for (let i = 0; i < buf.length; i++) rms += buf[i] * buf[i];
      rms = Math.sqrt(rms / buf.length);

      if (rms > CLAP_THRESHOLD && !triggered) {
        triggered = true;
        const now = Date.now();
        if (now - lastClapTime < CLAP_WINDOW) {
          // second clap within window → fire greeting
          onClap();
        }
        lastClapTime = now;
        setTimeout(() => { triggered = false; }, 120);
      }
      requestAnimationFrame(loop);
    }
    loop();
  } catch (_) {
    // microphone denied or unavailable — silently skip
  }
}

function onClap() {
  SFX.approve();
  ariyaSay("Greetings, Sir.");
}

// ══════════════════════════════════════════════════════
//  SPEECH-TO-TEXT (microphone)
// ══════════════════════════════════════════════════════
let recognition = null;
let micActive = false;

function initSTT() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { $("micBtn").title = "Speech not supported in this browser"; return; }
  recognition = new SR();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onresult = (e) => {
    const transcript = [...e.results].map(r => r[0].transcript).join("");
    $("chatInput").value = transcript;
    if (e.results[e.results.length - 1].isFinal) {
      stopMic();
      if (transcript.trim()) submit(transcript.trim());
    }
  };
  recognition.onerror = () => stopMic();
  recognition.onend   = () => stopMic();
}

function startMic() {
  if (!recognition) return;
  micActive = true;
  $("micBtn").classList.add("recording");
  $("orb").classList.add("thinking");
  SFX.send();
  recognition.start();
}
function stopMic() {
  micActive = false;
  $("micBtn").classList.remove("recording");
  try { recognition?.stop(); } catch (_) {}
}

$("micBtn").addEventListener("click", () => {
  if (micActive) stopMic();
  else startMic();
});

// ══════════════════════════════════════════════════════
//  MESSAGES
// ══════════════════════════════════════════════════════
const msgs = $("messages");
function addMsg(text, role) {
  const d = document.createElement("div");
  d.className = `msg ${role}`;
  d.textContent = text;
  msgs.appendChild(d);
  msgs.scrollTop = msgs.scrollHeight;
  while (msgs.children.length > 60) msgs.removeChild(msgs.firstChild);
}

function ariyaSay(text) {
  $("orb").classList.add("speaking");
  setTimeout(() => $("orb").classList.remove("speaking"), 900);
  SFX.receive();
  addMsg(text, "ariya");
  speak_tts(text);
}

// ══════════════════════════════════════════════════════
//  CONSTELLATION
// ══════════════════════════════════════════════════════
const AGENT_NAMES = ["SCOUT","ARCHITECT","SENTINEL","FORGE-BE","FORGE-FE","PROBE","GUARDIAN","PHOENIX"];
const NODES = { ARIYA: null }; // filled after layout

function buildConstellation() {
  const svg = $("constellation");
  const W = svg.clientWidth || 560, H = svg.clientHeight || 560;
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const cx = W / 2, cy = H / 2;
  const r = Math.min(W, H) * 0.43;
  NODES["ARIYA"] = { x: cx, y: cy };
  AGENT_NAMES.forEach((id, i) => {
    const a = (i / AGENT_NAMES.length) * Math.PI * 2 - Math.PI / 2;
    NODES[id] = { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
  });
  // Draw static ring + node markers
  let h = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(95,216,255,0.06)" stroke-dasharray="3 8"/>`;
  h += `<g id="edges"></g>`;
  AGENT_NAMES.forEach(id => {
    const p = NODES[id];
    h += `<g class="cnode" data-id="${id}">
      <circle cx="${p.x}" cy="${p.y}" r="4" fill="rgba(95,216,255,0.15)" stroke="rgba(95,216,255,0.3)" stroke-width="1"/>
    </g>`;
  });
  svg.innerHTML = h;
}

function flashEdge(from, to, color = "rgba(95,216,255,0.9)") {
  const a = NODES[from], b = NODES[to];
  if (!a || !b) return;
  const svg = $("constellation");
  const ns = "http://www.w3.org/2000/svg";
  const line = document.createElementNS(ns, "line");
  line.setAttribute("x1", a.x); line.setAttribute("y1", a.y);
  line.setAttribute("x2", a.x); line.setAttribute("y2", a.y);
  line.setAttribute("stroke", color);
  line.setAttribute("stroke-width", "1.2");
  line.setAttribute("stroke-linecap", "round");
  svg.appendChild(line);

  const t0 = performance.now();
  const draw = () => {
    const k = Math.min(1, (performance.now() - t0) / 500);
    line.setAttribute("x2", a.x + (b.x - a.x) * k);
    line.setAttribute("y2", a.y + (b.y - a.y) * k);
    line.setAttribute("opacity", String(1 - k * 0.6));
    if (k < 1) requestAnimationFrame(draw);
    else setTimeout(() => line.remove(), 300);
  };
  requestAnimationFrame(draw);

  // Light up target node
  const node = svg.querySelector(`.cnode[data-id="${to}"] circle`);
  if (node) {
    node.setAttribute("fill", "rgba(95,216,255,0.8)");
    node.setAttribute("r", "7");
    setTimeout(() => { node.setAttribute("fill", "rgba(95,216,255,0.15)"); node.setAttribute("r", "4"); }, 700);
  }
}

// ══════════════════════════════════════════════════════
//  AGENT CUBES (right rail)
// ══════════════════════════════════════════════════════
const AGENT_ROLES = {
  "ARIYA":     "Orchestrator Brain",
  "SCOUT":     "Market Research & Design",
  "ARCHITECT": "Technical Specification",
  "SENTINEL":  "Code Review & Security",
  "FORGE-BE":  "Backend Development",
  "FORGE-FE":  "Frontend Development",
  "PROBE":     "Manual QA",
  "GUARDIAN":  "Automated Testing",
  "PHOENIX":   "Self-Healing & Bug Fix",
};
const AGENT_MODELS = {
  "ARIYA":     "claude-opus-4-7",
  "SCOUT":     "claude-sonnet-4-6",
  "ARCHITECT": "claude-opus-4-7",
  "SENTINEL":  "claude-opus-4-7",
  "FORGE-BE":  "claude-sonnet-4-6",
  "FORGE-FE":  "claude-sonnet-4-6",
  "PROBE":     "claude-sonnet-4-6",
  "GUARDIAN":  "claude-sonnet-4-6",
  "PHOENIX":   "claude-opus-4-7",
};

let agentSkills = {};
let openCube = null;

function buildCubes(agents, skills) {
  // Cache skills by agent
  skills.forEach(s => {
    agentSkills[s.agent_id] = agentSkills[s.agent_id] || [];
    if (!agentSkills[s.agent_id].find(x => x.skill_id === s.skill_id))
      agentSkills[s.agent_id].push(s);
  });

  const known = Object.fromEntries(agents.map(a => [a.agent_id, a]));
  const container = $("agentCubes");

  const allIds = ["ARIYA", ...AGENT_NAMES];
  allIds.forEach(id => {
    const a = known[id] || { status: "idle", current_task: "" };
    let cube = container.querySelector(`.cube[data-id="${id}"]`);
    if (!cube) {
      cube = document.createElement("div");
      cube.className = "cube";
      cube.dataset.id = id;
      cube.innerHTML = `
        <div class="cube-head">
          <div class="cube-dot"></div>
          <div class="cube-name">${id}</div>
        </div>
        <div class="cube-role">${AGENT_ROLES[id] || ""}</div>
        <div class="cube-task"></div>
        <div class="cube-detail">
          <div><b>Model</b> ${AGENT_MODELS[id] || "—"}</div>
          <div style="margin-top:6px"><b>Skills</b></div>
          <div class="cube-skills-list"></div>
        </div>`;
      cube.addEventListener("click", () => {
        SFX.click();
        if (openCube && openCube !== cube) openCube.classList.remove("open", "active");
        cube.classList.toggle("open");
        cube.classList.toggle("active", cube.classList.contains("open"));
        openCube = cube.classList.contains("open") ? cube : null;
      });
      container.appendChild(cube);
    }

    // Update live state
    cube.classList.toggle("processing", a.status === "processing");
    cube.querySelector(".cube-task").textContent = a.current_task || "—";

    // Skill chips (once)
    const skillsList = cube.querySelector(".cube-skills-list");
    if (skillsList && skillsList.childElementCount === 0) {
      (agentSkills[id] || []).forEach(s => {
        const chip = document.createElement("span");
        chip.className = "cube-skill";
        chip.textContent = s.name;
        skillsList.appendChild(chip);
      });
    }
  });
}

// ══════════════════════════════════════════════════════
//  SIGNAL NARRATION
// ══════════════════════════════════════════════════════
let lastSeen = 0;
const sigColors = {
  TASK: "rgba(95,216,255,0.85)",
  FEEDBACK: "rgba(255,166,77,0.85)",
  APPROVAL: "rgba(76,255,170,0.85)",
  ALERT: "rgba(255,107,107,0.85)",
  CONTRACT_UPDATE: "rgba(180,130,255,0.85)",
};

function narrate(s) {
  const col = sigColors[s.type] || "rgba(95,216,255,0.7)";
  flashEdge(s.from, s.to, col);
  SFX.agent();
  if (s.type === "APPROVAL") SFX.approve();
  if (s.type === "ALERT")    SFX.alert();
}

// ══════════════════════════════════════════════════════
//  INTEGRATIONS
// ══════════════════════════════════════════════════════
const INT_CONFIG = {
  git:     { label: "GIT", color: "#f05033", fields: [{ key:"repo", label:"Repository URL" }, { key:"token", label:"Personal Access Token" }] },
  clickup: { label: "CLICKUP", color: "#7b68ee", fields: [{ key:"team", label:"Team ID" }, { key:"token", label:"API Token" }] },
  ide:     { label: "IDE / CURSOR", color: "#00b4d8", fields: [{ key:"ws", label:"WebSocket endpoint", placeholder:"ws://localhost:3456" }] },
};

function dotConnected(id) {
  return !!localStorage.getItem(`int_${id}_token`) || !!localStorage.getItem(`int_${id}_ws`);
}

function refreshIntDots() {
  Object.keys(INT_CONFIG).forEach(id => {
    const el = $(`int-${id}`);
    if (!el) return;
    el.classList.toggle("connected", dotConnected(id));
  });
}

function openIntModal(intId) {
  const cfg = INT_CONFIG[intId];
  if (!cfg) return;
  $("intModalTitle").textContent = cfg.label;
  const body = $("intModalBody");
  body.innerHTML = cfg.fields.map(f => `
    <div class="int-field">
      <label>${f.label}</label>
      <input type="text" id="int_inp_${f.key}"
             value="${localStorage.getItem(`int_${intId}_${f.key}`) || ""}"
             placeholder="${f.placeholder || ""}"/>
    </div>`).join("") +
    `<button class="int-save" onclick="saveInt('${intId}')">CONNECT</button>
     <div class="int-status-line" id="intStatusLine"></div>`;
  $("intModal").classList.remove("hidden");
  SFX.click();
}
window.saveInt = function(intId) {
  const cfg = INT_CONFIG[intId];
  cfg.fields.forEach(f => {
    const val = document.getElementById(`int_inp_${f.key}`)?.value || "";
    localStorage.setItem(`int_${intId}_${f.key}`, val);
  });
  $("intStatusLine").className = "int-status-line ok";
  $("intStatusLine").textContent = "✓ Saved.";
  refreshIntDots();
  SFX.approve();
  const el = $(`int-${intId}`);
  if (el) el.classList.add("connected");
};

Object.keys(INT_CONFIG).forEach(id => {
  $(`int-${id}`)?.addEventListener("click", () => openIntModal(id));
});
$("intModalClose").addEventListener("click", () => $("intModal").classList.add("hidden"));
$("intModal").addEventListener("click", e => { if (e.target === $("intModal")) $("intModal").classList.add("hidden"); });

// ══════════════════════════════════════════════════════
//  COMMAND PROCESSING
// ══════════════════════════════════════════════════════
async function submit(text) {
  SFX.send();
  addMsg(text, "user");
  $("chatInput").value = "";
  $("orb").classList.add("thinking");

  const lower = text.toLowerCase().trim();

  // status / report
  if (lower === "status" || lower === "report" || lower === "מה המצב") {
    const [projects, cost] = await Promise.all([api("GET","/api/projects"), api("GET","/api/cost")]);
    const summary = `${projects.length} project(s) running. Spend: $${(cost.total_usd||0).toFixed(4)}.\n` +
      projects.slice(0,5).map(p=>`• ${p.name} — ${p.phase}`).join("\n");
    ariyaSay(summary);
    $("orb").classList.remove("thinking");
    return;
  }

  // approve <gate> [id]
  const approveMatch = lower.match(/^approve\s+(\w+)(?:\s+(\S+))?/);
  if (approveMatch) {
    const gate = approveMatch[1], pid_hint = approveMatch[2];
    const projects = await api("GET","/api/projects");
    const p = pid_hint
      ? projects.find(x => x.project_id.startsWith(pid_hint))
      : projects[0];
    if (!p) { ariyaSay("No matching project found."); $("orb").classList.remove("thinking"); return; }
    await api("POST", `/api/projects/${p.project_id}/approve/${gate}`);
    ariyaSay(`Gate "${gate}" approved on ${p.name}.`);
    SFX.approve();
    $("orb").classList.remove("thinking");
    return;
  }

  // treat as brief
  const name = text.split(/[.,\n]/)[0].slice(0, 48) || "New Project";
  ariyaSay("Acknowledged. Decomposing the brief and activating the agent network.");
  const res = await api("POST", "/api/projects", { name, brief: text });
  if (res.error) { ariyaSay("An error occurred: " + res.error); }
  else { ariyaSay(`Project ${res.project_id?.slice(0,8)} initiated — routing to SCOUT.`); }
  $("orb").classList.remove("thinking");
}

$("sendBtn").addEventListener("click", () => {
  const v = $("chatInput").value.trim();
  if (v) submit(v);
});
$("chatInput").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("sendBtn").click(); }
});
$("orb").addEventListener("click", () => $("chatInput").focus());

// ══════════════════════════════════════════════════════
//  POLLING + WEBSOCKET
// ══════════════════════════════════════════════════════
async function tick() {
  try {
    const [agents, activity, skills] = await Promise.all([
      api("GET","/api/agents"),
      api("GET","/api/activity?limit=200"),
      api("GET","/api/skills"),
    ]);
    buildCubes(agents, skills);
    const newOnes = activity.slice(lastSeen);
    lastSeen = activity.length;
    newOnes.forEach(narrate);
    const busy = agents.some(a => a.status === "processing");
    $("orb").classList.toggle("thinking", busy);
  } catch (_) {}
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  try {
    const ws = new WebSocket(`${proto}//${location.host}/api/ws`);
    ws.onopen  = () => $("wsStatus").classList.add("live");
    ws.onclose = () => { $("wsStatus").classList.remove("live"); setTimeout(connectWS, 2500); };
    ws.onmessage = () => tick();
  } catch (_) {}
}

// ══════════════════════════════════════════════════════
//  BOOT
// ══════════════════════════════════════════════════════
function boot() {
  buildConstellation();
  window.addEventListener("resize", () => { buildConstellation(); });
  initTTS();
  initSTT();
  startClapListener();
  refreshIntDots();
  SFX.boot();
  setTimeout(() => ariyaSay("ARIYA online. Neural network standing by. Speak your brief."), 600);
  tick();
  setInterval(tick, 3500);
  connectWS();
}
boot();
