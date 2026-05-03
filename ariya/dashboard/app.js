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
  if (!r.ok) {
    const err = new Error(`HTTP ${r.status} ${path}`);
    err.status = r.status; err.path = path;
    throw err;
  }
  return r.json();
}

// ══════════════════════════════════════════════════════
//  SOUND ENGINE  (Jarvis-style — all synthesised, no files)
// ══════════════════════════════════════════════════════
let actx = null;
function getACtx() {
  if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)();
  // Browsers suspend AudioContext until a user gesture — resume on every call
  if (actx.state === "suspended") actx.resume();
  return actx;
}
// Unlock audio on first user interaction, then play boot sound
let _audioUnlocked = false;
function unlockAudio() {
  if (_audioUnlocked) return;
  _audioUnlocked = true;
  getACtx();
  SFX.boot();
  document.removeEventListener("click", unlockAudio);
  document.removeEventListener("keydown", unlockAudio);
}
document.addEventListener("click", unlockAudio);
document.addEventListener("keydown", unlockAudio);
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

// Per-agent color identity (used by the neural mesh)
const AGENT_COLORS = {
  "ARIYA":     "#c2f0ff",
  "SCOUT":     "#ffd166",
  "ARCHITECT": "#b388ff",
  "SENTINEL":  "#ff9f43",
  "FORGE-BE":  "#4cffaa",
  "FORGE-FE":  "#ff6bd6",
  "PROBE":     "#5fb8ff",
  "GUARDIAN":  "#ff6b6b",
  "PHOENIX":   "#ffcc33",
};
function agentColor(id) { return AGENT_COLORS[id] || "#5fd8ff"; }
function hexToRgba(hex, a) {
  const h = hex.replace("#",""); const n = parseInt(h, 16);
  return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;
}

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
  // Draw static ring + colored node markers + labels
  let h = `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="rgba(95,216,255,0.05)" stroke-dasharray="2 10"/>`;
  AGENT_NAMES.forEach(id => {
    const p = NODES[id];
    const c = agentColor(id);
    const labelOffset = (p.y < cy - 4) ? -14 : 22;
    h += `<g class="cnode" data-id="${id}">
      <circle cx="${p.x}" cy="${p.y}" r="5" fill="${hexToRgba(c,0.25)}" stroke="${c}" stroke-width="1.2"/>
      <text x="${p.x}" y="${p.y + labelOffset}" text-anchor="middle"
            font-family="monospace" font-size="9" letter-spacing="2" fill="${hexToRgba(c,0.55)}">${id}</text>
    </g>`;
  });
  svg.innerHTML = h;

  buildMeshLegend();
  setupMeshCanvas();
}

function buildMeshLegend() {
  const lg = $("meshLegend");
  if (!lg) return;
  lg.innerHTML = ["ARIYA", ...AGENT_NAMES].map(id => {
    const c = agentColor(id);
    return `<div class="lg"><span class="lg-dot" style="background:${c};color:${c}"></span>${id}</div>`;
  }).join("");
}

// ══════════════════════════════════════════════════════
//  NEURAL MESH (canvas particle system)
// ══════════════════════════════════════════════════════
let _mesh = { ctx: null, w: 0, h: 0, particles: [], glows: [], synapses: [],
              lastResting: 0, lastScan: 0, lastChatter: 0 };

function setupMeshCanvas() {
  const cv = $("mesh"); if (!cv) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const rect = cv.getBoundingClientRect();
  cv.width  = Math.round(rect.width  * dpr);
  cv.height = Math.round(rect.height * dpr);
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  _mesh.ctx = ctx;
  _mesh.w = rect.width; _mesh.h = rect.height;

  // Pre-generate resting synapse fibers (subtle wandering lines through nodes)
  _mesh.synapses = [];
  const ids = ["ARIYA", ...AGENT_NAMES];
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      const a = NODES[ids[i]], b = NODES[ids[j]];
      if (!a || !b) continue;
      // Skip distant pairs (avoid hairball); keep ARIYA-* and adjacent pairs
      const isCenter = ids[i] === "ARIYA" || ids[j] === "ARIYA";
      if (!isCenter && Math.random() > 0.35) continue;
      _mesh.synapses.push({ a, b, phase: Math.random() * Math.PI * 2 });
    }
  }
  if (!_mesh._raf) {
    _mesh._raf = true;
    requestAnimationFrame(meshLoop);
  }
}

function spawnParticle(from, to, type = "TASK") {
  const a = NODES[from], b = NODES[to];
  if (!a || !b || !_mesh.ctx) return;
  const sender = agentColor(from);
  const receiver = agentColor(to);
  _mesh.particles.push({
    ax: a.x, ay: a.y, bx: b.x, by: b.y,
    t: 0, speed: 0.012 + Math.random() * 0.006,
    cFrom: sender, cTo: receiver, type,
    trail: [],
  });
  _mesh.glows.push({ x: a.x, y: a.y, t: 0, color: sender });
  _mesh.glows.push({ x: b.x, y: b.y, t: -0.4, color: receiver }); // arrives later
}

function meshLoop(ts) {
  const ctx = _mesh.ctx;
  if (!ctx) { requestAnimationFrame(meshLoop); return; }
  ctx.clearRect(0, 0, _mesh.w, _mesh.h);

  // 1) Resting synapse fibers — slow shimmer
  ctx.lineCap = "round";
  for (const s of _mesh.synapses) {
    const shimmer = 0.025 + 0.02 * Math.sin(ts * 0.0008 + s.phase);
    ctx.strokeStyle = `rgba(95,216,255,${shimmer.toFixed(3)})`;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(s.a.x, s.a.y);
    ctx.lineTo(s.b.x, s.b.y);
    ctx.stroke();
  }

  // 2) Resting pulse — random faint particle every ~600ms
  if (ts - _mesh.lastResting > 600) {
    _mesh.lastResting = ts;
    if (_mesh.synapses.length) {
      const s = _mesh.synapses[Math.floor(Math.random() * _mesh.synapses.length)];
      const aId = Object.keys(NODES).find(k => NODES[k] === s.a) || "ARIYA";
      const bId = Object.keys(NODES).find(k => NODES[k] === s.b) || "ARIYA";
      // direction randomized
      const reverse = Math.random() < 0.5;
      _mesh.particles.push({
        ax: reverse ? s.b.x : s.a.x, ay: reverse ? s.b.y : s.a.y,
        bx: reverse ? s.a.x : s.b.x, by: reverse ? s.a.y : s.b.y,
        t: 0, speed: 0.010 + Math.random() * 0.006,
        cFrom: agentColor(reverse ? bId : aId), cTo: agentColor(reverse ? aId : bId),
        type: "RESTING", trail: [], faint: true,
      });
    }
  }

  // 2b) ARIYA scan pulse — every ~4s emit a wave to ALL agents simultaneously
  if (ts - _mesh.lastScan > 4200) {
    _mesh.lastScan = ts;
    const ariya = NODES["ARIYA"];
    if (ariya) {
      AGENT_NAMES.forEach((id, i) => {
        const target = NODES[id];
        if (!target) return;
        // stagger slightly per agent
        setTimeout(() => {
          _mesh.particles.push({
            ax: ariya.x, ay: ariya.y, bx: target.x, by: target.y,
            t: 0, speed: 0.018,
            cFrom: agentColor("ARIYA"), cTo: agentColor(id),
            type: "SCAN", trail: [], scan: true,
          });
          _mesh.glows.push({ x: ariya.x, y: ariya.y, t: 0, color: agentColor("ARIYA") });
        }, i * 60);
      });
    }
  }

  // 2c) Inter-agent chatter — every ~900ms a medium particle between two non-ARIYA agents
  if (ts - _mesh.lastChatter > 900) {
    _mesh.lastChatter = ts;
    const a = AGENT_NAMES[Math.floor(Math.random() * AGENT_NAMES.length)];
    let b = AGENT_NAMES[Math.floor(Math.random() * AGENT_NAMES.length)];
    if (b === a) b = AGENT_NAMES[(AGENT_NAMES.indexOf(a) + 1) % AGENT_NAMES.length];
    const pa = NODES[a], pb = NODES[b];
    if (pa && pb) {
      _mesh.particles.push({
        ax: pa.x, ay: pa.y, bx: pb.x, by: pb.y,
        t: 0, speed: 0.014,
        cFrom: agentColor(a), cTo: agentColor(b),
        type: "CHATTER", trail: [],
      });
    }
  }

  // 3) Active particles
  _mesh.particles = _mesh.particles.filter(p => {
    p.t += p.speed;
    const k = p.t;
    const x = p.ax + (p.bx - p.ax) * k;
    const y = p.ay + (p.by - p.ay) * k;
    p.trail.push({ x, y });
    if (p.trail.length > 14) p.trail.shift();

    // Trail
    for (let i = 0; i < p.trail.length; i++) {
      const tp = p.trail[i];
      const ratio = i / p.trail.length;
      const fade = (p.faint ? 0.12 : 0.55) * ratio;
      ctx.fillStyle = blendColors(p.cFrom, p.cTo, ratio).replace(/[\d.]+\)$/, `${fade})`);
      ctx.beginPath();
      ctx.arc(tp.x, tp.y, p.faint ? 1.0 : 1.6 * ratio + 0.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Head
    if (!p.faint) {
      const headColor = blendColors(p.cFrom, p.cTo, k);
      const baseRadius = p.scan ? 3.4 : 2.6;
      ctx.shadowBlur = p.scan ? 18 : 12;
      ctx.shadowColor = headColor;
      ctx.fillStyle = headColor;
      ctx.beginPath(); ctx.arc(x, y, baseRadius, 0, Math.PI * 2); ctx.fill();
      ctx.shadowBlur = 0;
    } else {
      ctx.fillStyle = blendColors(p.cFrom, p.cTo, k).replace(/[\d.]+\)$/, "0.35)");
      ctx.beginPath(); ctx.arc(x, y, 1.4, 0, Math.PI * 2); ctx.fill();
    }

    return p.t < 1;
  });

  // 4) Node glow halos
  _mesh.glows = _mesh.glows.filter(g => {
    g.t += 0.04;
    if (g.t < 0) return true;
    const k = Math.min(1, g.t);
    const r = 8 + 18 * k;
    const a = (1 - k) * 0.7;
    ctx.strokeStyle = hexToRgba(g.color, a);
    ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(g.x, g.y, r, 0, Math.PI * 2); ctx.stroke();
    return g.t < 1;
  });

  requestAnimationFrame(meshLoop);
}

function blendColors(hex1, hex2, t) {
  const p = (h) => { const n = parseInt(h.replace("#",""),16); return [(n>>16)&255,(n>>8)&255,n&255]; };
  const a = p(hex1), b = p(hex2);
  const r = Math.round(a[0] + (b[0]-a[0])*t);
  const g = Math.round(a[1] + (b[1]-a[1])*t);
  const bl= Math.round(a[2] + (b[2]-a[2])*t);
  return `rgba(${r},${g},${bl},1)`;
}

window.addEventListener("resize", () => {
  buildConstellation();
});

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
let lastSeen = -1;   // -1 = "not yet initialized"; set to current length on first tick
const sigColors = {
  TASK: "rgba(95,216,255,0.85)",
  FEEDBACK: "rgba(255,166,77,0.85)",
  APPROVAL: "rgba(76,255,170,0.85)",
  ALERT: "rgba(255,107,107,0.85)",
  CONTRACT_UPDATE: "rgba(180,130,255,0.85)",
};

function narrate(s) {
  spawnParticle(s.from, s.to, s.type);
  SFX.agent();
  if (s.type === "APPROVAL") SFX.approve();
  if (s.type === "ALERT")    SFX.alert();
}

// ══════════════════════════════════════════════════════
//  INTEGRATIONS
// ══════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════
//  INTEGRATIONS  (OAuth 2.0 via popup + manual token fallback)
// ══════════════════════════════════════════════════════

let _intStatus = {};

async function loadIntegrationStatus() {
  try {
    _intStatus = await api("GET", "/api/integrations");
    $("int-git").classList.toggle("connected",     !!_intStatus.github?.connected);
    $("int-clickup").classList.toggle("connected", !!_intStatus.clickup?.connected);
    $("int-ide").classList.toggle("connected",     !!localStorage.getItem("int_ide_ws"));
  } catch (_) {}
}

function openIntModal(intId) {
  SFX.click();
  $("intModal").classList.remove("hidden");
  $("intModalTitle").textContent = { git: "GIT / GITHUB", clickup: "CLICKUP", ide: "IDE / CURSOR" }[intId] || intId.toUpperCase();
  const body = $("intModalBody");
  const st = _intStatus;

  if (intId === "git") {
    const connected = st.github?.connected;
    const oauthOk   = st.github?.oauth_configured;
    const ghUser    = connected ? `<div class="int-status-line ok" style="margin-bottom:10px">✓ Connected as <b>${st.github.user}</b></div>` : "";
    const repoList  = (st.github?.repos || []).map(r =>
      `<div style="font-size:11px;color:var(--dim);padding:2px 0">📁 ${r}</div>`).join("");

    const oauthBtn = oauthOk
      ? `<button class="int-save" onclick="oauthLogin('github')">${connected ? "↻ RE-CONNECT" : "CONNECT WITH GITHUB"}</button>`
      : `<div class="int-setup-guide">
          <div class="setup-title">Set up GitHub OAuth</div>
          <ol class="setup-steps">
            <li>Go to <b>github.com/settings/developers</b> → "OAuth Apps" → "New OAuth App"</li>
            <li>Callback URL: <code>http://127.0.0.1:9001/api/auth/github/callback</code></li>
            <li>Copy <b>Client ID</b> + <b>Client Secret</b> into your <code>.env</code> file</li>
            <li>Restart ARIYA — the button will activate</li>
          </ol>
          <div style="color:var(--dim);font-size:10px;margin-top:8px">Or skip OAuth and paste a Personal Access Token below ↓</div>
        </div>`;

    body.innerHTML = `
      ${ghUser}
      ${repoList ? `<div style="margin:4px 0;font-size:10px;letter-spacing:2px;color:var(--dim)">RECENT REPOS</div>${repoList}<div style="margin-top:12px"></div>` : ""}
      ${oauthBtn}
      <div class="int-divider">── or Personal Access Token ──</div>
      <div class="int-field">
        <label>TOKEN (ghp_...)</label>
        <input type="password" id="git_token_inp" placeholder="ghp_xxxxxxxxxxxx"/>
      </div>
      <button class="int-save" onclick="saveTokenManual('github','git_token_inp')">SAVE TOKEN</button>
      <div class="int-status-line" id="intStatusLine"></div>`;

  } else if (intId === "clickup") {
    const connected = st.clickup?.connected;
    const oauthOk   = st.clickup?.oauth_configured;
    const cuUser    = connected ? `<div class="int-status-line ok" style="margin-bottom:10px">✓ Connected as <b>${st.clickup.user}</b></div>` : "";
    const teams     = (st.clickup?.teams || []).map(t =>
      `<div style="font-size:11px;color:var(--dim);padding:2px 0">🏢 ${t}</div>`).join("");

    const oauthBtn = oauthOk
      ? `<button class="int-save" onclick="oauthLogin('clickup')">${connected ? "↻ RE-CONNECT" : "CONNECT WITH CLICKUP"}</button>`
      : `<div class="int-setup-guide">
          <div class="setup-title">Set up ClickUp OAuth</div>
          <ol class="setup-steps">
            <li>Go to <b>app.clickup.com/settings/apps</b> → "Create App"</li>
            <li>Redirect URL: <code>http://127.0.0.1:9001/api/auth/clickup/callback</code></li>
            <li>Copy <b>Client ID</b> + <b>Secret Key</b> into your <code>.env</code> file</li>
            <li>Restart ARIYA — the button will activate</li>
          </ol>
          <div style="color:var(--dim);font-size:10px;margin-top:8px">Or skip OAuth and paste your API Token below ↓</div>
        </div>`;

    body.innerHTML = `
      ${cuUser}
      ${teams ? `<div style="margin:4px 0;font-size:10px;letter-spacing:2px;color:var(--dim)">WORKSPACES</div>${teams}<div style="margin-top:12px"></div>` : ""}
      ${oauthBtn}
      <div class="int-divider">── or API Token ──</div>
      <div class="int-field">
        <label>TOKEN (pk_...)</label>
        <input type="password" id="cu_token_inp" placeholder="pk_xxxxxxxxxxxx"/>
      </div>
      <button class="int-save" onclick="saveTokenManual('clickup','cu_token_inp')">SAVE TOKEN</button>
      <div class="int-status-line" id="intStatusLine"></div>`;

  } else if (intId === "ide") {
    const saved = localStorage.getItem("int_ide_ws") || "";
    body.innerHTML = `
      <div class="int-field">
        <label>CURSOR / VS CODE WS ENDPOINT</label>
        <input type="text" id="ide_ws_inp" placeholder="ws://localhost:3456" value="${saved}"/>
      </div>
      <button class="int-save" onclick="saveIde()">CONNECT</button>
      <div class="int-status-line" id="intStatusLine"></div>
      <div style="margin-top:16px;font-size:10px;color:var(--dim);line-height:1.8">
        Install the ARIYA VS Code extension from <code>vscode-extension/</code>.<br>
        Set <b>ariya.endpoint</b> to <code>http://localhost:8765</code> in settings.
      </div>`;
  }
}

window.oauthLogin = function(provider) {
  const url = `/api/auth/${provider === "github" ? "github" : "clickup"}`;
  const popup = window.open(url, "ariya_oauth",
    "width=520,height=640,toolbar=no,menubar=no,scrollbars=yes,resizable=yes");
  window.addEventListener("message", async function handler(e) {
    if (e.data?.type === "oauth_success" && e.data.provider === provider) {
      window.removeEventListener("message", handler);
      SFX.approve();
      await loadIntegrationStatus();
      openIntModal({ github: "git", clickup: "clickup" }[provider] || provider);
      ariyaSay(`${provider} connected as ${e.data.user}.`);
    }
  });
};

window.saveTokenManual = async function(provider, inputId) {
  const token = document.getElementById(inputId)?.value || "";
  if (!token || token.startsWith("•")) return;
  // Post to a simple endpoint that stores it server-side
  try {
    await api("POST", `/api/integrations/${provider}/token`, { token });
    await loadIntegrationStatus();
    $("intStatusLine").className = "int-status-line ok";
    $("intStatusLine").textContent = "✓ Token saved.";
    SFX.approve();
  } catch (e) {
    $("intStatusLine").className = "int-status-line err";
    $("intStatusLine").textContent = "✗ Failed to save.";
  }
};

window.saveIde = function() {
  const ws = $("ide_ws_inp")?.value || "";
  localStorage.setItem("int_ide_ws", ws);
  $("int-ide").classList.toggle("connected", !!ws);
  $("intStatusLine").className = "int-status-line ok";
  $("intStatusLine").textContent = "✓ Saved.";
  SFX.approve();
};

$("int-git").addEventListener("click",     () => openIntModal("git"));
$("int-clickup").addEventListener("click", () => openIntModal("clickup"));
$("int-ide").addEventListener("click",     () => openIntModal("ide"));
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

  // Everything else: ask ARIYA's chat endpoint to classify + reply
  try {
    const r = await api("POST", "/api/chat", { text });
    if (r.intent === "project") {
      const name = text.split(/[.,\n]/)[0].slice(0, 48) || "New Project";
      ariyaSay(r.reply || "Acknowledged. Routing to SCOUT.");
      const res = await api("POST", "/api/projects", { name, brief: text });
      if (res.error) ariyaSay("An error occurred: " + res.error);
      else ariyaSay(`Project ${res.project_id?.slice(0,8)} initiated — agents engaging.`);
    } else {
      ariyaSay(r.reply || "Standing by.");
    }
  } catch (e) {
    if (e.status === 404) {
      const msg = "Backend is running OLD code (no /api/chat endpoint). Please RESTART the server: Ctrl+C then re-run uvicorn.";
      ariyaSay(msg);
      showToast("error", "Server outdated", "Restart uvicorn to load /api/chat", 8000);
    } else {
      ariyaSay("Brain offline: " + (e.message || e));
      showToast("error", "Chat error", e.message || String(e), 5000);
    }
  }
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

$("demoBtn").addEventListener("click", async () => {
  SFX.send();
  ariyaSay("Initiating live demo. Watch the agent network come alive.");
  const res = await api("POST", "/api/projects", {
    name: "Live Demo — SaaS Dashboard",
    brief: "Build a SaaS analytics dashboard for restaurant chains. React + TypeScript frontend, Node.js + Express backend, PostgreSQL database. Include auth, real-time charts, and order management.",
    template: "saas",
  });
  if (!res.error) ariyaSay(`Project ${res.project_id?.slice(0,8)} running — agents activating.`);
});

// ══════════════════════════════════════════════════════
//  POLLING + WEBSOCKET
// ══════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════
//  HUD / PHASE STRIP / TOASTS
// ══════════════════════════════════════════════════════
const PHASES = ["INTAKE","RESEARCH","ARCH","IMPL","REVIEW","QA","DELIVERY"];
const PHASE_MAP = {
  "INTAKE":"INTAKE","RESEARCH":"RESEARCH","SPEC":"ARCH","ARCH":"ARCH",
  "IMPL":"IMPL","BUILD":"IMPL","REVIEW":"REVIEW","QA":"QA",
  "DELIVERY":"DELIVERY","DELIVERED":"DELIVERY","DONE":"DELIVERY",
};
function buildPhaseStrip() {
  const el = $("phaseStrip");
  if (!el || el.childElementCount) return;
  PHASES.forEach((p, i) => {
    if (i > 0) {
      const sep = document.createElement("div"); sep.className = "phase-sep";
      el.appendChild(sep);
    }
    const step = document.createElement("div");
    step.className = "phase-step"; step.dataset.phase = p;
    step.innerHTML = `<span class="pdot"></span><span class="plabel">${p}</span>`;
    el.appendChild(step);
  });
}
function updatePhaseStrip(currentPhase) {
  const norm = PHASE_MAP[(currentPhase || "").toUpperCase()] || "";
  const idx = PHASES.indexOf(norm);
  document.querySelectorAll(".phase-step").forEach((step, i) => {
    step.classList.remove("done", "active");
    if (idx >= 0) {
      if (i < idx) step.classList.add("done");
      if (i === idx) step.classList.add("active");
    }
  });
}

function flashHud(id, value) {
  const el = $(id); if (!el) return;
  if (el.textContent !== String(value)) {
    el.textContent = value;
    el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash");
  }
}

let _signalTimes = [];
function recordSignalTimes(n) {
  const now = Date.now();
  for (let i = 0; i < n; i++) _signalTimes.push(now);
  // keep last 60s window
  const cutoff = now - 60000;
  _signalTimes = _signalTimes.filter(t => t >= cutoff);
}
function signalsPerMin() { return _signalTimes.length; }

function showToast(level, title, msg, ttl = 3500) {
  const stack = $("toastStack"); if (!stack) return;
  const t = document.createElement("div");
  t.className = `toast ${level}`;
  const icons = { success: "✓", warn: "!", error: "✕", info: "i" };
  t.innerHTML = `<div class="ticon">${icons[level] || "i"}</div>
    <div class="tbody"><div class="ttitle">${title}</div><div class="tmsg">${msg}</div></div>`;
  stack.appendChild(t);
  while (stack.children.length > 4) stack.firstChild.remove();
  setTimeout(() => {
    t.classList.add("hide");
    setTimeout(() => t.remove(), 360);
  }, ttl);
}

let _knownProjectIds = new Set();
let _knownDlqLen = 0;

async function tick() {
  try {
    const [agents, activity, skills, projects, costSnap, dlq] = await Promise.all([
      api("GET","/api/agents"),
      api("GET","/api/activity?limit=200"),
      api("GET","/api/skills"),
      api("GET","/api/projects"),
      api("GET","/api/cost"),
      api("GET","/api/dlq").catch(() => []),
    ]);
    buildCubes(agents, skills);

    // Mesh narration
    if (lastSeen === -1) { lastSeen = activity.length; }
    const newOnes = activity.slice(lastSeen);
    lastSeen = activity.length;
    newOnes.forEach(narrate);
    recordSignalTimes(newOnes.length);

    // Orb thinking state
    const activeCount = agents.filter(a => a.status === "processing").length;
    $("orb").classList.toggle("thinking", activeCount > 0);

    // HUD updates
    flashHud("hudProjects", projects.length);
    flashHud("hudAgents", `${activeCount} active`);
    flashHud("hudSignals", `${signalsPerMin()}/min`);
    flashHud("hudCost", `$${(costSnap.total_usd || 0).toFixed(4)}`);
    const latestProj = projects[projects.length - 1];
    flashHud("hudPhase", latestProj?.phase || "—");
    updatePhaseStrip(latestProj?.phase);

    // Toast — new project detected
    projects.forEach(p => {
      if (!_knownProjectIds.has(p.project_id)) {
        if (_knownProjectIds.size > 0) {
          // skip first-load population
          showToast("success", "Project initiated", `${p.name} → ${p.phase}`);
        }
        _knownProjectIds.add(p.project_id);
      }
    });

    // Toast — DLQ growth
    if (dlq.length > _knownDlqLen) {
      showToast("error", "Signal failure", `${dlq.length - _knownDlqLen} message(s) in DLQ`);
    }
    _knownDlqLen = dlq.length;

    // Toast — gate awaiting (phase ending in _AWAIT or _GATE)
    projects.forEach(p => {
      if (p.phase && /AWAIT|GATE|PENDING/i.test(p.phase) && !p._toastedGate) {
        showToast("warn", "Approval gate", `${p.name} awaiting ${p.phase}`);
        p._toastedGate = true;
      }
    });

  } catch (e) {
    // Network/server down → show one warning
    if (!window._netDown) {
      window._netDown = true;
      showToast("error", "Backend offline", "Reconnect retrying…", 6000);
    }
  }
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
  buildPhaseStrip();
  window.addEventListener("resize", () => { buildConstellation(); });
  initTTS();
  initSTT();
  startClapListener();
  loadIntegrationStatus();
  setTimeout(() => ariyaSay("ARIYA online. Neural network standing by. Speak your brief."), 600);
  tick();
  setInterval(tick, 3500);
  connectWS();
}
boot();
