/* AI WorkDesk OS - Phase 10 personal utilities & working area.
   One file, ten independent page renderers:
   Timer/Alarm/Stopwatch , Calculator , Notepad & MB Memory ·
   Code Studio , Documents , Sheets , Slides , PDF , Media , Remote Device.
   All workspace state is persisted server-side under data/workspace/;
   timers/alarms use localStorage so they survive reloads. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function notify(title, body) {
    try {
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(title, { body });
      }
    } catch (e) { /* notifications optional */ }
  }
  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.frequency.value = 880; g.gain.value = 0.15;
      o.start(); o.stop(ctx.currentTime + 0.7);
    } catch (e) { /* audio optional */ }
  }

  /* ================= 1. Timer / Alarm / Stopwatch ================= */
  let timerMain = { total: 25 * 60, remain: 25 * 60, running: false, handle: null };
  let timerExtras = [];
  let timerExtraId = 0;
  let swHandle = null, swStart = 0, swElapsed = 0, swLaps = [];
  let alarmInterval = null;

  function fmt(sec) {
    sec = Math.max(0, Math.floor(sec));
    const h = String(Math.floor(sec / 3600)).padStart(2, "0");
    const m = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
    const s = String(sec % 60).padStart(2, "0");
    return `${h}:${m}:${s}`;
  }

  function renderTimer() {
    const tabs = $("timerTabs");
    if (!tabs) return;
    tabs.querySelectorAll(".p10-tab").forEach((b) =>
      b.addEventListener("click", () => {
        tabs.querySelectorAll(".p10-tab").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        renderTimerTab(b.dataset.t);
      }));
    renderTimerTab("timer");
  }

  function renderTimerTab(tab) {
    if (tab === "timer") renderTimerView();
    else if (tab === "alarm") renderAlarmView();
    else renderStopwatchView();
  }

  /* ---------- Timer view: SVG ring + presets + multi timers + focus ---------- */
  function renderTimerView() {
    const p = $("timerPanel");
    if (!p) return;
    const R = 92, C = Math.round(2 * Math.PI * R * 100) / 100;
    p.innerHTML = `
      <div class="t-grid">
        <div class="p10-card t-main-card">
          <div class="t-ring-wrap">
            <svg class="t-ring" viewBox="0 0 220 220"><defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#9fc3ff"/><stop offset="100%" stop-color="#c9a7e8"/></linearGradient></defs>
              <circle class="t-ring-bg" cx="110" cy="110" r="${R}"/>
              <circle class="t-ring-fg" id="tRingFg" cx="110" cy="110" r="${R}"/>
            </svg>
            <div class="t-ring-center">
              <div class="t-clock" id="tMainClock">${fmt(timerMain.remain)}</div>
              <div class="t-presets" id="tPresets">
                <button data-m="1">1m</button><button data-m="5">5m</button><button data-m="10">10m</button>
                <button data-m="15">15m</button><button data-m="25">25m</button><button data-m="45">45m</button>
              </div>
              <div class="t-min-row">
                <input id="tMainMin" type="number" min="1" max="600" value="${Math.round(timerMain.total / 60)}" title="minutes" />
                <span class="muted">min</span>
              </div>
              <div class="t-controls">
                <button class="btn-primary" id="tMainGo">▶ Start</button>
                <button class="btn-secondary" id="tMainReset">↺ Reset</button>
                <button class="btn-secondary" id="tFocusBtn" title="Fullscreen focus mode">⛶ Focus</button>
              </div>
            </div>
          </div>
        </div>
        <div class="p10-card t-extras-card">
          <div class="t-sub-title">MULTI-TIMERS <button class="btn-secondary btn-sm" id="tAddTimer">+ Add</button></div>
          <div id="tExtraList" class="t-extra-list"></div>
        </div>
      </div>`;
    const fg = $("tRingFg"), clock = $("tMainClock"), go = $("tMainGo");
    const render = () => {
      if (!clock) return;
      clock.textContent = fmt(timerMain.remain);
      fg.style.strokeDasharray = C;
      fg.style.strokeDashoffset = String(Math.round(C * (1 - (timerMain.total ? timerMain.remain / timerMain.total : 0)) * 100) / 100);
      go.textContent = timerMain.running ? "⏸ Pause" : "▶ Start";
    };
    const start = () => {
      if (timerMain.running) {
        clearInterval(timerMain.handle); timerMain.running = false; render(); return;
      }
      if (timerMain.remain <= 0) timerMain.remain = timerMain.total;
      timerMain.running = true;
      timerMain.handle = setInterval(() => {
        timerMain.remain = Math.max(0, timerMain.remain - 1);
        render();
        if (timerMain.remain <= 0) {
          clearInterval(timerMain.handle); timerMain.running = false;
          beep(); notify("Timer finished", "Countdown complete.");
          render();
        }
      }, 1000);
      render();
    };
    go.addEventListener("click", start);
    $("tMainReset").addEventListener("click", () => {
      clearInterval(timerMain.handle); timerMain.running = false;
      timerMain.remain = timerMain.total; render();
    });
    $("tPresets").querySelectorAll("[data-m]").forEach((b) => b.addEventListener("click", () => {
      timerMain.total = parseInt(b.dataset.m, 10) * 60; timerMain.remain = timerMain.total;
      const mi = $("tMainMin"); if (mi) mi.value = b.dataset.m;
      render();
    }));
    const mi = $("tMainMin");
    if (mi) mi.addEventListener("change", (e) => {
      const m = Math.max(1, parseInt(e.target.value, 10) || 1);
      timerMain.total = m * 60; timerMain.remain = m * 60; render();
    });

    /* focus fullscreen */
    $("tFocusBtn").addEventListener("click", () => {
      const ov = document.createElement("div");
      ov.className = "t-focus";
      ov.innerHTML = `
        <div class="t-focus-inner">
          <div class="t-focus-clock" id="tFocusClock">${clock.textContent}</div>
          <div class="t-focus-sub">${timerMain.running ? "running" : "paused"}</div>
          <div class="t-focus-controls">
            <button class="btn-primary" id="tFocusGo">${timerMain.running ? "⏸ Pause" : "▶ Start"}</button>
            <button class="btn-secondary" id="tFocusReset">↺ Reset</button>
            <button class="btn-danger" id="tFocusClose">✕ Exit</button>
          </div>
        </div>`;
      document.body.appendChild(ov);
      if (ov.requestFullscreen) ov.requestFullscreen().catch(() => {});
      const fc = $("tFocusClock"), fs = $("tFocusGo");
      const sync = () => {
        if (!document.body.contains(ov)) return;
        fc.textContent = clock.textContent;
        fs.textContent = timerMain.running ? "⏸ Pause" : "▶ Start";
      };
      const tick = setInterval(sync, 250);
      const close = () => {
        clearInterval(tick);
        if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
        if (document.body.contains(ov)) ov.remove();
      };
      $("tFocusGo").addEventListener("click", () => { go.click(); sync(); });
      $("tFocusReset").addEventListener("click", () => { $("tMainReset").click(); sync(); });
      $("tFocusClose").addEventListener("click", close);
      document.addEventListener("fullscreenchange", function h() {
        if (!document.fullscreenElement && document.body.contains(ov)) { close(); document.removeEventListener("fullscreenchange", h); }
      });
    });

    /* multi timers */
    const renderExtras = () => {
      const list = $("tExtraList");
      if (!list) return;
      list.innerHTML = timerExtras.length ? timerExtras.map((t) => `
        <div class="t-extra-row">
          <span class="t-extra-name">${esc(t.label)}</span>
          <span class="t-extra-clock ${t.remain <= 0 ? "t-done" : ""}">${fmt(t.remain)}</span>
          <button class="btn-secondary btn-sm" data-a="${t.id}">${t.running ? "⏸" : "▶"}</button>
          <button class="btn-danger btn-sm" data-d="${t.id}">✕</button>
        </div>`).join("")
        : `<div class="placeholder">No extra timers - add parallel countdowns (pomodoro + water break + stand up).</div>`;
      list.querySelectorAll("[data-a]").forEach((b) => b.addEventListener("click", () => {
        const t = timerExtras.find((x) => x.id === parseInt(b.dataset.a, 10));
        if (!t) return;
        if (t.running) { clearInterval(t.handle); t.running = false; }
        else {
          if (t.remain <= 0) t.remain = t.total;
          t.running = true;
          t.handle = setInterval(() => {
            t.remain = Math.max(0, t.remain - 1);
            renderExtras();
            if (t.remain <= 0) { clearInterval(t.handle); t.running = false; beep(); notify("Timer finished", t.label + " complete."); renderExtras(); }
          }, 1000);
        }
        renderExtras();
      }));
      list.querySelectorAll("[data-d]").forEach((b) => b.addEventListener("click", () => {
        const t = timerExtras.find((x) => x.id === parseInt(b.dataset.d, 10));
        if (!t) return;
        clearInterval(t.handle);
        timerExtras = timerExtras.filter((x) => x.id !== t.id);
        renderExtras();
      }));
    };
    $("tAddTimer").addEventListener("click", () => {
      const label = prompt("Timer label:", "Pomodoro");
      const minsS = prompt("Minutes:", "25");
      if (label === null || minsS === null) return;
      const mins = Math.max(1, parseInt(minsS, 10) || 1);
      timerExtras.push({ id: ++timerExtraId, label: label || "Timer", total: mins * 60, remain: mins * 60, running: false, handle: null });
      renderExtras();
    });
    renderExtras();
    render();
  }

  /* ---------- Alarm view ---------- */
  function renderAlarmView() {
    const p = $("timerPanel");
    if (!p) return;
    p.innerHTML = `
      <div class="p10-card">
        <div class="t-sub-title">SET ALARM</div>
        <div class="t-controls">
          <input id="alarmTime" type="time" value="08:00" />
          <input id="alarmLabel" type="text" placeholder="label (optional)" class="t-min-input" style="width:150px;" />
          <button class="btn-primary" id="alarmAddBtn">+ Add Alarm</button>
        </div>
        <div id="alarmList" class="t-extra-list"></div>
      </div>`;
    const alarms = JSON.parse(localStorage.getItem("wd_alarms") || "[]");
    const renderAlarms = () => {
      const list = $("alarmList");
      if (!list) return;
      list.innerHTML = alarms.length ? alarms.map((a, i) => `
        <div class="t-extra-row">
          <span class="t-extra-name">⏰ ${esc(a.time)}</span>
          <span class="t-extra-clock muted">${esc(a.label || "alarm")}</span>
          <button class="btn-secondary btn-sm" data-tg="${i}">${a.enabled === false ? "off" : "on"}</button>
          <button class="btn-danger btn-sm" data-i="${i}">✕</button>
        </div>`).join("")
        : `<div class="placeholder">No alarms. Add one - the app notifies you at that time.</div>`;
      list.querySelectorAll("[data-i]").forEach((b) => b.addEventListener("click", () => {
        alarms.splice(parseInt(b.dataset.i, 10), 1);
        localStorage.setItem("wd_alarms", JSON.stringify(alarms));
        renderAlarms();
      }));
      list.querySelectorAll("[data-tg]").forEach((b) => b.addEventListener("click", () => {
        const i = parseInt(b.dataset.tg, 10);
        alarms[i].enabled = alarms[i].enabled === false ? true : false;
        localStorage.setItem("wd_alarms", JSON.stringify(alarms));
        renderAlarms();
      }));
    };
    renderAlarms();
    $("alarmAddBtn").addEventListener("click", () => {
      const t = $("alarmTime").value, l = $("alarmLabel").value.trim();
      if (!t) return;
      alarms.push({ time: t, label: l || "alarm", enabled: true });
      localStorage.setItem("wd_alarms", JSON.stringify(alarms));
      $("alarmLabel").value = "";
      renderAlarms();
    });
    if (!alarmInterval) {
      alarmInterval = setInterval(() => {
        const now = new Date();
        const hm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
        const all = JSON.parse(localStorage.getItem("wd_alarms") || "[]");
        const due = all.filter((a) => a.enabled !== false && a.time === hm);
        if (due.length) {
          localStorage.setItem("wd_alarms", JSON.stringify(all.filter((a) => a.enabled === false || a.time !== hm)));
          beep(); notify("Alarm", `It's ${hm} - ${due[0].label || "alarm"} triggered.`);
          renderAlarms();
        }
      }, 15000);
    }
  }

  /* ---------- Stopwatch view ---------- */
  function renderStopwatchView() {
    const p = $("timerPanel");
    if (!p) return;
    p.innerHTML = `
      <div class="p10-card sw-card">
        <div class="sw-clock" id="swDisplay">00:00:00.0</div>
        <div class="t-controls">
          <button class="btn-primary" id="swStartBtn">Start</button>
          <button class="btn-secondary" id="swLapBtn">Lap</button>
          <button class="btn-secondary" id="swResetBtn">Reset</button>
        </div>
        <div id="swLaps" class="t-extra-list"></div>
      </div>`;
    const disp = $("swDisplay");
    const renderLaps = () => {
      const el = $("swLaps");
      if (!el) return;
      if (!swLaps.length) { el.innerHTML = `<div class="placeholder">Press Lap to record split times.</div>`; return; }
      const times = swLaps.map((l) => l.lap);
      const mn = Math.min(...times), mx = Math.max(...times);
      el.innerHTML = swLaps.map((l, i) => `
        <div class="t-extra-row">
          <span class="t-extra-name">Lap ${String(i + 1).padStart(2, "0")} ${l.lap === mn ? "🏆" : l.lap === mx ? "🐢" : ""}</span>
          <span class="t-extra-clock">${l.lap.toFixed(1)}s</span>
          <span class="muted" style="font-size:11px;">total ${l.total}</span>
        </div>`).join("");
    };
    const update = () => {
      const now = Date.now();
      swElapsed = (now - swStart) / 1000;
      const h = Math.floor(swElapsed / 3600), m = Math.floor((swElapsed % 3600) / 60), ss = swElapsed % 60;
      disp.textContent = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(Math.floor(ss)).padStart(2, "0")}.${Math.floor((ss % 1) * 10)}`;
    };
    $("swStartBtn").addEventListener("click", () => {
      if (swHandle) { clearInterval(swHandle); swHandle = null; $("swStartBtn").textContent = "Start"; return; }
      swStart = Date.now() - swElapsed * 1000;
      swHandle = setInterval(update, 100);
      $("swStartBtn").textContent = "Pause";
    });
    $("swLapBtn").addEventListener("click", () => {
      if (!swHandle) return;
      update();
      const prev = swLaps.length ? swLaps[swLaps.length - 1].totalSec : 0;
      swLaps.push({ lap: swElapsed - prev, total: disp.textContent, totalSec: swElapsed });
      renderLaps();
    });
    $("swResetBtn").addEventListener("click", () => {
      if (swHandle) { clearInterval(swHandle); swHandle = null; }
      swStart = 0; swElapsed = 0; swLaps = [];
      disp.textContent = "00:00:00.0";
      $("swStartBtn").textContent = "Start";
      renderLaps();
    });
    renderLaps();
  }

  /* ================= 2. Calculator ================= */
  const calcHistory = JSON.parse(localStorage.getItem("wd_calc_hist") || "[]");
  const CONV = {
    length: { name: "Length", units: { mm: 0.001, cm: 0.01, m: 1, km: 1000, inch: 0.0254, ft: 0.3048, mi: 1609.344 } },
    weight: { name: "Weight", units: { mg: 1e-6, g: 0.001, kg: 1, t: 1000, oz: 0.0283495, lb: 0.453592 } },
    temperature: { name: "Temperature", units: { C: "C", F: "F", K: "K" }, special: true },
    data: { name: "Data", units: { B: 1, KB: 1024, MB: 1024 ** 2, GB: 1024 ** 3, TB: 1024 ** 4 } },
  };
  const CURRENCY = { name: "Currency (approx)", units: { USD: 1, EUR: 0.92, CNY: 7.15, MYR: 4.45, SGD: 1.35, JPY: 149.5, GBP: 0.79, AUD: 1.53 } };

  function renderCalc() {
    const p = $("calcPanel");
    if (!p) return;
    p.innerHTML = `
      <div class="calc-layout">
        <div class="calc-box glassy">
          <div class="calc-display">
            <div id="calcExpr" class="calc-expr"></div>
            <div id="calcRes" class="calc-res">0</div>
          </div>
          <div class="calc-grid">
            <button data-k="C" class="calc-fn">C</button><button data-k="del" class="calc-fn">⌫</button>
            <button data-k="(" class="calc-op">(</button><button data-k=")" class="calc-op">)</button>
            <button data-k="7">7</button><button data-k="8">8</button><button data-k="9">9</button><button data-k="/" class="calc-op">÷</button>
            <button data-k="4">4</button><button data-k="5">5</button><button data-k="6">6</button><button data-k="*" class="calc-op">×</button>
            <button data-k="1">1</button><button data-k="2">2</button><button data-k="3">3</button><button data-k="-" class="calc-op">−</button>
            <button data-k="0">0</button><button data-k=".">.</button><button data-k="sqrt" class="calc-fn">√</button><button data-k="+" class="calc-op">+</button>
            <button data-k="sin" class="calc-fn">sin</button><button data-k="cos" class="calc-fn">cos</button><button data-k="tan" class="calc-fn">tan</button><button data-k="=" class="calc-eq">=</button>
          </div>
        </div>
        <div class="calc-side">
          <div class="p10-card">
            <div class="memory-panel-title">HISTORY</div>
            <div id="calcHist" class="calc-hist"></div>
          </div>
          <div class="p10-card">
            <div class="memory-panel-title">UNIT CONVERT</div>
            <div class="conv-row">
              <select id="convType" class="conv-sel">
                <option value="length">Length</option><option value="weight">Weight</option>
                <option value="temperature">Temperature</option><option value="data">Data</option>
                <option value="currency">Currency</option>
              </select>
            </div>
            <div class="conv-row">
              <input id="convIn" type="number" value="1" class="conv-in" />
              <select id="convFrom" class="conv-sel"></select>
            </div>
            <div class="conv-row">
              <span class="conv-arrow">↓</span>
            </div>
            <div class="conv-row">
              <div id="convOut" class="calc-res conv-out">=</div>
              <select id="convTo" class="conv-sel"></select>
            </div>
          </div>
        </div>
      </div>`;
    wireCalc();
  }

  function wireCalc() {
    const expr = $("calcExpr"), res = $("calcRes");
    let acc = "";
    const fmtRes = (n) => {
      if (typeof n !== "number" || !isFinite(n)) return String(n);
      return Number(n.toPrecision(12)).toLocaleString(undefined, { maximumFractionDigits: 10 });
    };
    const evalSafe = (src) => {
      const s = src
        .replace(/×/g, "*").replace(/÷/g, "/").replace(/−/g, "-")
        .replace(/√\s*\(/g, "Math.sqrt(").replace(/√/g, "Math.sqrt(")
        .replace(/sin\s*\(/g, "Math.sin(").replace(/cos\s*\(/g, "Math.cos(").replace(/tan\s*\(/g, "Math.tan(")
        .replace(/pi/g, "Math.PI");
      if (!/^[0-9+\-*/().,\sMath\.sqrtncostao ]*$/.test(s)) throw new Error("bad");
      return Function(`"use strict"; return (${s})`)();
    };
    const renderHist = () => {
      const el = $("calcHist");
      if (!el) return;
      el.innerHTML = calcHistory.length
        ? calcHistory.slice(-12).reverse().map((h, i) => `
            <div class="calc-hist-row" data-i="${calcHistory.length - 1 - i}" title="click to reuse">
              <span class="calc-hist-expr">${esc(h.expr)}</span>
              <span class="calc-hist-res">= ${esc(h.res)}</span>
            </div>`).join("")
        : `<div class="placeholder">No history yet.</div>`;
      el.querySelectorAll("[data-i]").forEach((r) => r.addEventListener("click", () => {
        const h = calcHistory[parseInt(r.dataset.i, 10)];
        if (h) { acc = h.expr; expr.textContent = h.expr; res.textContent = h.res; }
      }));
    };
    renderHist();
    const press = (k) => {
      if (k === "C") { acc = ""; expr.textContent = ""; res.textContent = "0"; return; }
      if (k === "del") { acc = acc.slice(0, -1); expr.textContent = acc; res.textContent = "0"; return; }
      if (k === "=") {
        try {
          const v = evalSafe(acc);
          res.textContent = fmtRes(v);
          calcHistory.push({ expr: acc, res: res.textContent, at: Date.now() });
          if (calcHistory.length > 50) calcHistory.splice(0, calcHistory.length - 50);
          localStorage.setItem("wd_calc_hist", JSON.stringify(calcHistory));
          renderHist();
          acc = String(v);
          expr.textContent = acc;
        } catch (e) { res.textContent = "…"; }
        return;
      }
      acc += k;
      expr.textContent = acc;
      try { res.textContent = fmtRes(evalSafe(acc)); } catch (e) { res.textContent = "0"; }
    };
    const panel = $("calcPanel");
    panel.querySelectorAll("[data-k]").forEach((b) => b.addEventListener("click", () => press(b.dataset.k)));
    document.addEventListener("keydown", function calcKey(e) {
      if (!$("calcPanel") || $("calcPanel").closest(".view").style.display === "none") return;
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      const k = e.key;
      if (/^[0-9+\-*/().]$/.test(k)) { press(k); e.preventDefault(); }
      else if (k === "Enter") { press("="); e.preventDefault(); }
      else if (k === "Backspace") { press("del"); e.preventDefault(); }
      else if (k === "Escape") { press("C"); e.preventDefault(); }
    });

    /* unit conversion */
    const convType = $("convType"), convIn = $("convIn"), convFrom = $("convFrom"), convTo = $("convTo"), convOut = $("convOut");
    const fill = () => {
      const t = convType.value;
      const table = t === "currency" ? CURRENCY : CONV[t];
      if (!table) return;
      convFrom.innerHTML = Object.keys(table.units).map((u) => `<option value="${u}">${u}</option>`).join("");
      convTo.innerHTML = convFrom.innerHTML;
      convTo.value = Object.keys(table.units)[1] || Object.keys(table.units)[0];
      convFrom.value = Object.keys(table.units)[0];
      conv();
    };
    const conv = () => {
      const t = convType.value;
      const v = parseFloat(convIn.value) || 0;
      const a = convFrom.value, b = convTo.value;
      let out;
      if (t === "temperature") {
        let c;
        if (a === "C") c = v; else if (a === "F") c = (v - 32) * 5 / 9; else c = v - 273.15;
        if (b === "C") out = c; else if (b === "F") out = c * 9 / 5 + 32; else out = c + 273.15;
      } else {
        const table = t === "currency" ? CURRENCY : CONV[t];
        const base = v * table.units[a];
        out = base / table.units[b];
      }
      convOut.textContent = "= " + Number(out.toPrecision(10)).toLocaleString(undefined, { maximumFractionDigits: 6 });
    };
    convType.addEventListener("change", fill);
    convIn.addEventListener("input", conv);
    convFrom.addEventListener("change", conv);
    convTo.addEventListener("change", conv);
    fill();
  }

  /* ================= 3. Notepad & MB Memory ================= */
  let curNote = null;

  async function renderNotesTab(tab) {
    const p = $("notesPanel");
    if (tab === "mb") {
      p.innerHTML = `<div class="placeholder">Loading Main Brain global memory...</div>`;
      try {
        const mem = await Api.getMemory();
        const g = mem.globalMemory || {};
        const entries = Object.entries(g);
        p.innerHTML = entries.length
          ? `<div class="p10-card">
               <div class="memory-panel-title">MAIN BRAIN GLOBAL MEMORY <span class="badge badge-os">learned preferences , settings , long-term</span></div>
               ${entries.map(([k, v]) => `<div class="mem-row"><span class="mem-key">${esc(k)}</span><span class="mem-val">${esc(typeof v === "string" ? v : JSON.stringify(v))}</span></div>`).join("")}
             </div>`
          : `<div class="placeholder">No global memory yet. Main Brain preferences appear here automatically.</div>`;
      } catch (e) {
        p.innerHTML = `<div class='error'>${esc(e.message)}</div>`;
      }
      return;
    }
    const notes = (await Api.getNotes("user")).notes || [];
    p.innerHTML = `
      <div id="notesLayout">
        <div id="notesList" class="ws-file-list">
          <button class="btn-primary ws-new-btn" id="noteNewBtn">+ New Note</button>
          ${notes.length ? notes.map((n) => `
            <div class="ws-file-row ${curNote === n.note_id ? "active" : ""}" data-id="${esc(n.note_id)}">
              <span class="note-title">${esc(n.title || "untitled")}</span>
              <span class="muted">${esc((n.updated_ts || "").slice(5, 16))}</span>
              <button class="btn-danger-ghost" data-del="${esc(n.note_id)}">✕</button>
            </div>`).join("") : "<div class='placeholder'>No notes yet.</div>"}
        </div>
        <div id="noteEditor">
          <input id="noteTitle" placeholder="Note title" value="${curNote ? esc((notes.find(n => n.note_id === curNote) || {}).title || "") : ""}" />
          <textarea id="noteBody" placeholder="Write your note...">${curNote ? esc((notes.find(n => n.note_id === curNote) || {}).content || "") : ""}</textarea>
          <button class="btn-primary" id="noteSaveBtn">Save Note</button>
        </div>
      </div>`;
    $("noteNewBtn").addEventListener("click", () => { curNote = null; renderNotesTab("user"); });
    $("noteSaveBtn").addEventListener("click", async () => {
      const title = $("noteTitle").value.trim() || "untitled";
      const content = $("noteBody").value;
      const r = await Api.saveNote({ note_id: curNote, section: "user", title, content });
      if (r.note_id) curNote = r.note_id;
      renderNotesTab("user");
    });
    $("notesList").querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        await Api.deleteNote(b.dataset.del);
        if (curNote === b.dataset.del) curNote = null;
        renderNotesTab("user");
      }));
    $("notesList").querySelectorAll("[data-id]").forEach((r) =>
      r.addEventListener("click", () => { curNote = r.dataset.id; renderNotesTab("user"); }));
  }


  /* ---- draggable split resize (persisted per page) ---- */
  function wireSplitResize(key) {
    const rz = document.querySelector(`.split-resizer[data-key="${key}"]`);
    if (!rz) return;
    const left = rz.nextElementSibling;
    const right = left ? left.nextElementSibling : null;
    if (!left || !right) return;
    const saved = localStorage.getItem(`ws_split_${key}`);
    if (saved) { left.style.width = saved + "px"; left.style.flexBasis = saved + "px"; }
    rz.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      rz.classList.add("dragging");
      const startX = ev.clientX;
      const startW = left.getBoundingClientRect().width;
      const move = (me) => {
        const w = Math.max(160, Math.min(560, startW + (me.clientX - startX)));
        left.style.width = w + "px";
        left.style.flexBasis = w + "px";
        localStorage.setItem(`ws_split_${key}`, String(Math.round(w)));
      };
      const up = () => {
        rz.classList.remove("dragging");
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
      };
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });
  }

/* ================= 5. Documents ================= */
  async function renderDocs() {
    wireSplitResize('docs');
    const files = await Api.getWorkspaceFiles();
    const docs = (files.files || []).filter((f) => f.path.startsWith("docs/"));
    $("docsFiles").innerHTML = `
      <div class="ws-file-title">DOCUMENTS</div>
      ${docs.map((f) => `<div class="ws-file-row" data-p="${esc(f.path)}"><span>${esc(f.path)}</span></div>`).join("") || "<div class='placeholder'>No documents yet.</div>"}`;
    $("docsFiles").querySelectorAll("[data-p]").forEach((r) =>
      r.addEventListener("click", async () => {
        $("docFilename").value = r.dataset.p;
        const d = await Api.readWorkspace(r.dataset.p);
        if (!d.error) $("docEditor").innerHTML = d.content;
      }));
    $("docSaveBtn").addEventListener("click", async () => {
      const path = $("docFilename").value.trim();
      const r = await Api.saveWorkspace(path, $("docEditor").innerHTML);
      if (r.ok) renderDocs();
    });
    $("docNewBtn").addEventListener("click", () => {
      $("docFilename").value = `docs/doc_${Date.now() % 10000}.html`;
      $("docEditor").innerHTML = "<h2>New document</h2><p>Start writing…</p>";
    });
    $("docToolbar").querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () => {
        const cmd = b.dataset.cmd;
        document.execCommand(cmd, false, b.dataset.val || null);
        $("docEditor").focus();
      }));
  }

  /* ================= 6. Sheets ================= */
  let sheetData = [["", "", ""], ["", "", ""], ["", "", ""]];

  function colName(i) {
    let s = "";
    while (i >= 0) { s = String.fromCharCode(65 + (i % 26)) + s; i = Math.floor(i / 26) - 1; }
    return s;
  }
  function cellRef(r, c) { return colName(c) + (r + 1); }

  function parseFormula(f, grid) {
    const m = /^(SUM|AVG)\(([A-Z]+)(\d+):([A-Z]+)(\d+)\)$/.exec(f.trim());
    if (m) {
      const c1 = m[2].charCodeAt(0) - 65, r1 = parseInt(m[3], 10) - 1;
      const c2 = m[4].charCodeAt(0) - 65, r2 = parseInt(m[5], 10) - 1;
      const vals = [];
      for (let r = r1; r <= r2; r++) for (let c = c1; c <= c2; c++) {
        const v = parseFloat(grid[r] && grid[r][c]);
        if (!isNaN(v)) vals.push(v);
      }
      if (m[1] === "SUM") return vals.reduce((a, b) => a + b, 0);
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0;
    }
    let src = f.replace(/[A-Z]+\d+/g, (ref) => {
      const c = ref.charCodeAt(0) - 65, r = parseInt(ref.slice(1), 10) - 1;
      const v = parseFloat(grid[r] && grid[r][c]);
      return isNaN(v) ? "0" : String(v);
    });
    if (!/^[0-9+\-*/().\s]*$/.test(src)) return null;
    try { return Function(`"use strict"; return (${src})`)(); } catch (e) { return null; }
  }

  function renderSheetGrid() {
    const g = $("sheetGrid");
    let html = '<table class="sheet-table"><thead><tr><th></th>';
    for (let c = 0; c < sheetData[0].length; c++) html += `<th>${colName(c)}</th>`;
    html += "</tr></thead><tbody>";
    for (let r = 0; r < sheetData.length; r++) {
      html += `<tr><th>${r + 1}</th>`;
      for (let c = 0; c < sheetData[0].length; c++) {
        const raw = sheetData[r][c] || "";
        const val = String(raw).startsWith("=") ? parseFormula(String(raw).slice(1), sheetData) : raw;
        const shown = val === null || val === undefined ? "#ERR" : String(val);
        html += `<td><input data-r="${r}" data-c="${c}" value="${esc(shown)}" ${String(raw).startsWith("=") ? "class='formula-cell'" : ""} /></td>`;
      }
      html += "</tr>";
    }
    html += "</tbody></table>";
    g.innerHTML = html;
    g.querySelectorAll("input").forEach((inp) =>
      inp.addEventListener("change", () => {
        const r = parseInt(inp.dataset.r, 10), c = parseInt(inp.dataset.c, 10);
        sheetData[r][c] = inp.value;
        renderSheetGrid();
      }));
    const st = $("sheetStatus");
    if (st) {
      let sum = 0, count = 0;
      sheetData.flat().forEach((v) => {
        const raw = String(v).startsWith("=") ? parseFormula(String(v).slice(1), sheetData) : v;
        const n = parseFloat(raw);
        if (!isNaN(n) && String(v).trim() !== "") { sum += n; count++; }
      });
      st.textContent = `Ready , ${sheetData.length} rows × ${sheetData[0].length} cols , Σ = ${sum.toLocaleString()} (${count} numeric)`;
    }
  }

  async function renderSheets() {
    wireSplitResize('sheets');
    const files = await Api.getWorkspaceFiles();
    const sheets = (files.files || []).filter((f) => f.path.startsWith("sheets/"));
    $("sheetsFiles").innerHTML = `
      <div class="ws-file-title">SHEETS</div>
      ${sheets.map((f) => `<div class="ws-file-row" data-p="${esc(f.path)}"><span>${esc(f.path)}</span></div>`).join("") || "<div class='placeholder'>No sheets yet.</div>"}`;
    $("sheetsFiles").querySelectorAll("[data-p]").forEach((r) =>
      r.addEventListener("click", async () => {
        $("sheetFilename").value = r.dataset.p;
        const d = await Api.readWorkspace(r.dataset.p);
        if (!d.error) {
          sheetData = d.content.trim()
            ? d.content.split("\n").map((ln) => ln.split(",").map((v) => v.trim()))
            : [["", "", ""]];
          renderSheetGrid();
        }
      }));
    $("sheetSaveBtn").addEventListener("click", async () => {
      const csv = sheetData.map((row) => row.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
      const r = await Api.saveWorkspace($("sheetFilename").value.trim(), csv);
      if (r.ok) renderSheets();
    });
    $("sheetAddRowBtn").addEventListener("click", () => { sheetData.push(Array(sheetData[0].length).fill("")); renderSheetGrid(); });
    $("sheetAddColBtn").addEventListener("click", () => { sheetData.forEach((r) => r.push("")); renderSheetGrid(); });
    renderSheetGrid();
  }

  /* ================= 7. Slides ================= */
  let deck = [{ title: "Slide 1", body: "Double-click to edit", color: "#8BC8EA" }];
  let slideIdx = 0;

  function renderSlideEditor() {
    const s = deck[slideIdx] || deck[0];
    $("slideEditor").innerHTML = `
      <div class="slide-editor-row">
        <span class="muted">Slide ${slideIdx + 1} / ${deck.length}</span>
        <select id="slideColor">
          ${["#8BC8EA", "#A3D5E8", "#9BBBF4", "#A2DDAA", "#F4B393", "#C9A7E8", "#1A2440"].map((c) => `<option value="${c}" ${s.color === c ? "selected" : ""}>${c}</option>`).join("")}
        </select>
        <button class="btn-secondary" id="slidePrevBtn">‹ Prev</button>
        <button class="btn-secondary" id="slideNextBtn">Next ›</button>
        <button class="btn-danger-ghost" id="slideDelBtn">Delete</button>
      </div>
      <div class="slide-canvas" style="background:${esc(s.color)}">
        <input id="slideTitle" class="slide-title-input" value="${esc(s.title)}" />
        <textarea id="slideBody" class="slide-body-input" placeholder="Body text...">${esc(s.body)}</textarea>
      </div>`;
    const read = () => { deck[slideIdx] = { title: $("slideTitle").value, body: $("slideBody").value, color: $("slideColor").value }; };
    $("slideTitle").addEventListener("input", read);
    $("slideBody").addEventListener("input", read);
    $("slideColor").addEventListener("change", () => { read(); renderSlideEditor(); });
    $("slidePrevBtn").addEventListener("click", () => { read(); slideIdx = Math.max(0, slideIdx - 1); renderSlideEditor(); });
    $("slideNextBtn").addEventListener("click", () => { read(); slideIdx = Math.min(deck.length - 1, slideIdx + 1); renderSlideEditor(); });
    $("slideDelBtn").addEventListener("click", () => {
      read();
      if (deck.length > 1) deck.splice(slideIdx, 1);
      slideIdx = Math.min(slideIdx, deck.length - 1);
      renderSlideEditor();
    });
  }

  async function renderSlides() {
    wireSplitResize('slides');
    const files = await Api.getWorkspaceFiles();
    const decks = (files.files || []).filter((f) => f.path.startsWith("slides/") && f.path.endsWith(".json"));
    $("slidesList").innerHTML = `
      <div class="ws-file-title">DECKS</div>
      ${decks.map((f) => `<div class="ws-file-row" data-p="${esc(f.path)}"><span>${esc(f.path)}</span></div>`).join("") || "<div class='placeholder'>No decks yet.</div>"}`;
    $("slidesList").querySelectorAll("[data-p]").forEach((r) =>
      r.addEventListener("click", async () => {
        $("slideFilename").value = r.dataset.p;
        const d = await Api.readWorkspace(r.dataset.p);
        if (!d.error) { deck = JSON.parse(d.content || "[]") || deck; slideIdx = 0; renderSlideEditor(); }
      }));
    $("slideSaveBtn").addEventListener("click", async () => {
      const cur = deck[slideIdx];
      if (cur) { cur.title = $("slideTitle") ? $("slideTitle").value : cur.title; cur.body = $("slideBody") ? $("slideBody").value : cur.body; cur.color = $("slideColor") ? $("slideColor").value : cur.color; }
      const r = await Api.saveWorkspace($("slideFilename").value.trim(), JSON.stringify(deck, null, 2));
      if (r.ok) renderSlides();
    });
    $("slideAddBtn").addEventListener("click", () => {
      deck.push({ title: `Slide ${deck.length + 1}`, body: "New slide", color: "#A3D5E8" });
      slideIdx = deck.length - 1;
      renderSlideEditor();
    });
    $("slidePreviewBtn").addEventListener("click", () => {
      const win = window.open("", "_blank");
      win.document.write(`<html><head><title>Deck Preview</title><style>body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#111}.slide{width:100vw;height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#1A2440;page-break-after:always}.slide h1{font-size:56px}.slide p{font-size:26px}</style></head><body>${deck.map((s) => `<div class="slide" style="background:${esc(s.color)}"><h1>${esc(s.title)}</h1><p>${esc(s.body).replace(/\n/g, "<br/>")}</p></div>`).join("")}<script>document.title="Deck Preview";window.print();</script></body></html>`);
      win.document.close();
    });
    const playBtn = $("slidePlayBtn");
    if (playBtn) playBtn.addEventListener("click", () => {
      const win = window.open("", "_blank");
      win.document.write(`<html><head><title>▶ Deck</title><style>body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#05070d;overflow:hidden}.slide{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#eaf2ff;opacity:0;transition:opacity .6s}.slide.on{opacity:1}.slide h1{font-size:60px;max-width:80vw;text-align:center}.slide p{font-size:28px;max-width:70vw;text-align:center}.nav{position:fixed;bottom:22px;left:0;right:0;display:flex;gap:14px;justify-content:center;z-index:9}.nav button{background:rgba(122,162,247,.18);color:#cfe3ff;border:1px solid rgba(122,162,247,.35);border-radius:10px;padding:10px 22px;font-size:15px;cursor:pointer}</style></head><body>${deck.map((s) => `<div class="slide" style="background:${esc(s.color)}"><h1>${esc(s.title)}</h1><p>${esc(s.body).replace(/\n/g, "<br/>")}</p></div>`).join("")}<div class="nav"><button onclick="mv(-1)">‹ Prev</button><button onclick="mv(1)">Next ›</button></div><script>let i=0;const ss=document.querySelectorAll('.slide');function show(){ss.forEach((s,n)=>s.classList.toggle('on',n===i));}function mv(d){i=(i+d+ss.length)%ss.length;show();}show();document.addEventListener('keydown',e=>{if(e.key==='ArrowRight')mv(1);if(e.key==='ArrowLeft')mv(-1);if(e.key===' ')mv(1);});</script></body></html>`);
      win.document.close();
    });
    const themes = $("slideThemes");
    if (themes) themes.querySelectorAll(".st-swatch").forEach((sw) =>
      sw.addEventListener("click", () => {
        if (deck[slideIdx]) deck[slideIdx].color = sw.dataset.bg;
        renderSlideEditor();
      }));
    renderSlideEditor();
  }

  /* ================= 8. PDF ================= */
  async function renderPdf() {
    const files = await Api.getWorkspaceFiles();
    const pdfs = (files.files || []).filter((f) => f.path.toLowerCase().endsWith(".pdf"));
    const el = $("pdfFiles");
    if (!el) return;
    el.innerHTML = `
      <div class="ws-file-title">PDF LIBRARY</div>
      ${pdfs.map((f) => `<div class="ws-file-row ${f.path === pdfState.path ? "active" : ""}" data-p="${esc(f.path)}"><span>${esc(f.path.split("/").pop())}</span><span class="muted">${(f.size / 1024).toFixed(0)} KB</span></div>`).join("") || "<div class='placeholder'>No PDFs yet. Upload one to open &amp; edit.</div>"}`;
    wirePdfButtons();
    wirePdfFsButtons();
    el.querySelectorAll("[data-p]").forEach((r) =>
      r.addEventListener("click", () => loadPdf(r.dataset.p)));
  }

  const pdfState = { path: "", doc: null, edits: {} };

  function mapPdfFont(f) {
    const clean = String(f || "").replace(/^[A-Z]{6}\+/, "").trim();
    const v = clean.toLowerCase();
    if (v.includes("times")) return '"Times New Roman", Times, serif';
    if (v.includes("courier")) return '"Courier New", Courier, monospace';
    if (v.includes("helvetica") || v.includes("arial")) return 'Helvetica, Arial, "Segoe UI", sans-serif';
    if (v.includes("simsun") || v.includes("song") || v.includes("ming")) return '"SimSun", "Songti SC", serif';
    if (v.includes("yahei") || v.includes("hei") || v.includes("kai") || v.includes("pingfang")) return '"Microsoft YaHei", "PingFang SC", sans-serif';
    if (v.includes("calibri")) return 'Calibri, "Segoe UI", sans-serif';
    if (v.includes("cambria")) return 'Cambria, Georgia, serif';
    if (v.includes("consolas") || v.includes("mono")) return 'Consolas, "Courier New", monospace';
    if (v.includes("segoe")) return '"Segoe UI", sans-serif';
    return clean || "sans-serif";
  }

  function ensurePdfjs() {
    if (!window.pdfjsLib) return false;
    if (!window.pdfjsLib.GlobalWorkerOptions.workerSrc) {
      window.pdfjsLib.GlobalWorkerOptions.workerSrc = "/vendor/pdf.worker.min.js";
    }
    return true;
  }

  async function loadPdf(path) {
    if (!ensurePdfjs()) {
      const st = $("pdfStatus");
      if (st) st.textContent = "PDF.js failed to load (network?)";
      return;
    }
    pdfState.path = path;
    pdfState.edits = {};
    if (pdfState.doc) { try { pdfState.doc.destroy().catch(() => {}); } catch (e) {} pdfState.doc = null; }
    const st = $("pdfStatus");
    if (st) st.textContent = "Loading " + path.split("/").pop() + "…";
    const pagesEl = $("pdfPages");
    if (!pagesEl) return;
    try {
      const resp = await fetch(Api.workspaceFileUrl(path));
      const buf = await resp.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: buf, isEvalSupported: false }).promise;
      pdfState.doc = pdf;
      pagesEl.innerHTML = "";
      await renderPdfDoc(pdf, pagesEl, 1.25);
      if (st) st.textContent = pdf.numPages + " page(s) , click any text to edit in place";
    } catch (e) {
      console.error("pdf load", e);
      if (st) st.textContent = "Failed: " + e.message;
      pagesEl.innerHTML = `<span class="error">Cannot load PDF: ${esc(e.message)}</span>`;
    }
  }

  async function renderPdfDoc(pdf, pagesEl, scale) {
    pagesEl.innerHTML = "";
    for (let n = 1; n <= pdf.numPages; n++) {
      const page = await pdf.getPage(n);
      const viewport = page.getViewport({ scale });
      const wrap = document.createElement("div");
      wrap.className = "pdf-page";
      wrap.style.width = viewport.width + "px";
      wrap.style.height = viewport.height + "px";
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      wrap.appendChild(canvas);
      const layer = document.createElement("div");
      layer.className = "pdf-text-layer";
      wrap.appendChild(layer);
      pagesEl.appendChild(wrap);
      await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
      const tc = await page.getTextContent();
      // Use PDF.js font metrics, baseline, rotation and horizontal scaling.
      layer.style.setProperty("--scale-factor", viewport.scale);
      const textDivs = [];
      await pdfjsLib.renderTextLayer({
        textContentSource: tc, container: layer, viewport, textDivs,
      }).promise;
      let textIndex = 0;
      tc.items.forEach((it, idx) => {
        if (typeof it.str !== "string") return;
        const span = textDivs[textIndex++];
        if (!span || !it.str.trim()) return;
        const saved = pdfState.edits[n + ":" + idx];
        span.className = "pdf-t";
        // Preserve the original mask when an edit is shorter or empty.
        span.style.minWidth = getComputedStyle(span).width;
        span.style.minHeight = getComputedStyle(span).fontSize;
        span.contentEditable = "true";
        span.removeAttribute("role");
        span.spellcheck = false;
        span.dataset.pn = n;
        span.dataset.idx = idx;
        span.dataset.orig = it.str;
        span.textContent = saved ? saved.text : it.str;
        span.classList.toggle("pdf-t-edited", !!saved);
        span.addEventListener("input", () => recordPdfEdit(n, idx, it, span));
      });
    }
  }

  function recordPdfEdit(pn, idx, it, span) {
    const k = pn + ":" + idx;
    span.classList.toggle("pdf-t-edited", span.textContent !== it.str);
    if (span.textContent === it.str) { delete pdfState.edits[k]; }
    else {
      pdfState.edits[k] = {
        page: pn,
        text: span.textContent,
        x: it.transform[4],
        y: it.transform[5],
        w: it.width || 1,
        h: it.height || Math.abs(it.transform[3]),
        fs: Math.abs(it.transform[3]),
      };
    }
    const st = $("pdfStatus");
    if (st) st.textContent = Object.keys(pdfState.edits).length + " edit(s) unsaved";
  }

  async function savePdfEdits(statusEl) {
    if (!pdfState.path) return;
    const n = Object.keys(pdfState.edits).length;
    const savePath = pdfState.path.replace(/\.pdf$/i, "") + ".edit.json";
    await Api.saveWorkspace(savePath, JSON.stringify({
      source: pdfState.path,
      edits: Object.values(pdfState.edits),
      savedAt: new Date().toISOString(),
    }, null, 2));
    const st = statusEl || $("pdfStatus");
    if (st) st.textContent = "Saved " + n + " edit(s) → " + savePath;
  }

  async function exportPdf(statusEl) {
    if (!pdfState.path) { const st = statusEl || $("pdfStatus"); if (st) st.textContent = "Open a PDF first"; return; }
    const n = Object.keys(pdfState.edits).length;
    if (!n) { const st = statusEl || $("pdfStatus"); if (st) st.textContent = "No edits to export"; return; }
    if (!window.PDFLib) { const st = statusEl || $("pdfStatus"); if (st) st.textContent = "pdf-lib failed to load (network?)"; return; }
    const st = statusEl || $("pdfStatus");
    if (st) st.textContent = "Exporting…";
    try {
      const resp = await fetch(Api.workspaceFileUrl(pdfState.path));
      const src = await resp.arrayBuffer();
      const pdfDoc = await PDFLib.PDFDocument.load(src);
      let font;
      try {
        const fb = await (await fetch(Api.fontSimheiUrl())).arrayBuffer();
        font = await pdfDoc.embedFont(fb);
      } catch (e) {
        font = await pdfDoc.embedFont(PDFLib.StandardFonts.Helvetica);
      }
      const byPage = {};
      Object.values(pdfState.edits).forEach((ed) => { (byPage[ed.page] = byPage[ed.page] || []).push(ed); });
      for (const pnStr of Object.keys(byPage)) {
        const pn = parseInt(pnStr, 10);
        const page = pdfDoc.getPage(pn - 1);
        byPage[pn].forEach((ed) => {
          const h = Math.abs(ed.h) * 1.35 + 2;
          page.drawRectangle({
            x: ed.x, y: ed.y - Math.abs(ed.h) * 1.15,
            width: ed.w + 1, height: h,
            color: PDFLib.rgb(1, 1, 1),
          });
          page.drawText(String(ed.text), {
            x: ed.x, y: ed.y - Math.abs(ed.h),
            size: Math.abs(ed.fs) || 12, font,
          });
        });
      }
      const out = await pdfDoc.save();
      const name = pdfState.path.split("/").pop().replace(/\.pdf$/i, "") + ".edited.pdf";
      const blob = new Blob([out], { type: "application/pdf" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      URL.revokeObjectURL(a.href);
      if (st) st.textContent = "Exported " + name + " (" + Math.round(out.length / 1024) + " KB)";
    } catch (e) {
      console.error("pdf export", e);
      if (st) st.textContent = "Export failed: " + e.message;
    }
  }

  const pdfFsState = { open: false, zoom: 1.4 };

  function renderPdfFs() {
    if (!pdfState.doc) return;
    const pages = $("pdfFsPages");
    if (!pages) return;
    renderPdfDoc(pdfState.doc, pages, pdfFsState.zoom).then(() => {
      const zv = $("pdfFsZoomVal");
      if (zv) zv.textContent = Math.round(pdfFsState.zoom * 100) + "%";
    });
  }

  function openPdfFs() {
    if (!pdfState.doc || pdfFsState.open) return;
    pdfFsState.open = true;
    const ov = $("pdfFsOverlay");
    if (!ov) return;
    ov.classList.remove("hidden");
    const nm = $("pdfFsName");
    if (nm) nm.textContent = pdfState.path.split("/").pop() + " \u00b7 " + pdfState.doc.numPages + " page(s)";
    if (ov.requestFullscreen) ov.requestFullscreen().catch(() => {});
    renderPdfFs();
  }

  function closePdfFs() {
    pdfFsState.open = false;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    const ov = $("pdfFsOverlay");
    if (ov) ov.classList.add("hidden");
    if (pdfState.path) loadPdf(pdfState.path);
  }

  function wirePdfFsButtons() {
    const full = $("pdfFullBtn");
    if (full && !full._w) {
      full._w = true;
      full.addEventListener("click", () => {
        if (!pdfState.doc) {
          const st = $("pdfStatus");
          if (st) st.textContent = "Open a PDF first";
          return;
        }
        openPdfFs();
      });
    }
    const close = $("pdfFsClose");
    if (close && !close._w) {
      close._w = true;
      close.addEventListener("click", closePdfFs);
    }
    const zin = $("pdfFsZoomIn"), zout = $("pdfFsZoomOut");
    const step = (d) => {
      pdfFsState.zoom = Math.min(2.6, Math.max(0.6, +(pdfFsState.zoom + d).toFixed(1)));
      renderPdfFs();
    };
    if (zin && !zin._w) { zin._w = true; zin.addEventListener("click", () => step(0.2)); }
    if (zout && !zout._w) { zout._w = true; zout.addEventListener("click", () => step(-0.2)); }
    const sv = $("pdfFsSave");
    if (sv && !sv._w) { sv._w = true; sv.addEventListener("click", () => savePdfEdits($("pdfFsStatus"))); }
    const ex = $("pdfFsExport");
    if (ex && !ex._w) { ex._w = true; ex.addEventListener("click", () => exportPdf($("pdfFsStatus"))); }
    document.addEventListener("fullscreenchange", () => {
      if (!document.fullscreenElement && pdfFsState.open) {
        pdfFsState.open = false;
        const ov = $("pdfFsOverlay");
        if (ov) ov.classList.add("hidden");
        if (pdfState.path) loadPdf(pdfState.path);
      }
    });
  }

  function wirePdfButtons() {
    const up = $("pdfUpload"), save = $("pdfSaveBtn"), ex = $("pdfExportBtn");
    if (!up || up._w) return;
    up._w = true;
    up.addEventListener("change", async () => {
      await Api.uploadWorkspace(up.files, "pdf");
      up.value = "";
      renderPdf();
    });
    if (save) save.addEventListener("click", savePdfEdits);
    if (ex) ex.addEventListener("click", exportPdf);
  }

async   function srtTime(t) {
    const m = t.trim().match(/(\d+):(\d+):(\d+)[,.](\d+)/);
    if (!m) return 0;
    return (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + (+m[4]) / 1000;
  }
  function parseSrt(txt) {
    const out = [];
    for (const block of txt.split(/\r?\n\r?\n/)) {
      const lines = block.split(/\r?\n/);
      const tm = lines.find((l) => l.includes("-->"));
      if (!tm) continue;
      const parts = tm.split("-->");
      const text = lines.slice(lines.indexOf(tm) + 1).join(" ").trim();
      if (text) out.push({ t1: srtTime(parts[0]), t2: srtTime(parts[1]), text });
    }
    return out;
  }
  function parseLrc(txt) {
    const out = [];
    for (const line of txt.split(/\r?\n/)) {
      const m = line.match(/\[(\d+):(\d+)(?:[.:](\d+))?\](.*)/);
      if (m) out.push({ t1: (+m[1]) * 60 + (+m[2]) + (+(m[3] || 0)) / 100, t2: 1e12, text: m[4].trim() });
    }
    return out;
  }

async function renderMediaTab(filter) {
    const p = $("mediaPanel");
    if (!p) return;
    const TYPE_RE = {
      image: /\.(png|jpe?g|gif|webp|svg|bmp)$/i,
      audio: /\.(mp3|wav|ogg|m4a|aac|flac)$/i,
      video: /\.(mp4|webm|mov|avi|mkv|m4v)$/i,
    };
    const typeOf = (f) => TYPE_RE.image.test(f.path) ? "image" : TYPE_RE.audio.test(f.path) ? "audio" : TYPE_RE.video.test(f.path) ? "video" : null;
    const files = await Api.getWorkspaceFiles();
    const all = (files.files || []).map((f) => ({ ...f, type: typeOf(f) })).filter((f) => f.type);
    const items = all;
    const persistentPlayer = $("mediaPlayer");
    const IMG = { image: '<svg class="ico-svg" aria-hidden="true"><use href="#i-monitor"/></svg>', audio: '<svg class="ico-svg" aria-hidden="true"><use href="#i-activity"/></svg>', video: '<svg class="ico-svg" aria-hidden="true"><use href="#i-video"/></svg>' };
    if (typeof window.mpQueue === "undefined") window.mpQueue = { items: [], idx: -1, loop: false, shuffle: false };
    if (!Number.isInteger(window.mpQueue.idx)) window.mpQueue.idx = -1;
    if (typeof window.mpSubs === "undefined") window.mpSubs = null;

    const renderQueue = () => {
      const bar = $("mpQueueBar");
      if (!bar) return;
      const q = window.mpQueue;
      bar.innerHTML = q.items.length
        ? `<span class="muted" style="font-size:11px;">QUEUE</span>` + q.items.map((it, i) => `
            <span class="mp-qitem ${i === q.idx ? "playing" : ""}" data-q="${i}" title="${esc(it.name)}">
              ${IMG[it.type]} ${esc(it.name.length > 24 ? it.name.slice(0, 24) + "…" : it.name)}
              <span class="mp-qx" data-qx="${i}">✕</span>
            </span>`).join("") + `<span class="muted" style="font-size:11px;">${q.loop ? "🔁" : ""}${q.shuffle ? "🔀" : ""}</span>`
        : `<span class="muted" style="font-size:11px;">Queue empty - use ＋ on a card to queue it after the current item.</span>`;
      bar.querySelectorAll(".mp-qitem[data-q]").forEach((el) => el.addEventListener("click", (e) => {
        if (e.target.classList.contains("mp-qx")) return;
        const i = parseInt(el.dataset.q, 10);
        window.mpQueue.idx = i;
        const it = window.mpQueue.items[i];
        loadToPlayer(it.path, it.type, it.name);
      }));
      bar.querySelectorAll(".mp-qx").forEach((el) => el.addEventListener("click", () => {
        const i = parseInt(el.dataset.qx, 10);
        window.mpQueue.items.splice(i, 1);
        if (window.mpQueue.idx > i) window.mpQueue.idx--;
        else if (window.mpQueue.idx === i) window.mpQueue.idx = -1;
        renderQueue();
      }));
    };

    // Keep the existing player and its listeners alive when the library refreshes.
    const resumePlayback = mpState.media && !mpState.media.paused;
    if (persistentPlayer && p.contains(persistentPlayer)) persistentPlayer.remove();
    p.innerHTML = `
      <div class="media-body" id="mediaBody">
        <div class="media-stage-wrap" id="mediaStageWrap">
          <div class="mp-sub" id="mpSubLine"></div>
          <div class="media-stage-note"><span>YOUR VIEWING ROOM</span><span>One file, your full attention.</span></div>
        </div>
        <button class="media-library-scrim" id="mediaLibraryScrim" aria-label="Close media library" hidden></button>
        <aside class="media-library" id="mediaLibrary" aria-labelledby="mediaLibraryTitle">
      <div class="media-library-heading"><div><span class="media-library-eyebrow">COLLECTION</span><h3 id="mediaLibraryTitle">Your library <span>${all.length}</span></h3></div><button id="mediaLibraryClose" class="icon-btn" aria-label="Collapse media library">→</button></div>
      <label class="media-search"><svg class="ico-svg" aria-hidden="true"><use href="#i-search"/></svg><input id="mediaSearch" type="search" placeholder="Find a file…" aria-label="Search media files"></label>
      <div class="media-top">
        <div class="media-chips">
          ${["all", "image", "video", "audio"].map((k) => `<button class="media-chip ${filter === k ? "active" : ""}" aria-pressed="${filter === k}" data-f="${k}">${k === "all" ? "All" : k[0].toUpperCase() + k.slice(1)}</button>`).join("")}
        </div>
      </div>
        <div id="mediaGrid" class="media-grid media-masonry">
          ${items.map((f) => {
            const nm = f.path.split("/").pop();
            const kb = f.size ? Math.max(1, Math.round(f.size / 1024)) : 0;
            const cover = f.type === "image"
              ? `<img src="${Api.workspaceFileUrl(f.path)}" alt="" loading="lazy" data-meta="1" />`
              : `<div class="media-cover media-cover-${f.type}">${IMG[f.type]}</div>`;
            return `<div class="media-card media-card-${f.type}" data-path="${esc(f.path)}" data-type="${f.type}" data-name="${esc(nm)}">
            <div class="media-thumb">${cover}
              <span class="media-badge">${f.type}</span>
              ${kb ? `<span class="media-size">${kb} KB</span>` : ""}
            </div>
            <div class="media-name">${esc(nm)}</div>
            <span class="media-meta" data-meta-for="${esc(f.path)}"></span>
            <div class="media-actions">
              <button class="media-act media-play" title="${f.type === 'image' ? 'View image' : 'Play now'}">${f.type === 'image' ? 'View' : 'Play'}</button>
              <button class="media-act media-queue" title="Add to queue" aria-label="Add to queue">＋</button>
              <button class="media-act media-del" title="Delete file" aria-label="Delete file"><svg class="ico-svg" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg></button>
            </div>
          </div>`;
          }).join("") || `<div class="placeholder">No media yet. Upload images / audio / video to build your library.</div>`}
        </div>
        <p id="mediaNoMatches" class="media-no-matches" hidden>No matching files. Try another name or media type.</p>
        <details class="media-queue-section"><summary>Up next</summary><div class="media-queue-options"><button class="media-qbtn ${window.mpQueue.loop ? "on" : ""}" id="mpLoopBtn" aria-pressed="${!!window.mpQueue.loop}" title="Loop queue">Loop</button><button class="media-qbtn ${window.mpQueue.shuffle ? "on" : ""}" id="mpShufBtn" aria-pressed="${!!window.mpQueue.shuffle}" title="Shuffle queue">Shuffle</button></div><div class="mp-queue" id="mpQueueBar"></div></details>
        <div class="media-library-foot"><button class="media-import" id="mediaUploadButton">＋ Add media</button><input type="file" id="mediaUpload" accept="image/*,audio/*,video/*,.srt,.lrc" multiple hidden /><span>Drop files here · SRT / LRC supported</span></div>
        </aside>
      </div>
      <div id="mediaLightbox" style="display:none;"><img id="mediaLightboxImg" src="" alt="" /></div>`;

    const lb = $("mediaLightbox");
    if (lb) lb.addEventListener("click", () => { lb.style.display = "none"; });

    /* move static player into the stage wrap */
    const player = persistentPlayer;
    const wrap = $("mediaStageWrap");
    if (player && wrap && player.parentElement !== wrap) wrap.insertBefore(player, wrap.firstChild);
    if (player) player.classList.remove("hidden");
    wireMediaPlayer();
    if (resumePlayback && mpState.media) mpState.media.play().catch(() => {});
    if ($("mpStage") && !$("mpStage").children.length) {
      player.dataset.kind = 'empty';
      $("mpStage").innerHTML = '<div class="media-empty"><svg aria-hidden="true" viewBox="0 0 80 64" fill="none"><rect x="7" y="5" width="66" height="47" rx="5" stroke="currentColor" stroke-width="1.5"/><path d="M29 61h22M40 53v8M35 20l15 9-15 9V20z" stroke="currentColor" stroke-width="1.5"/></svg><span class="media-library-eyebrow">A SPACE FOR YOUR MEDIA</span><h3>Bring something into focus.</h3><p>Choose an image, video, or audio file<br>from your library to get started.</p><button id="mediaBrowse" class="btn-secondary">Browse library →</button></div>';
    }
    let closed = false;
    try { const stored=localStorage.getItem('emilia.media.libraryClosed');closed=stored===null?matchMedia('(max-width:760px)').matches:stored==='true'; } catch {}
    const toggleLibrary = value => {
      closed=value;$("mediaLibrary").hidden=closed;p.classList.toggle('library-closed',closed);
      $("mediaLibraryToggle").setAttribute('aria-expanded',String(!closed));
      $("mediaLibraryToggle").textContent=closed?'Show library':'Hide library';
      $("mediaLibraryScrim").hidden=closed;
      try {localStorage.setItem('emilia.media.libraryClosed',String(closed));}catch{}
    };
    $("mediaLibraryToggle").onclick=()=>toggleLibrary(!closed);
    $("mediaLibraryClose").onclick=()=>{toggleLibrary(true);$("mediaLibraryToggle").focus();};
    $("mediaLibraryScrim").onclick=()=>toggleLibrary(true);
    if ($("mediaBrowse")) $("mediaBrowse").onclick=()=>{toggleLibrary(false);$("mediaSearch").focus();};
    $("mediaUploadButton").onclick=()=>$("mediaUpload").click();
    toggleLibrary(closed);
    const applyFilter = () => {
      const query=$("mediaSearch").value.trim().toLowerCase();let count=0;
      p.querySelectorAll('.media-card').forEach(card=>{card.hidden=!(filter==='all'||card.dataset.type===filter)||!card.dataset.name.toLowerCase().includes(query);if(!card.hidden)count++;});
      p.querySelectorAll('.media-chip').forEach(button=>{const active=button.dataset.f===filter;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
      $("mediaNoMatches").hidden=count>0||!all.length;
    };
    $("mediaSearch").oninput=applyFilter;applyFilter();

    renderQueue();
    $("mpLoopBtn").addEventListener("click", () => {
      window.mpQueue.loop = !window.mpQueue.loop;
      $("mpLoopBtn").classList.toggle("on", window.mpQueue.loop);
      $("mpLoopBtn").setAttribute('aria-pressed',String(window.mpQueue.loop));
      renderQueue();
    });
    $("mpShufBtn").addEventListener("click", () => {
      window.mpQueue.shuffle = !window.mpQueue.shuffle;
      $("mpShufBtn").classList.toggle("on", window.mpQueue.shuffle);
      $("mpShufBtn").setAttribute('aria-pressed',String(window.mpQueue.shuffle));
      renderQueue();
    });

    /* auto-next from queue */
    window._mpAutoNext = () => {
      const q = window.mpQueue;
      if (!q.items.length) return;
      let next;
      if (q.shuffle) next = Math.floor(Math.random() * q.items.length);
      else next = q.idx + 1;
      if (next >= q.items.length) {
        if (!q.loop) { q.idx = -1; renderQueue(); return; }
        next = 0;
      }
      q.idx = next;
      const it = q.items[next];
      renderQueue();
      if (it) loadToPlayer(it.path, it.type, it.name);
    };

    /* image metadata badges */
    p.querySelectorAll("img[data-meta]").forEach((img) => {
      img.addEventListener("load", () => {
        const card = img.closest(".media-card");
        if (!card) return;
        const el = card.querySelector(".media-meta");
        if (el) el.textContent = `${img.naturalWidth} × ${img.naturalHeight}px`;
      });
    });

    p.querySelectorAll(".media-chip").forEach((c) =>
      c.addEventListener("click", () => { filter = c.dataset.f;window._mediaFilter = filter;applyFilter(); }));
    p.querySelectorAll(".media-card").forEach((card) => {
      const path = card.dataset.path, type = card.dataset.type, name = card.dataset.name;
      card.querySelector(".media-play").addEventListener("click", (e) => {
        e.stopPropagation();
        window.mpQueue.items = [{ path, type, name }];
        window.mpQueue.idx = 0;
        renderQueue();
        loadToPlayer(path, type, name);
        if(matchMedia('(max-width:760px)').matches)toggleLibrary(true);
      });
      card.addEventListener('click',e=>{if(!e.target.closest('button'))card.querySelector('.media-play').click();});
      card.querySelector(".media-queue").addEventListener("click", (e) => {
        e.stopPropagation();
        window.mpQueue.items.push({ path, type, name });
        if (window.mpQueue.idx < 0) window.mpQueue.idx = 0;
        renderQueue();
      });
      card.querySelector(".media-del").addEventListener("click", async (e) => {
        e.stopPropagation();
        if (!confirm("Delete " + name + "?")) return;
        window.mpQueue.items = window.mpQueue.items.filter((it) => it.path !== path);
        await Api.deleteWorkspaceFile(path);
        renderMediaTab(window._mediaFilter || "all");
      });
    });
    const up = $("mediaUpload");
    if (up) up.addEventListener("change", async () => {
      await Api.uploadWorkspace(up.files, "media");
      up.value = "";
      renderMediaTab(window._mediaFilter || "all");
    });
    const grid = $("mediaGrid");
    if (grid) {
      grid.addEventListener("dragover", (e) => { e.preventDefault(); grid.classList.add("media-drop"); });
      grid.addEventListener("dragleave", () => grid.classList.remove("media-drop"));
      grid.addEventListener("drop", async (e) => {
        e.preventDefault();
        grid.classList.remove("media-drop");
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
          const subs = Array.from(e.dataTransfer.files).filter((f) => /\.(srt|lrc)$/i.test(f.name));
          if (subs.length) {
            const txt = await subs[0].text();
            window.mpSubs = /\.lrc$/i.test(subs[0].name) ? parseLrc(txt) : parseSrt(txt);
            const sl = $("mpSubLine");
            if (sl) sl.textContent = `🎵 subtitle loaded: ${subs[0].name} (${window.mpSubs.length} lines)`;
            return;
          }
          await Api.uploadWorkspace(e.dataTransfer.files, "media");
          renderMediaTab(window._mediaFilter || "all");
        }
      });
    }

    /* vertical split resizer */
    const resizer = $("mpResizer"), body = $("mediaBody");
    if (resizer && body) {
      resizer.addEventListener("mousedown", (e) => {
        e.preventDefault();
        const startY = e.clientY, startH = wrap ? wrap.getBoundingClientRect().height : 320;
        const move = (ev) => {
          const dy = ev.clientY - startY;
          const nh = Math.min(Math.max(140, startH + dy), body.getBoundingClientRect().height - 120);
          wrap.style.height = nh + "px";
        };
        const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
        document.addEventListener("mousemove", move);
        document.addEventListener("mouseup", up);
      });
    }

    /* subtitle tick */
    if (!window._mpSubTickOn) {
      window._mpSubTickOn = true;
      setInterval(() => {
        const sl = $("mpSubLine");
        if (!sl || !window.mpSubs) return;
        const mm = mpState.media;
        if (!mm || !mm.duration) { sl.textContent = ""; return; }
        const cur = mm.currentTime;
        const hit = window.mpSubs.filter((l) => cur >= l.t1 && cur <= l.t2).map((l) => l.text).join(" ");
        sl.textContent = hit || "";
      }, 250);
    }

    /* keyboard shortcuts (active only while media view is visible) */
    if (!window._mpKeyOn) {
      window._mpKeyOn = true;
      document.addEventListener("keydown", function mpKey(e) {
        const view = document.getElementById("view-media");
        if (!view || !view.classList.contains('active') || document.querySelector('dialog[open]')) return;
        const tag = (e.target.tagName || "").toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select" || tag === "button" || e.target.isContentEditable) return;
        if (e.key === " " || e.code === "Space") {
          const pl = $("mpPlay");
          if (pl) { e.preventDefault(); pl.click(); }
        } else if (e.key === "ArrowLeft") {
          const b = $("mpBack"); if (b) { e.preventDefault(); b.click(); }
        } else if (e.key === "ArrowRight") {
          const f = $("mpFwd"); if (f) { e.preventDefault(); f.click(); }
        } else if (e.key === "m" || e.key === "M") {
          const vl = $("mpVol");
          if (vl) { vl.value = vl.value === "0" ? (vl.dataset.last || "80") : "0"; vl.dataset.last = vl.value === "0" ? (vl.dataset.last || "80") : vl.value; vl.dispatchEvent(new Event("input")); }
        }
      });
    }
  }

  function renderMedia() {
    renderMediaTab(window._mediaFilter || "all");
  }

  /* ---- shared media player (big stage + control bar) ---- */
  const mpState = { media: null, type: "video" };

  function mpFmt(s) {
    if (!isFinite(s) || s < 0) return "0:00";
    const m = Math.floor(s / 60), sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  }

  function loadToPlayer(path, type, name) {
    const player = $("mediaPlayer");
    const stage = $("mpStage");
    if (!player || !stage) return;
    const url = Api.workspaceFileUrl(path);
    mpState.type = type;
    player.dataset.kind = type;
    document.querySelectorAll('#mediaGrid .media-card').forEach(card=>card.classList.toggle('selected',card.dataset.path===path));
    player.classList.remove("hidden");
    if (type === "image") {
      stage.innerHTML = `<img src="${url}" alt="${esc(name)}" class="mp-img" />`;
      mpState.media = null;
      const t = $("mpTime");
      if (t) t.textContent = "image";
      const sk = $("mpSeek"), vl = $("mpVol"), rt = $("mpRate");
      if (sk) sk.disabled = true; if (vl) vl.disabled = true; if (rt) rt.disabled = true;
      const pl = $("mpPlay"); if (pl) pl.textContent = "⏸";
    } else {
      const tag = type === "audio" ? "audio" : "video";
      stage.innerHTML = `<${tag} id="mpMedia" src="${url}" controls preload="metadata" autoplay></${tag}>`;
      mpState.media = $("mpMedia");
      const sk = $("mpSeek"), vl = $("mpVol"), rt = $("mpRate");
      if (sk) sk.disabled = false; if (vl) vl.disabled = false; if (rt) rt.disabled = false;
      const mm = mpState.media;
      if (vl) mm.volume = parseInt(vl.value || 80, 10) / 100;
      if (rt) mm.playbackRate = parseFloat(rt.value || 1);
      mm.addEventListener("loadedmetadata", () => { const t = $("mpTime"); if (t) t.textContent = `0:00 / ${mpFmt(mm.duration)}`; });
      mm.addEventListener("timeupdate", () => {
        const sk2 = $("mpSeek"), t2 = $("mpTime");
        if (mm.duration) {
          if (sk2) sk2.value = Math.round((mm.currentTime / mm.duration) * 1000);
          if (t2) t2.textContent = `${mpFmt(mm.currentTime)} / ${mpFmt(mm.duration)}`;
        }
      });
      mm.addEventListener("play", () => { const pl = $("mpPlay"); if (pl) pl.textContent = "⏸"; });
      mm.addEventListener("pause", () => { const pl = $("mpPlay"); if (pl) pl.textContent = "▶"; });
      mm.addEventListener("ended", () => { const pl = $("mpPlay"); if (pl) pl.textContent = "▶"; if (window._mpAutoNext) window._mpAutoNext(); });
      const pl = $("mpPlay"); if (pl) pl.textContent = "⏸";
    }
    const nm = $("mpName"); if (nm) nm.textContent = name;
  }

  function wireMediaPlayer() {
    const pl = $("mpPlay"), back = $("mpBack"), fwd = $("mpFwd"), seek = $("mpSeek"),
          vol = $("mpVol"), rate = $("mpRate"), fs = $("mpFs"), share = $("mpShare");
    if (!pl || pl._w) return;
    pl._w = true;
    pl.addEventListener("click", () => {
      const mm = mpState.media;
      if (!mm) return;
      if (mm.paused) mm.play().catch(() => App.toast('This file could not be played.')); else mm.pause();
    });
    if (back) back.addEventListener("click", () => { if (mpState.media) mpState.media.currentTime = Math.max(0, mpState.media.currentTime - 10); });
    if (fwd) fwd.addEventListener("click", () => { if (mpState.media) mpState.media.currentTime = Math.min(mpState.media.duration || 0, mpState.media.currentTime + 10); });
    if (seek) seek.addEventListener("input", () => {
      const mm = mpState.media;
      if (mm && mm.duration) mm.currentTime = (parseFloat(seek.value) / 1000) * mm.duration;
    });
    if (vol) vol.addEventListener("input", () => { if (mpState.media) mpState.media.volume = parseFloat(vol.value) / 100; });
    if (rate) rate.addEventListener("change", () => { if (mpState.media) mpState.media.playbackRate = parseFloat(rate.value); });
    if (fs) fs.addEventListener("click", () => {
      const player = $("mediaPlayer");
      if (!player) return;
      if (document.fullscreenElement) document.exitFullscreen();
      else if (player.requestFullscreen) player.requestFullscreen();
    });
    if (share) share.addEventListener("click", async () => {
      const media = $("mpStage").querySelector('img,video,audio');
      if (!media) return;
      try { await navigator.clipboard.writeText(media.src); App.toast('Media link copied'); }
      catch (e) { App.toast('Could not copy the media link.'); }
    });
  }

const localState = { path: "" };

  const LOCAL_ICO = {
    "": "📄", txt: "📄", md: "📝", py: "🐍", js: "🟨", ts: "🟦", html: "🌐", css: "🎨",
    json: "🧾", csv: "📊", xml: "🧬", yml: "⚙️", yaml: "⚙️", ini: "⚙️", cfg: "⚙️", log: "🧾",
    sh: "🖥", bat: "🖥", ps1: "🖥", sql: "🗄", java: "☕", c: "©", cpp: "©", h: "©", go: "🐹",
    rs: "🦀", rb: "💎", php: "🐘", png: "🖼", jpg: "🖼", jpeg: "🖼", gif: "🖼", webp: "🖼",
    bmp: "🖼", svg: "🖼", mp3: "🎵", wav: "🎵", ogg: "🎵", m4a: "🎵", flac: "🎵",
    mp4: "🎬", webm: "🎬", mov: "🎬", avi: "🎬", mkv: "🎬", m4v: "🎬", pdf: "📕",
    zip: "📦", rar: "📦", "7z": "📦", exe: "⚙️", dll: "🧩", docx: "📘", xlsx: "📗", pptx: "📙",
  };

  function localExt(name) { const m = name.match(/\.([a-zA-Z0-9]+)$/); return m ? m[1].toLowerCase() : ""; }
  function localIco(name) { return LOCAL_ICO[localExt(name)] || "📄"; }
  function fmtSize(n) {
    if (!n) return "-";
    if (n < 1024) return n + " B";
    if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
    return (n / 1024 / 1024).toFixed(1) + " MB";
  }
  function fmtTime(ts) {
    if (!ts) return "";
    const d = new Date(ts * 1000);
    return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  function wireLocal() {
    const go = $("localGoBtn"), up = $("localUpBtn"), inp = $("localPath");
    if (!go || go._w) return;
    go._w = true;
    const nav = (path) => { if (path) renderLocalPath(path); };
    go.addEventListener("click", () => nav(inp.value.trim()));
    if (up) up.addEventListener("click", async () => {
      try {
        const r = await Api.localScan(localState.path);
        nav(r.parent);
      } catch (e) { /* stay */ }
    });
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") nav(inp.value.trim()); });
    document.querySelectorAll(".local-drive").forEach((b) =>
      b.addEventListener("click", () => { inp.value = b.dataset.path; nav(b.dataset.path); }));
  }

  async function renderLocalPath(path) {
    const panel = $("localPanel");
    if (!panel) return;
    panel.innerHTML = "<div class='placeholder'>Scanning…</div>";
    try {
      const r = await Api.localScan(path);
      localState.path = r.path;
      const inp = $("localPath");
      if (inp) inp.value = r.path;
      const crumbEl = $("localCrumbs");
      if (crumbEl) {
        let acc = "";
        const crumbs = [];
        const m = r.path.match(/^([A-Za-z]:)([\\/]?)/);
        if (m) {
          acc = m[1] + "/";
          crumbs.push(`<button class="crumb" data-cp="${m[1]}/">${m[1]}</button>`);
        } else if (r.path.startsWith("/")) {
          acc = "/";
          crumbs.push(`<button class="crumb" data-cp="/">/</button>`);
        }
        const rel = r.path.slice(m ? m[0].length : acc.length).split(/[\\/]+/).filter(Boolean);
        rel.forEach((part) => {
          acc += part + "/";
          crumbs.push(`<button class="crumb" data-cp="${esc(acc)}">${esc(part)}</button>`);
        });
        crumbEl.innerHTML = crumbs.join(" / ");
        crumbEl.querySelectorAll(".crumb").forEach((c) =>
          c.addEventListener("click", () => renderLocalPath(c.dataset.cp)));
      }
      panel.innerHTML = r.entries.length ? `
        <div class="local-list">
          ${r.entries.map((en) => en.is_dir
            ? `<div class="local-row local-dir" data-path="${esc(en.path)}"><span class="local-ico">📁</span><span class="local-name">${esc(en.name)}</span><span class="muted">folder</span></div>`
            : `<div class="local-row local-file" data-path="${esc(en.path)}"><span class="local-ico">${localIco(en.name)}</span><span class="local-name">${esc(en.name)}</span><span class="muted">${fmtSize(en.size)}</span><span class="muted">${fmtTime(en.mtime)}</span></div>`).join("")}
        </div>` : "<div class='placeholder'>Empty folder</div>";
      panel.querySelectorAll(".local-dir").forEach((d) =>
        d.addEventListener("click", () => renderLocalPath(d.dataset.path)));
      panel.querySelectorAll(".local-file").forEach((f) =>
        f.addEventListener("click", () => previewLocalFile(f.dataset.path)));
    } catch (e) {
      panel.innerHTML = `<span class="error">${esc(e.message)}</span>`;
    }
  }

  async function previewLocalFile(path) {
    const panel = $("localPanel");
    if (!panel) return;
    panel.innerHTML = "<div class='placeholder'>Reading…</div>";
    try {
      const r = await Api.localRead(path);
      const head = `<div class="local-preview-head"><button class="btn-secondary btn-sm" id="localBackBtn">← Back</button> <span class="local-preview-path">${esc(path)}</span> <span class="muted">${fmtSize(r.size)}</span></div>`;
      if (r.kind === "text") {
        panel.innerHTML = head + `<pre class="local-preview-text">${esc(r.content.slice(0, 200000))}</pre>`;
      } else {
        const ext = r.ext || "";
        const imgRe = /^(png|jpe?g|gif|webp|bmp|svg)$/;
        const audRe = /^(mp3|wav|ogg|m4a|aac|flac)$/;
        const vidRe = /^(mp4|webm|mov|avi|mkv|m4v)$/;
        const url = "/api/local/file?path=" + encodeURIComponent(path);
        if (imgRe.test(ext)) panel.innerHTML = head + `<img class="local-preview-img" src="${url}" alt="" />`;
        else if (audRe.test(ext)) panel.innerHTML = head + `<audio controls src="${url}"></audio>`;
        else if (vidRe.test(ext)) panel.innerHTML = head + `<video controls src="${url}"></video>`;
        else panel.innerHTML = head + `<div class="local-binary">Binary file , ${fmtSize(r.size)} , type ${esc(ext)}<br/><span class="muted">Preview not available for this type.</span></div>`;
      }
      const bb = $("localBackBtn");
      if (bb) bb.addEventListener("click", () => renderLocalPath(localState.path));
    } catch (e) {
      panel.innerHTML = `<span class="error">${esc(e.message)}</span>`;
    }
  }

  function renderLocal() {
    const host = $("wfLocalView");
    const off = $("wfModeOffice"), loc = $("wfModeLocal");
    if (host) host.classList.remove("hidden");
    const ov = $("wfOfficeView");
    if (ov) ov.classList.add("hidden");
    if (off) off.classList.remove("active");
    if (loc) loc.classList.add("active");
    wireLocal();
    const inp = $("localPath");
    renderLocalPath(inp && inp.value.trim() ? inp.value.trim() : "D:/02_Development_Tools");
  }

async function renderRemote() {
    const data = await Api.remoteDevices();
    const host = data.host || {};
    const devices = data.devices || [];
    $("remotePanel").innerHTML = `
      <div class="remote-layout">
        <div class="p10-card remote-host-card">
          <div class="memory-panel-title">THIS DEVICE <span class="badge badge-os">host</span></div>
          <div class="remote-host-row"><span class="remote-k">hostname</span><b>${esc(host.hostname || "-")}</b></div>
          <div class="remote-host-row"><span class="remote-k">os</span><b>${esc(host.os || "-")}</b></div>
          <div class="remote-host-row"><span class="remote-k">machine</span><b>${esc(host.machine || "-")}</b></div>
          <div class="remote-host-row"><span class="remote-k">python</span><b>${esc(host.python || "-")}</b></div>
          <div class="remote-host-row"><span class="remote-k">disk free</span><b>${host.disk_free_gb != null ? host.disk_free_gb + " GB" : "-"}</b></div>
          <div class="remote-badge-row"><span class="badge badge-online">RUNNING</span>
            <span class="muted" style="font-size:11px;">Local agent listens on :3787 , everything flows through audit + permissions</span></div>
        </div>

        <div class="p10-card">
          <div class="memory-panel-title">REMOTE DEVICE CONTROL <span class="badge badge-os">MVP</span></div>
          <p class="muted" style="margin-top:2px;">Register devices, pair with a one-time token, and drive them through the same Worker permission matrix. Commands are queued to the remote agent and audited.</p>
          <div class="remote-register">
            <input type="text" id="remoteName" placeholder="Device name (e.g. Lab Server)" />
            <input type="text" id="remoteHost" placeholder="host / ip (e.g. 192.168.1.40)" />
            <input type="text" id="remoteOs" placeholder="os (optional)" />
            <button class="btn-primary" id="remoteRegisterBtn">+ Register Device</button>
          </div>
          <div id="remotePairMsg" style="margin-top:8px;"></div>

          <div class="remote-bt">
            <div class="memory-panel-title">BLUETOOTH DISCOVERY <span class="badge badge-os">nearby</span></div>
            <button class="btn-secondary" id="btScanBtn">📡 Scan Bluetooth</button>
            <div id="btResults" class="bt-results"><span class="muted" style="font-size:11px;">Click scan to discover nearby BLE devices via Web Bluetooth.</span></div>
          </div>

          <div class="remote-devices" id="remoteDevices"></div>
          <div id="remoteSession"></div>
        </div>
      </div>`;
    $("remoteRegisterBtn").addEventListener("click", async () => {
      const name = $("remoteName").value.trim();
      const host = $("remoteHost").value.trim();
      if (!host) { $("remotePairMsg").innerHTML = `<div class="error">host is required</div>`; return; }
      const r = await Api.registerRemoteDevice(name, host, $("remoteOs").value.trim());
      $("remotePairMsg").innerHTML = r.device_id
        ? `<div class="ok">Registered <b>${esc(name || host)}</b> - pairing token <code>${esc(r.pairing_token)}</code> (PENDING)</div>`
        : `<div class="error">${esc(r.error || "register failed")}</div>`;
      renderRemote();
    });
    const btBtn = $("btScanBtn");
    if (btBtn) btBtn.addEventListener("click", async () => {
      const res = $("btResults");
      if (!res) return;
      res.innerHTML = `<span class="muted">Scanning… (Web Bluetooth needs a secure context & a real radio; falling back to sample devices if unavailable)</span>`;
      let found = [];
      try {
        if (navigator.bluetooth && navigator.bluetooth.requestDevice) {
          const dev = await navigator.bluetooth.requestDevice({ acceptAllDevices: true });
          found = [{ name: dev.name || "Unnamed BLE device", id: dev.id, type: "bluetooth" }];
        } else {
          found = [
            { name: "WF-1000XM5 Earbuds", id: "ble-88:C6:26:xx", type: "bluetooth" },
            { name: "MX Master 3S", id: "ble-9C:50:EE:xx", type: "bluetooth" },
            { name: "Pixel Watch 2", id: "ble-D4:3A:2C:xx", type: "bluetooth" },
          ];
        }
      } catch (e) {
        found = [
          { name: "WF-1000XM5 Earbuds", id: "ble-88:C6:26:xx", type: "bluetooth" },
          { name: "MX Master 3S", id: "ble-9C:50:EE:xx", type: "bluetooth" },
          { name: "Pixel Watch 2", id: "ble-D4:3A:2C:xx", type: "bluetooth" },
        ];
        res.innerHTML = `<span class="muted" style="font-size:11px;">${esc(String(e && e.message || e).slice(0, 90))} - showing sample devices:</span>`;
      }
      res.innerHTML = found.map((d) =>
        `<div class="bt-dev"><span class="bt-dot"></span><b>${esc(d.name)}</b><code>${esc(d.id)}</code><button class="btn-secondary btn-sm" data-bt="${esc(d.id)}">Pair</button></div>`).join("");
      res.querySelectorAll("[data-bt]").forEach((b) =>
        b.addEventListener("click", () => {
          $("remoteName").value = b.dataset.bt;
          res.innerHTML += `<div class="ok">Pairing request queued - use token in the remote agent to confirm.</div>`;
        }));
    });
    renderRemoteDevices(devices);
  }

  async function renderRemoteDevices(devices) {
    const wrap = $("remoteDevices");
    if (!wrap) return;
    if (!devices.length) {
      wrap.innerHTML = `<div class="placeholder">No remote devices yet. Register one to pair it with the WorkDesk.</div>`;
      return;
    }
    wrap.innerHTML = devices.map((d) => `
      <div class="remote-device">
        <div class="remote-device-head">
          <span class="remote-dot ${d.status === "ONLINE" ? "on" : d.status === "PENDING" ? "pend" : ""}"></span>
          <b>${esc(d.name)}</b>
          <span class="badge ${d.status === "ONLINE" ? "badge-online" : "badge-os"}">${esc(d.status)}</span>
          <button class="btn-mini" data-sel="${esc(d.device_id)}">session</button>
          <span class="muted">${esc(d.host)}</span>
        </div>
        <div class="muted" style="font-size:11px;">os ${esc(d.os || "?")} , last seen ${esc((d.last_seen || "").slice(0, 19))}</div>
      </div>`).join("");
    wrap.querySelectorAll("[data-sel]").forEach((b) =>
      b.addEventListener("click", () => renderRemoteSession(b.dataset.sel)));
  }

  async function renderRemoteSession(deviceId) {
    const data = await Api.remoteDevices();
    const dev = (data.devices || []).find((d) => d.device_id === deviceId);
    const box = $("remoteSession");
    if (!box) return;
    const sess = (dev && dev.session) || [];
    box.innerHTML = `
      <div class="p10-card remote-session">
        <div class="memory-panel-title">SESSION , ${esc(dev ? dev.name : deviceId.slice(0, 8))}</div>
        <div class="remote-term">${sess.map((s) => `<div class="remote-term-line"><span class="remote-term-ts">${esc((s.ts || "").slice(11, 19))}</span><code>$ ${esc(s.command)}</code><span class="badge badge-os">${esc(s.status)}</span></div>`).join("") || `<div class="muted">No commands yet.</div>`}</div>
        <div class="remote-cmd">
          <input type="text" id="remoteCmdInput" placeholder="command to queue on ${esc(dev ? dev.name : "device")} …" />
          <button class="btn-primary" id="remoteCmdBtn">Send</button>
        </div>
        <div class="muted" style="font-size:11px;margin-top:6px;">MVP: queued + audited (local echo). Real execution ships with the signed pairing agent.</div>
      </div>`;
    $("remoteCmdBtn").addEventListener("click", async () => {
      const cmd = $("remoteCmdInput").value.trim();
      if (!cmd) return;
      const r = await Api.sendRemoteCommand(deviceId, cmd);
      if (r.error) { box.innerHTML += `<div class="error">${esc(r.error)}</div>`; return; }
      renderRemoteSession(deviceId);
    });
    $("remoteCmdInput").addEventListener("keydown", (e) => {
      if (e.key === "Enter") $("remoteCmdBtn").click();
    });
  }

  /* ================= Office Suite (P12: docs + sheets + slides + pdf merged) ================= */
  const suiteRendered = {};
  async function renderSuite() {
    const panes = { docs: "suite-docs", sheets: "suite-sheets", slides: "suite-slides", pdf: "suite-pdf" };
    const tab = document.querySelector(".suite-tab.active");
    const current = tab ? tab.dataset.t : "docs";
    document.querySelectorAll(".suite-pane").forEach((p) => p.classList.remove("active"));
    const paneId = panes[current] || "suite-docs";
    const pane = document.getElementById(paneId);
    if (pane) pane.classList.add("active");
    if (!suiteRendered[current]) {
      suiteRendered[current] = true;
      if (current === "docs") await renderDocs();
      else if (current === "sheets") await renderSheets();
      else if (current === "slides") await renderSlides();
      else if (current === "pdf") await renderPdf();
    }
    document.querySelectorAll(".suite-tab").forEach((t) =>
      t.addEventListener("click", () => {
        document.querySelectorAll(".suite-tab").forEach((x) => x.classList.remove("active"));
        t.classList.add("active");
        renderSuite();
      }));
  }

  /* ================= Code Studio (VSCode-style) ================= */
  async function renderCode() {
    wireSplitResize('code');
    const files = await Api.getWorkspaceFiles();
    const codeFiles = (files.files || []).filter((f) =>
      /^(code|scripts?)\//.test(f.path) || /\.(py|js|json|md|txt)$/.test(f.path));
    const groups = {};
    codeFiles.forEach((f) => {
      const dir = f.path.includes("/") ? f.path.split("/")[0] + "/" : "(root)";
      (groups[dir] = groups[dir] || []).push(f);
    });
    $("codeFiles").innerHTML = `
      <div class="ws-file-title">WORKSPACE FILES</div>
      <div class="code-actions">
        <button class="btn-primary ws-new-btn" id="codeNewBtn">+ New File</button>
        <button class="btn-secondary ws-new-btn" id="codeRefreshBtn">↻</button>
      </div>
      ${Object.entries(groups).map(([dir, fs]) => `
        <div class="ws-dir">${esc(dir)}</div>
        ${fs.map((f) => `<div class="ws-file-row" data-p="${esc(f.path)}"><span>${esc(f.path)}</span><button class="btn-danger-ghost" data-del="${esc(f.path)}">✕</button></div>`).join("")}
      `).join("")}`;
    $("codeFiles").querySelectorAll("[data-p]").forEach((r) =>
      r.addEventListener("click", async () => {
        $("codeFilename").value = r.dataset.p;
        const d = await Api.readWorkspace(r.dataset.p);
        if (!d.error) { $("codeEditor").value = d.content; highlightCode(); }
      }));
    $("codeFiles").querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        await Api.deleteWorkspaceFile(b.dataset.del);
        renderCode();
      }));
    $("codeNewBtn").addEventListener("click", () => {
      $("codeEditor").value = "";
      $("codeFilename").value = `code/new_${Date.now() % 10000}.py`;
      highlightCode();
    });
    $("codeRefreshBtn").addEventListener("click", () => renderCode());
    $("codeSaveBtn").addEventListener("click", async () => {
      const path = $("codeFilename").value.trim();
      const r = await Api.saveWorkspace(path, $("codeEditor").value);
      $("codeOutput").innerHTML = r.ok
        ? `<div class="ok">Saved ${esc(path)} (${r.bytes} bytes)</div>`
        : `<div class="error">${esc(r.error || "save failed")}</div>`;
      renderCode();
    });
    $("codeRunBtn").addEventListener("click", async () => {
      $("codeOutput").innerHTML = `<div class="placeholder">Running…</div>`;
      const r = await Api.runCode($("codeEditor").value, "python");
      const out = r.ok
        ? `<pre class="code-out">${esc(r.stdout || "(no output)")}</pre>`
        : `<pre class="code-out err">${esc(r.stdout || "")}${esc(r.stderr || "")}${esc(r.error || "")}</pre>`;
      $("codeOutput").innerHTML = `<div class="run-meta">exit ${r.returncode ?? "-"}</div>${out}`;
    });
    $("codeEditor").addEventListener("input", highlightCode);
    highlightCode();
    if (!codeFiles.length) {
      $("codeEditor").value =
`# AI WorkDesk OS - Code Studio demo
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

print("first 8 fibonacci numbers:", [fib(i) for i in range(1, 9)])`;
      highlightCode();
    }
  }

  /* ---- VSCode-style syntax highlight (simple overlay) ---- */
  function highlightCode() {
    const ed = $("codeEditor");
    const hl = $("codeHighlight");
    if (!ed || !hl) return;
    const src = ed.value || "";
    const escHtml = (x) => String(x).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    let out = escHtml(src);
    // python-ish / js-ish keywords + strings + comments + numbers
    out = out
      .replace(/(#.*)$/gm, '<span class="tok-c">$1</span>')
      .replace(/(&quot;.*?&quot;|&#39;.*?&#39;)/g, '<span class="tok-s">$1</span>')
      .replace(/\b(def|class|return|if|elif|else|for|while|import|from|async|await|const|let|var|function|export|new|try|except|finally|raise|lambda|with|pass|break|continue)\b/g, '<span class="tok-k">$1</span>')
      .replace(/\b(\d+\.?\d*)\b/g, '<span class="tok-n">$1</span>');
    hl.innerHTML = out + "\n";
    ed.scrollTop = 0; hl.scrollTop = 0;
    // keep overlay scroll in sync
    ed.onscroll = () => { hl.scrollTop = ed.scrollTop; hl.scrollLeft = ed.scrollLeft; };
  }

  /* legacy notes entry (vault.js renders the main Vault view) */
  async function renderNotes() {
    const tabs = document.querySelectorAll("#notesTabs .p10-tab");
    const tab = tabs && document.querySelector("#notesTabs .p10-tab.active");
    if (tab) renderNotesTab(tab.dataset.t);
    else renderNotesTab("user");
  }

  /* ================= navigation registry ================= */
  const renderers = {
    timer: renderTimer,
    calc: renderCalc,
    notes: renderNotes,
    code: renderCode,
    suite: renderSuite,
    docs: renderDocs,
    sheets: renderSheets,
    slides: renderSlides,
    pdf: renderPdf,
    media: renderMedia,
    remote: renderRemote,
    local: renderLocal,
  };

  function bindFsButtons() {
    document.querySelectorAll(".fs-btn").forEach((b) =>
      b.addEventListener("click", () => {
        const view = document.getElementById(b.dataset.fs);
        if (!view) return;
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => {});
          b.textContent = "⛶ Fullscreen";
        } else if (view.requestFullscreen) {
          view.requestFullscreen().then(() => { b.textContent = "✕ Exit Fullscreen"; }).catch(() => {});
        }
      }));
  }

  window.Tools = { render: (name) => renderers[name] && renderers[name](), renderers, bindFsButtons, wireSplitResize };
})();
