// Phase 7/8 - WorkDesk views: Projects, Tasks, PMs, Knowledge, Settings +
// the per-chat Session Pane (Virtual Office + Approvals inside every chat).
// All backed by the engine read models.
const Views = (() => {
  const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  const STATE_COLOR = {
    CREATED: "#9EACEA", ANALYZING: "#A3D5E8", CLARIFYING: "#E4D48F", READY: "#8BC8EA",
    RUNNING: "#94D8C3", WAITING_INPUT: "#EAA7B2", PAUSED: "#E1B98F", IN_QA: "#9BBBF4",
    REWORK: "#F4B393", COMPLETED: "#52C41A", FAILED: "#EA6668", CANCELLED: "#6B7280",
  };
  const stateBadge = (s) => `<span class="state-badge" style="background:${STATE_COLOR[s] || "#999"}22;color:${STATE_COLOR[s] || "#555"};border-color:${STATE_COLOR[s] || "#999"}66;">${esc(s)}</span>`;

  // ---------------- Projects & PMs ----------------
  async function renderProjects() {
    const el = document.getElementById("projectsContainer");
    el.innerHTML = "<div class='placeholder'>Loading projects...</div>";
    try {
      const [pms, tasks] = await Promise.all([Api.listPMs(), Api.listTasks(null, 500)]);
      if (!pms.length) {
        el.innerHTML = `<div class='placeholder'>No projects yet. Chat with the Main Brain to start one - a Lifetime PM is created automatically for each project.</div>`;
        return;
      }
      el.innerHTML = pms.map((pm) => {
        const ptasks = tasks.filter((t) => t.project_id === pm.project_id);
        const states = {};
        ptasks.forEach((t) => { states[t.state] = (states[t.state] || 0) + 1; });
        const stateChips = Object.entries(states)
          .map(([s, n]) => `<span class="chip-mini">${esc(s)} ×${n}</span>`).join("");
        const lessons = (pm.lessons || []);
        const high = lessons.filter((l) => l.confidence === "HIGH").length;
        return `<div class="project-card">
          <div class="pc-head">
            <div class="pc-title">
              <div class="pc-name">${esc(pm.project_id)}</div>
              <div class="pc-sub">PM: ${esc(pm.name)} , status ${esc(pm.status)}</div>
            </div>
            <div class="pc-meta">
              <span class="stat-pill">${ptasks.length} tasks</span>
              <span class="stat-pill">${high} HIGH lessons</span>
            </div>
          </div>
          <div class="pc-chips">${stateChips || "<span class='muted'>no tasks yet</span>"}</div>
          ${pm.worker_performance && Object.keys(pm.worker_performance).length
            ? `<div class="pc-perf">Worker performance: ${Object.entries(pm.worker_performance)
                .map(([w, p]) => `${esc(w)} (${typeof p === "object" ? JSON.stringify(p) : p})`).join(" , ")}</div>` : ""}
        </div>`;
      }).join("");
    } catch (e) {
      el.innerHTML = `<div class='error'>Failed loading projects: ${esc(e.message)}</div>`;
    }
  }

  // ---------------- Tasks & QA History ----------------
  let currentTaskId = null;

  async function renderTasks() {
    const list = document.getElementById("tasksList");
    list.innerHTML = "<div class='placeholder'>Loading tasks...</div>";
    try {
      const tasks = await Api.listTasks(null, 500);
      if (!tasks.length) {
        list.innerHTML = "<div class='placeholder'>No tasks yet. Send a task to the Main Brain in the Chat view.</div>";
        return;
      }
      list.innerHTML = tasks.map((t) => `
        <div class="task-row ${t.task_id === currentTaskId ? "active" : ""}" data-task="${t.task_id}">
          <div class="task-row-top">
            <span class="task-request">${esc(t.request)}</span>
            ${stateBadge(t.state)}
          </div>
          <div class="task-row-meta">
            <span class="muted">${esc(t.project_id)}</span>
            <span>QA cycles: ${t.qa_cycles ?? "-"}</span>
            <span>score: ${t.qa_score ?? "-"}</span>
            <span>rework: ${t.rework_count}</span>
            <span class="muted">${esc(t.created_ts || "")}</span>
          </div>
        </div>`).join("");
      list.querySelectorAll("[data-task]").forEach((el) => {
        el.addEventListener("click", () => openTaskDetail(el.getAttribute("data-task")));
      });
      if (currentTaskId) await openTaskDetail(currentTaskId);
    } catch (e) {
      list.innerHTML = `<div class='error'>Failed loading tasks: ${esc(e.message)}</div>`;
    }
  }

  async function openTaskDetail(taskId) {
    currentTaskId = taskId;
    document.querySelectorAll(".task-row").forEach((el) =>
      el.classList.toggle("active", el.getAttribute("data-task") === taskId));
    const pane = document.getElementById("taskDetailPane");
    pane.innerHTML = "<div class='placeholder'>Loading task detail...</div>";
    try {
      const d = await Api.getTaskDetail(taskId);
      if (currentTaskId !== taskId) return;
      const task = d.task;
      const spec = task.spec || {};
      const comps = spec.components || [];
      const team = spec.team_plan || {};
      const verdicts = d.qa_history || [];
      const qa1 = verdicts.filter((v) => v.stage === "QA1");
      const qa2 = verdicts.filter((v) => v.stage === "QA2");
      const cycles = [...new Set(qa2.map((v) => v.cycle))];
      const artifacts = (task.result && task.result.artifacts) || [];
      const timeline = d.timeline || [];
      const routes = d.model_routes || [];

      pane.innerHTML = `
        <div class="td-head">
          <div class="td-title">${esc(task.request)}</div>
          <div class="td-badges">${stateBadge(task.state)} <span class="chip-mini">QA score ${task.result.qa_score ?? "-"}</span></div>
        </div>

        <div class="td-section">
          <div class="td-section-title">SPEC & TEAM</div>
          <div class="td-spec-grid">
            <div><span class="muted">output</span> <strong>${esc(spec.output_type || "-")}</strong></div>
            <div><span class="muted">complexity</span> <strong>${esc(spec.complexity || "-")}</strong></div>
            <div><span class="muted">project</span> <strong>${esc(task.project_id)}</strong></div>
            <div><span class="muted">components</span> <strong>${comps.length}</strong></div>
          </div>
          ${comps.length ? `<table class="td-table"><tr><th>component</th><th>capability</th><th>assigned worker</th><th>SBR (skill , score)</th></tr>${
            (() => {
              const sbrBySkill = {};
              (spec.team_routes || []).forEach((r) => { if (r.skill) sbrBySkill[r.skill] = r; });
              (spec.capability_gaps_detail || []).forEach((g) => { sbrBySkill[g.skill] = g; });
              return comps.map((c) => {
                const r = sbrBySkill[c.skill] || sbrBySkill[c.capability] || sbrBySkill[c.id];
                let cell = "-";
                if (r && r.worker) {
                  cell = `${esc(r.worker)} , <span class="chip-mini">${r.score}</span>`;
                } else if (r) {
                  const gapSkill = r.suggested_skill || r.skill || c.capability;
                  cell = `<span class="chip-mini warn">GAP → ${esc(gapSkill)}</span> ` +
                    `<button class="btn-primary btn-sm sbr-create" data-cap="${esc(gapSkill)}">Create worker</button>`;
                }
                return `<tr><td>${esc(c.id)}</td><td>${esc(c.capability)}</td><td>${esc(team[c.id] || "-")}</td><td>${cell}</td></tr>`;
              }).join("");
            })()
          }</table>` : ""}
        </div>

        <div class="td-section">
          <div class="td-section-title">REQUIREMENT QA (QA-1)</div>
          ${qa1.length ? qa1.map((v) => `
            <div class="verdict-row ${v.passed ? "ok" : "bad"}">
              <span class="verdict-tag">${esc(v.criterion)}</span>
              <span>${v.passed ? "PASS" : "FAIL"}</span>
              ${v.evidence ? `<span class="muted">, ${esc(v.evidence)}</span>` : ""}
              ${v.fix_hint ? `<span class="muted">, ${esc(v.fix_hint)}</span>` : ""}
            </div>`).join("") : "<div class='muted'>not recorded</div>"}
        </div>

        <div class="td-section">
          <div class="td-section-title">OUTPUT QA (QA-2) - ${cycles.length} cycle${cycles.length === 1 ? "" : "s"}</div>
          ${cycles.map((c) => {
            const cv = qa2.filter((v) => v.cycle === c);
            const passed = cv.length && cv.every((v) => v.passed);
            return `<div class="qa-cycle">
              <div class="qa-cycle-head"><strong>Cycle ${c}</strong> ${passed ? '<span class="chip-mini ok">PASS</span>' : '<span class="chip-mini bad">FAIL</span>'}</div>
              ${cv.filter((v) => !v.passed).map((v) => `
                <div class="verdict-row bad">
                  <span class="verdict-tag">${esc(v.component)} , ${esc(v.criterion)}</span>
                  <span>${esc(v.severity)}</span>
                  <span class="muted">${esc(v.evidence)}</span>
                  <span class="muted">→ ${esc(v.fix_hint)}</span>
                </div>`).join("") || '<div class="muted">all checks passed</div>'}
            </div>`;
          }).join("")}
        </div>

        <div class="td-section">
          <div class="td-section-title">ARTIFACTS</div>
          ${artifacts.length ? `<table class="td-table"><tr><th>component</th><th>kind</th><th>path</th></tr>${
            artifacts.map((a) => `<tr><td>${esc(a.component)}</td><td>${esc(a.kind)}</td><td class="mono">${esc(a.path || "-")}</td></tr>`).join("")
          }</table>` : "<div class='muted'>none</div>"}
        </div>

        <div class="td-section">
          <div class="td-section-title">MODEL ROUTES (Phase 8)</div>
          ${routes.length ? `<table class="td-table"><tr><th>worker</th><th>capability</th><th>provider</th><th>model</th><th>reason</th></tr>${
            routes.map((r) => `<tr><td>${esc(r.worker_id)}</td><td>${esc(r.capability)}</td>
              <td>${esc(r.provider)}${r.privacy_sensitive ? ' <span class="chip-mini warn">PRIVATE</span>' : ""}</td>
              <td class="mono">${esc(r.model)}</td>
              <td class="muted">${esc(r.reason)}</td></tr>`).join("")
          }</table>` : "<div class='muted'>no routing decisions recorded</div>"}
        </div>

        <div class="td-section">
          <div class="td-section-title">STATE MACHINE</div>
          <div class="sm-chain">${(d.transitions || []).map((tr, i) => `
            ${i ? '<span class="sm-arrow">→</span>' : ""}<span class="sm-node">${esc(tr.from_state)}<span class="sm-trigger">${esc(tr.trigger)}</span>${esc(tr.to_state)}</span>`).join("")
            || "<span class='muted'>no transitions</span>"}</div>
        </div>

        <div class="td-section">
          <div class="td-section-title">AUDIT TIMELINE</div>
          <div class="td-timeline">${timeline.map((a) => `
            <div class="tl-row"><span class="tl-ts muted">${esc(a.ts)}</span>
              <span class="tl-actor">${esc(a.actor_role)}·${esc(a.actor_id || "")}</span>
              <code>${esc(a.action)}</code>
              <span class="muted">${esc(a.reason || "")}</span></div>`).join("")
            || "<div class='muted'>no audit events</div>"}</div>
        </div>

        ${task.state === "CLARIFYING" || task.state === "READY" || task.state === "PAUSED" || task.state === "CANCELLED"
          ? `<button class="btn-primary td-resume" data-task="${taskId}">↻ Resume Task</button>` : ""}`;

      const btn = pane.querySelector(".td-resume");
      if (btn) btn.addEventListener("click", async () => {
        await Api.resumeTask(taskId);
        await Promise.all([renderTasks(), renderProjects()]);
        App.toast("Task resumed");
      });
      pane.querySelectorAll(".sbr-create").forEach((b) => {
        b.addEventListener("click", async () => {
          const cap = b.getAttribute("data-cap");
          b.disabled = true; b.textContent = "Creating…";
          try {
            const res = await Api.createCapabilityWorker(cap);
            if (res && res.error) { App.toast("Create failed: " + res.error); b.disabled = false; b.textContent = "Create worker"; return; }
            App.toast(`Worker ready: ${res.name || res.worker_id} (${res.mode})`);
            await Promise.all([renderTasks(), renderProjects()]);
            if (window.Workers && Workers.renderRegistry) await Workers.renderRegistry();
          } catch (err) {
            App.toast("Create failed: " + err.message);
            b.disabled = false; b.textContent = "Create worker";
          }
        });
      });
    } catch (e) {
      pane.innerHTML = `<div class='error'>Failed loading detail: ${esc(e.message)}</div>`;
    }
  }

  // ---------------- Project Managers ----------------
  async function renderPMs() {
    const el = document.getElementById("pmsContainer");
    el.innerHTML = "<div class='placeholder'>Loading PMs...</div>";
    try {
      const pms = await Api.listPMs();
      if (!pms.length) { el.innerHTML = "<div class='placeholder'>No PMs yet. Create a workspace to spawn your first Project Manager.</div>"; return; }
      const totalTasks = pms.reduce((s, pm) => s + (pm.task_count || 0), 0);
      const totalLessons = pms.reduce((s, pm) => s + (pm.lessons || []).length, 0);
      const active = pms.filter((pm) => (pm.status || "").toLowerCase() !== "closed").length;
      el.innerHTML = `
        <div class="pm-toolbar">
          <div class="pm-stats">
            <span class="pm-stat"><b>${pms.length}</b> PMs</span>
            <span class="pm-stat"><b>${active}</b> active</span>
            <span class="pm-stat"><b>${totalTasks}</b> tasks</span>
            <span class="pm-stat"><b>${totalLessons}</b> lessons</span>
          </div>
          <input id="pmSearch" class="pm-search" placeholder="Search PMs by name / project / lesson..." />
        </div>
        <div class="pm-list">
        ${pms.map((pm) => {
          const lessons = pm.lessons || [];
          const perf = pm.worker_performance || {};
          const st = (pm.status || "active").toLowerCase();
          const badgeCls = st === "closed" ? "badge-off" : st === "paused" ? "badge-warn" : "badge-online";
          return `<div class="pm-card" data-search="${esc((pm.name + " " + pm.project_id + " " + lessons.map((l) => l.content).join(" ")).toLowerCase())}">
          <div class="pm-head">
            <div class="pm-avatar">🧭</div>
            <div class="pm-info">
              <div class="pm-name">${esc(pm.name)} <span class="badge ${badgeCls}">${esc(pm.status || "active")}</span></div>
              <div class="pm-sub">project <code>${esc(pm.project_id)}</code> , ${pm.task_count} tasks , institutional memory</div>
            </div>
          </div>
          <div class="pm-counts">
            <span>📚 knowledge ${(pm.knowledge || []).length}</span>
            <span>📌 decisions ${(pm.decisions || []).length}</span>
            <span>🤝 conventions ${(pm.conventions || []).length}</span>
            <span>🧠 lessons ${lessons.length}</span>
          </div>
          ${Object.keys(perf).length ? `<div class="pm-perf">${Object.entries(perf)
            .map(([w, pp]) => {
              if (typeof pp === "object" && pp) {
                const qa = (pp.qa_passed ?? "-") + " QA pass";
                const fl = (pp.failure_rate ?? 0) + "% fail";
                const ms = pp.avg_execution_time_ms != null ? Math.round(pp.avg_execution_time_ms) + "ms avg" : "";
                const upd = pp.last_updated ? pp.last_updated.slice(0, 10) : "";
                return `<span class="chip-mini"><b>${esc(w)}</b> &middot; ${pp.tasks_completed ?? 0} done &middot; ${qa} &middot; ${fl} ${ms} ${upd}</span>`;
              }
              return `<span class="chip-mini">${esc(w)}: ${esc(pp)}</span>`;
            }).join("")}</div>` : ""}
          ${lessons.length ? `<div class="pm-lessons">${lessons.slice(0, 3).map((l) => `
            <div class="lesson-row ${l.confidence === "HIGH" ? "high" : ""}">
              <span class="verdict-tag">${esc(l.confidence)}</span>
              <span>${esc(l.content)}</span>
              <span class="muted">evidence ×${l.evidence_count}</span>
            </div>`).join("")}${lessons.length > 3 ? `<div class="muted" style="font-size:11px;padding:4px 2px;">+ ${lessons.length - 3} more lessons</div>` : ""}</div>` : ""}
        </div>`;
        }).join("")}
        </div>`;
      const inp = document.getElementById("pmSearch");
      if (inp) inp.addEventListener("input", () => {
        const q = inp.value.trim().toLowerCase();
        document.querySelectorAll(".pm-card").forEach((c) => {
          c.style.display = !q || c.dataset.search.includes(q) ? "" : "none";
        });
      });
    } catch (e) {
      el.innerHTML = `<div class='error'>Failed loading PMs: ${esc(e.message)}</div>`;
    }
  }

  // ---------------- Knowledge & Memory ----------------// ---------------- Knowledge & Memory ----------------// ---------------- Knowledge & Memory ----------------
  async function renderKnowledge() {
    const [globalList, pmList] = [document.getElementById("globalMemoryList"),
                                  document.getElementById("projectMemoryList")];
    globalList.innerHTML = "<div class='placeholder'>Loading global memory...</div>";
    try {
      const mem = await Api.getMemory();
      const g = mem.globalMemory || {};
      const entries = Object.entries(g);
      globalList.innerHTML = entries.length
        ? entries.map(([k, v]) => `<div class="mem-row"><span class="mem-key">${esc(k)}</span><span class="mem-val">${esc(typeof v === "string" ? v : JSON.stringify(v))}</span></div>`).join("")
        : "<div class='placeholder'>No global memory yet. Learned preferences appear here automatically.</div>";

      const pms = await Api.listPMs();
      const sel = document.getElementById("projectMemSelect");
      const cur = sel.value;
      sel.innerHTML = `<option value="">- choose project -</option>` + pms.map((p) =>
        `<option value="${esc(p.project_id)}" ${p.project_id === cur ? "selected" : ""}>${esc(p.project_id)}</option>`).join("");
      sel.onchange = () => renderProjectMemory(sel.value);
      if (cur) await renderProjectMemory(cur);
      await renderLearning();
    } catch (e) {
      globalList.innerHTML = `<div class='error'>${esc(e.message)}</div>`;
    }
  }

  async function renderProjectMemory(projectId) {
    const el = document.getElementById("projectMemoryList");
    if (!projectId) { el.innerHTML = ""; return; }
    el.innerHTML = "<div class='placeholder'>Loading project memory...</div>";
    const mem = await Api.getMemory(projectId);
    const pm = mem.projectMemory || {};
    const entries = Object.entries(pm);
    el.innerHTML = entries.length
      ? entries.map(([k, v]) => `<div class="mem-row"><span class="mem-key">${esc(k)}</span><span class="mem-val">${esc(typeof v === "string" ? v : JSON.stringify(v))}</span></div>`).join("")
      : "<div class='placeholder'>No project memory yet.</div>";
  }

  // ---------------- Phase 9: Learning System ----------------
  async function renderLearning() {
    const scopeEl = document.getElementById("learningScope");
    const listEl = document.getElementById("learningList");
    const statsEl = document.getElementById("learningStats");
    if (!listEl || !statsEl) return;
    try {
      const data = await Api.getLearning(scopeEl ? scopeEl.value : "");
      const st = data.stats || {};
      statsEl.innerHTML = [
        `<div class="learning-stat"><span class="lstat-n">${st.total ?? 0}</span><span class="lstat-l">lessons</span></div>`,
        `<div class="learning-stat"><span class="lstat-n">${(st.by_scope && st.by_scope.pm) || 0}</span><span class="lstat-l">pm</span></div>`,
        `<div class="learning-stat"><span class="lstat-n">${(st.by_scope && st.by_scope.worker) || 0}</span><span class="lstat-l">worker</span></div>`,
        `<div class="learning-stat"><span class="lstat-n">${(st.by_scope && st.by_scope.global) || 0}</span><span class="lstat-l">global</span></div>`,
        `<div class="learning-stat"><span class="lstat-n">${(st.by_confidence && st.by_confidence.HIGH) || 0}</span><span class="lstat-l">high</span></div>`,
        `<div class="learning-stat"><span class="lstat-n">${st.applied ?? 0}</span><span class="lstat-l">applied</span></div>`,
      ].join("");
      const lessons = data.lessons || [];
      listEl.innerHTML = lessons.length
        ? lessons.map((l) => `
            <div class="lesson-row">
              <div class="lesson-head">
                <span class="chip-mini ${l.confidence === "HIGH" ? "ok" : "bad"}">${esc(l.confidence)}</span>
                <span class="chip-mini ${l.scope === "global" ? "ok" : ""}">${esc(l.scope)}</span>
                <span class="lesson-key">${esc(l.lesson_key)}</span>
                <span class="lesson-owner">${esc(l.owner_id || l.pm_id)}</span>
                <span class="lesson-meta">ev ${l.evidence_count} - applied ${l.applied_count ?? 0} - ${esc(l.status)}</span>
              </div>
              <div class="lesson-content">${esc(l.content)}</div>
              ${(l.refs || []).length ? `<div class="lesson-refs">${(l.refs || []).slice(0, 5).map(r => `<code>${esc(r)}</code>`).join(" ")}</div>` : ""}
            </div>`).join("")
        : "<div class='placeholder'>No lessons yet. Reworked or failed tasks produce evidence-gated lesson candidates automatically.</div>";
    } catch (e) {
      listEl.innerHTML = `<div class='error'>${esc(e.message)}</div>`;
    }
  }

  // ---------------- Per-chat Session Pane (Virtual Office + Approvals) ----------------
  // Every chat session has its own workers, task flow and approvals, so the
  // office and the permission gates live INSIDE the chat - not as global views.
    // ---------------- Per-chat session panel (right sidebar) ----------------
  const spState = { cid: null, tasks: [], workers: [], approvals: [], vo: null, bound: false };

  function spBody(name) {
    const pane = document.getElementById("spPane" + name[0].toUpperCase() + name.slice(1));
    return pane ? pane.querySelector(".sp-body") : null;
  }

  function bindChatTabs() {
    document.querySelectorAll(".chat-tab").forEach((b) =>
      b.addEventListener("click", () => switchChatTab(b.getAttribute("data-chat-tab"))));
  }

  function switchChatTab(name) {
    document.querySelectorAll(".chat-tab").forEach((b) =>
      b.classList.toggle("active", b.getAttribute("data-chat-tab") === name));
    const brain = document.getElementById("chatBrainPane");
    const pm = document.getElementById("chatPmPane");
    if (brain) brain.style.display = name === "brain" ? "" : "none";
    if (pm) pm.style.display = name === "pm" ? "" : "none";
    if (name === "pm") renderChatPm();
  }

  function bindSessionSidebar() {
    if (spState.bound) return;
    spState.bound = true;
    document.querySelectorAll(".ss-tab").forEach((b) =>
      b.addEventListener("click", () => switchSessionTab(b.getAttribute("data-ss-tab"))));
    const tg = document.getElementById("sessionToggle");
    if (tg) tg.addEventListener("click", toggleSessionSidebar);
    const cst = document.getElementById("chatSidebarToggle");
    if (cst) cst.addEventListener("click", toggleSessionSidebar);
  }

  
  function wireWfMode() {
    const off = document.getElementById("wfModeOffice");
    const loc = document.getElementById("wfModeLocal");
    if (!off || !loc || off._wired) return;
    off._wired = true;
    const showOffice = () => {
      off.classList.add("active");
      loc.classList.remove("active");
      const lv = document.getElementById("wfLocalView");
      const ov = document.getElementById("wfOfficeView");
      if (lv) lv.classList.add("hidden");
      if (ov) ov.classList.remove("hidden");
      const wf = document.getElementById("chatWorkflow");
      if (wf) wf.style.minWidth = "";
    };
    const showLocal = () => {
      if (window.Tools && window.Tools.render) {
        try { window.Tools.render("local"); } catch (e) { console.error(e); }
      } else {
        loc.classList.remove("active");
        showOffice();
      }
    };
    off.addEventListener("click", showOffice);
    loc.addEventListener("click", showLocal);
  }
function wireWfResize() {
    const rz = document.querySelector(".wf-resizer");
    const wf = document.getElementById("chatWorkflow");
    if (!rz || !wf || wf._wfWired) return;
    wf._wfWired = true;
    const saved = localStorage.getItem("ws_split_wf");
    if (saved) wf.style.flexBasis = saved + "px";
    rz.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      rz.classList.add("dragging");
      const startX = ev.clientX;
      const startW = wf.getBoundingClientRect().width;
      const move = (me) => {
        const w = Math.max(220, Math.min(480, startW + (me.clientX - startX)));
        wf.style.flexBasis = w + "px";
        wf.style.flex = "0 0 " + w + "px";
        localStorage.setItem("ws_split_wf", String(Math.round(w)));
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

  async function renderSessionPane(conversationId) {
    wireWfMode();
    bindSessionSidebar();
    bindChatTabs();
    const sidebar = document.getElementById("sessionSidebar");
    if (!sidebar) return;
    try {
      // Open a new conversation's dock; retain a user's collapse choice on refresh.
      if (!sidebar.dataset.initialized || spState.cid !== (conversationId || null)) {
        setSessionSidebar(true);
        sidebar.dataset.initialized = "true";
      }
    } catch (e) {}
    const cid = conversationId || null;
    spState.cid = cid;
    if (!cid) {
      const msg = "<span class='muted'>Start a new chat - this session panel shows its tasks, workers, approvals and results.</span>";
      ["tasks", "workers", "approvals", "result"].forEach((n) => { const b = spBody(n); if (b) b.innerHTML = msg; });
      return;
    }
    try {
      const [tasks, vo, approvals] = await Promise.all([
        Api.listTasks(null, 100, cid),
        Api.getVirtualOffice(cid),
        Api.listApprovals(cid),
      ]);
      spState.tasks = tasks;
      spState.workers = vo.workers || [];
      spState.approvals = approvals;
      spState.vo = vo;
      refreshChatWorkflow();
      wireWfResize();
      if (window._wfTimer) clearInterval(window._wfTimer);
      window._wfTimer = setInterval(() => {
        const vc = document.getElementById("view-chat");
        if (!vc || !vc.classList.contains("active")) return;
        refreshChatWorkflow();
      }, 4000);
      renderSessionTasks();
      renderSessionWorkers();
      renderSessionApprovals();
      renderSessionResult();
    } catch (e) {
      const b = spBody("tasks");
      if (b) b.innerHTML = `<span class='error'>${esc(e.message)}</span>`;
    }
  }

  function renderSessionTasks() {
    const body = spBody("tasks");
    if (!body) return;
    const tasks = spState.tasks;
    body.innerHTML = tasks.length
      ? tasks.map((t) => `
          <div class="sp-task of-task" data-task="${t.task_id}" draggable="true">
            <span class="of-drag" title="drag to set priority">\u{29BF}</span>
            <span class="sp-task-req">${esc(t.request.slice(0, 56))}</span>
            ${stateBadge(t.state)}
          </div>`).join("")
      : "<span class='muted'>No tasks yet in this chat.</span>";
    body.querySelectorAll("[data-task]").forEach((el) =>
      el.addEventListener("click", () => openTaskDetail(el.getAttribute("data-task"))));
    makeTasksSortable(body, spState.cid);
  }

  const OF_STATUS_META = {
    idle:     { label: "idle",     cls: "idle" },
    thinking: { label: "thinking", cls: "thinking" },
    working:  { label: "working",  cls: "working" },
    waiting:  { label: "waiting",  cls: "waiting" },
    blocked:  { label: "needs you", cls: "blocked" },
    success:  { label: "success",  cls: "success" },
    offline:  { label: "offline",  cls: "offline" },
  };
  const OF_ACT_CLS = { request: "act-req", inform: "act-inf", propose: "act-prop",
                       query: "act-q", agree: "act-ok", refuse: "act-no", done: "act-done" };
  const OF_AVATARS = { researcher: "\u{1F50D}", coder: "\u{1F4BB}", documenter: "\u{1F4C4}",
                       data_analyst: "\u{1F4CA}", "w-slides": "\u{1F5BC}", docx: "\u{1F4C4}" };

  function ofAvatar(w) {
    return OF_AVATARS[w.id] || OF_AVATARS[w.worker_id] || "\u{1F916}";
  }

  // ---- Command Center (munder-difflin style, one per chat) ----
  function ccTab(name, id, active) {
    return `<button class="of-cc-tab ${active ? "active" : ""}" data-cctab="${id}">${name}</button>`;
  }

  const CC_ROW1 = [["MONITOR", "monitor"], ["TASKS", "tasks"], ["APPROVALS", "approvals"], ["TERMINAL", "terminal"]];
  const CC_ROW2 = [["GRAPH", "graph"], ["ACTIVITY", "activity"], ["MEMORY", "memory"], ["COMMANDS", "commands"], ["ASK ME", "askme"]];

  function officeFloorHTML(ws, hive, activeTab) {
    const cid = spState.cid || "";
    const msgs = (hive.messages || []).slice(-24);
    const board = (hive.board || {}).content || "";
    const tasks = spState.tasks || [];
    const approvals = spState.approvals || [];
    const logs = (hive.log || []).slice(-24);
    const desk = (w, big) => {
      const meta = OF_STATUS_META[(w.status || "idle").toLowerCase()] || OF_STATUS_META.idle;
      const overlay = w.status === "blocked" ? '<span class="of-over of-blocked">!</span>'
        : w.status === "thinking" ? '<span class="of-over of-think"><i></i><i></i><i></i></span>'
        : w.status === "success" ? '<span class="of-over of-sparkle">\u2726</span>' : "";
      return `<div class="of-desk ${big ? "of-desk-mb" : ""}" data-wid="${esc(w.id || "")}" data-wstatus="${esc(w.status || "idle")}" title="Open ${esc(w.name)} workspace">
        <div class="of-avatar">${ofAvatar(w)}${overlay}</div>
        <div class="of-name">${esc(w.name || w.id)}</div>
        <span class="of-badge of-badge-${meta.cls}">${meta.label}</span>
      </div>`;
    };
    const mb = { id: "mb", name: "Main Brain",
                 status: (spState.approvals || []).length > 0
                   ? "blocked"
                   : (hive.log || []).length ? "working" : "idle" };
    const workers = ws.slice(0, 10);
    const msgHtml = msgs.length
      ? msgs.map((m) => `
          <div class="of-msg" data-mid="${esc(m.id)}">
            <span class="of-env">\u2709\uFE0F</span>
            <span class="of-from">${esc(m.from)}</span>
            <span class="of-arrow">\u2192</span>
            <span class="of-to">${esc(m.to)}</span>
            <span class="of-act ${OF_ACT_CLS[m.act] || ""}">${esc(m.act)}</span>
            <span class="of-subj">${esc(m.subject)}</span>
            <span class="of-hop" title="message chain depth">#${m.hops || 0}</span>
          </div>`).join("")
      : '<div class="muted">No hive messages yet - brief the Main Brain, or send one below.</div>';
    const tasksHtml = tasks.length
      ? tasks.map((t) => `
          <div class="of-msg of-task" data-task="${esc(t.task_id)}" draggable="true">
            <span class="of-env">\u{1F4CB}</span>
            <span class="of-drag" title="drag to set priority">\u{29BF}</span>
            <span class="of-subj">${esc(t.request.slice(0, 60))}</span>
            <span class="of-act act-done">${esc(t.state)}</span>
          </div>`).join("")
      : '<div class="muted">No tasks in this chat yet.</div>';
    const apprHtml = approvals.length
      ? approvals.map((r) => `
          <div class="of-msg">
            <span class="of-env">\u{1F6E2}</span>
            <span class="of-subj">${esc(r.tool)}.${esc(r.action)}</span>
            <span class="of-act act-req">L${r.level}</span>
            <button class="btn-secondary btn-sm of-ap-deny" data-id="${esc(r.requestId)}">Deny</button>
            <button class="btn-primary btn-sm of-ap-ok" data-id="${esc(r.requestId)}">Approve</button>
          </div>`).join("")
      : '<div class="muted">No pending approvals in this chat.</div>';
    const logHtml = logs.length
      ? logs.map((l) => `
          <div class="of-msg of-term-line">
            <span class="of-term-ts">${esc((l.ts || l.created_at || "").toString().slice(11, 19))}</span>
            <span class="of-term-mark">\u0024</span>
            <span class="of-subj">${esc(l.event || "")}</span>
            ${l.from ? `<span class="of-from">${esc(l.from)}</span>` : ""}
            ${l.to ? `<span class="of-arrow">\u2192</span><span class="of-to">${esc(l.to)}</span>` : ""}
            ${l.act ? `<span class="of-act act-inf">${esc(l.act)}</span>` : ""}
            ${l.subject ? `<span class="of-subj">${esc(l.subject)}</span>` : ""}
          </div>`).join("")
      : '<div class="muted">No hive events yet.</div>';
    // GRAPH: task-state distribution + worker-state distribution (pure DOM bars)
    const tStates = {};
    tasks.forEach((t) => { tStates[t.state] = (tStates[t.state] || 0) + 1; });
    const wStates = {};
    [mb].concat(workers).forEach((w) => { const k = w.status || "idle"; wStates[k] = (wStates[k] || 0) + 1; });
    const tTot = tasks.length || 1;
    const tBars = Object.entries(tStates).map(([k, n]) => `
      <div class="of-grow">
        <div class="of-grow-head"><span>${esc(k)}</span><span>${n}</span></div>
        <div class="of-grow-bar"><div class="of-grow-fill" style="width:${(n / tTot * 100).toFixed(0)}%"></div></div>
      </div>`).join("") || '<div class="muted">No task states yet.</div>';
    const wTot = workers.length + 1 || 1;
    const wBars = Object.entries(wStates).map(([k, n]) => `
      <div class="of-grow">
        <div class="of-grow-head"><span>${esc(k)}</span><span>${n}</span></div>
        <div class="of-grow-bar"><div class="of-grow-fill" style="width:${(n / wTot * 100).toFixed(0)}%"></div></div>
      </div>`).join("");
    const graphHtml = `<div class="of-graph-sec"><div class="of-pane-title">TASK STATES</div>${tBars}</div>
      <div class="of-graph-sec"><div class="of-pane-title">AGENT STATES</div>${wBars}</div>`;
    const boardHtml = board
      ? `<pre class="of-board-text">${esc(board)}</pre>`
      : '<div class="muted">No shared plan yet. The PM scribes the blackboard here as work is assigned.</div>';
    const opts = workers.map((w) => `<option value="${esc(w.id)}">${esc(w.name)}</option>`).join("");
    const strip = [mb].concat(workers).map((w) => {
      const meta = OF_STATUS_META[(w.status || "idle").toLowerCase()] || OF_STATUS_META.idle;
      return `<div class="of-strip-card" data-wid="${esc(w.id || "")}">
        <span class="of-avatar of-strip-av">${ofAvatar(w)}</span>
        <div class="of-strip-info">
          <div class="of-strip-name">${esc(w.name || w.id)}</div>
          <span class="of-badge of-badge-${meta.cls}">${meta.label}</span>
        </div>
        <button class="btn-secondary btn-sm of-talk" data-wid="${esc(w.id || "")}" title="Send this agent a message">talk</button>
      </div>`;
    }).join("");
    // ctx estimate (display only): messages ~2k, tasks ~4k tokens each
    const ctxK = Math.min(128, Math.round((msgs.length * 2 + tasks.length * 4) / 1024 * 10) / 10 || 1);
    const ctxPct = Math.min(100, Math.round((msgs.length * 2 + tasks.length * 4) / 131072 * 1000) / 10);
    const ccRow = (row, at) => row.map(([n, id]) => ccTab(n, id, activeTab === id)).join("");
    const ccTabsHtml = `<div class="of-cc-tabs">${ccRow(CC_ROW1, activeTab)}</div>
      <div class="of-cc-tabs of-cc-tabs2">${ccRow(CC_ROW2, activeTab)}</div>`;
    const commandsHtml = `
      <button class="of-cmd btn-secondary btn-sm" data-cmd="askall">\u{1F5E3} Ask all workers for status</button>
      <button class="of-cmd btn-secondary btn-sm" data-cmd="mbsync">\u{1F9E0} Sync Main Brain memory</button>
      <button class="of-cmd btn-secondary btn-sm" data-cmd="approvals">\u{1F6E2} Pending approvals</button>
      <button class="of-cmd btn-secondary btn-sm" data-cmd="newtask">\u{1F4CB} New task in chat</button>`;
    const askHtml = `<div class="of-ask">
        <input id="ofAskMe" class="of-input" placeholder="Ask the Main Brain… (jumps to the composer)" />
        <button id="ofAskGo" class="btn-primary btn-sm">Go</button>
      </div>`;
    return `
      <div class="of-wrap">
        <div class="of-floor">
          <div class="of-row of-row-mb">${desk(mb, true)}</div>
          ${workers.length ? `<div class="of-row">${workers.map((w) => desk(w)).join("")}</div>` : ""}
        </div>
        <div class="of-cc">
          <div class="of-cc-main">
            <div class="of-cc-topline">
              <span class="of-cc-tag">auto mode</span>
              <span class="of-cc-tag">memory: minimal</span>
              <span class="of-cc-tag" title="estimated MB context for this chat">ctx: ${ctxK}k/128k (${ctxPct}%)</span>
            </div>
            ${ccTabsHtml}
            <div class="of-cc-body" id="ofCcBody">
              <div class="of-cc-page" data-ccpage="monitor">${msgHtml}</div>
              <div class="of-cc-page" data-ccpage="tasks" style="display:none;">${tasksHtml}</div>
              <div class="of-cc-page" data-ccpage="approvals" style="display:none;">${apprHtml}</div>
              <div class="of-cc-page" data-ccpage="terminal" style="display:none;">${logHtml}</div>
              <div class="of-cc-page" data-ccpage="graph" style="display:none;">${graphHtml}</div>
              <div class="of-cc-page" data-ccpage="activity" style="display:none;"><div class="muted">Loading activity…</div></div>
              <div class="of-cc-page" data-ccpage="memory" style="display:none;"><div class="muted">Loading memory…</div></div>
              <div class="of-cc-page" data-ccpage="commands" style="display:none;">${commandsHtml}</div>
              <div class="of-cc-page" data-ccpage="askme" style="display:none;">${askHtml}</div>
            </div>
            <div class="of-cc-queue">
              <span class="of-cc-qlabel">QUEUE \u00B7 send to</span>
              <select id="ofTo" class="of-sel">${opts}</select>
              <select id="ofAct" class="of-sel of-sel-act">
                <option value="request">request</option><option value="query">query</option>
                <option value="propose">propose</option><option value="inform">inform</option>
                <option value="done">done</option>
              </select>
              <input id="ofSubject" class="of-input" placeholder="subject…" />
              <button id="ofSend" class="btn-primary btn-sm">Send</button>
            </div>
          </div>
          <div class="of-pane of-pane-board">
            <div class="of-pane-title">BLACKBOARD <span class="muted">(PM scribe)</span></div>
            <div id="ofBoardText">${boardHtml}</div>
            <textarea id="ofBoardEdit" class="of-board-edit" style="display:none;" placeholder="Shared plan…">${esc(board)}</textarea>
            <div class="of-board-actions">
              <button id="ofBoardEditBtn" class="btn-secondary btn-sm">Edit</button>
              <button id="ofBoardSave" class="btn-primary btn-sm" style="display:none;">Save</button>
              <button id="ofBoardCancel" class="btn-secondary btn-sm" style="display:none;">Cancel</button>
            </div>
          </div>
        </div>
        <div class="of-strip">${strip}</div>
      </div>`;
  }

  async function loadCcDynamic(body, cid) {
    // ACTIVITY: audit timeline tail
    const actPage = body.querySelector('[data-ccpage="activity"]');
    if (actPage) {
      try {
        const rows = await Api.getAuditLogs(15);
        const mine = cid ? rows.filter((r) => !r.task_id || (spState.tasks || []).some((t) => t.task_id === r.task_id)) : rows;
        actPage.innerHTML = mine.length
          ? mine.slice(-15).map((r) => `
              <div class="of-msg of-term-line">
                <span class="of-term-ts">${esc((r.ts || "").toString().slice(11, 19))}</span>
                <span class="of-term-mark">\u25B8</span>
                <span class="of-from">${esc(r.actor || r.role || "?")}</span>
                <span class="of-act act-inf">${esc(r.action)}</span>
                <span class="of-subj">${esc((r.reason || "").toString().slice(0, 40))}</span>
              </div>`).join("")
          : '<div class="muted">No activity in this chat yet.</div>';
      } catch (e) { actPage.innerHTML = `<span class='error'>${esc(e.message)}</span>`; }
    }
    // MEMORY: MB vault auto-notes
    const memPage = body.querySelector('[data-ccpage="memory"]');
    if (memPage) {
      try {
        const tree = await Api.vaultTree("mb");
        const auto = tree.files || tree || [];
        let preview = "No MB memory yet - run Sync Main Brain memory.";
        try {
          const g = await Api.vaultRead("mb", "_auto/global-memory.md");
          preview = String(g.content || g.text || "").slice(0, 160);
        } catch (e) { /* keep default */ }
        memPage.innerHTML = `<div class="of-pane-title">MAIN BRAIN MEMORY</div>
          <div class="of-mem-note">${esc(preview)}</div>
          <div class="of-mem-counts">${auto.length} auto-notes in vault</div>
          <button class="btn-secondary btn-sm of-cmd" data-cmd="mbsync">Sync now</button>`;
      } catch (e) { memPage.innerHTML = `<span class='error'>${esc(e.message)}</span>`; }
    }
  }

function bindOfficeFloor(body, hive, cid) {
    body.querySelectorAll(".of-desk").forEach((d) => {
      d.addEventListener("click", () => {
        const wid = d.dataset.wid;
        if (!wid || wid === "mb") return;
        Workers.openStudio(wid);
      });
    });
    // drag-to-prioritize inside the TASKS page
    makeTasksSortable(body.querySelector('[data-ccpage="tasks"]'), cid);
    // command center tabs (two rows, remember active across heartbeat re-renders)
    body.querySelectorAll(".of-cc-tab").forEach((t) => t.addEventListener("click", () => {
      body.querySelectorAll(".of-cc-tab").forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      const page = t.dataset.cctab;
      window._ofActiveCcTab = page;
      body.querySelectorAll(".of-cc-page").forEach((p) => { p.style.display = p.dataset.ccpage === page ? "" : "none"; });
      if (page === "activity" || page === "memory") loadCcDynamic(body, cid);
    }));
    // command shortcuts
    body.querySelectorAll(".of-cmd").forEach((b) => b.addEventListener("click", async () => {
      const cmd = b.dataset.cmd;
      if (cmd === "askall") {
        const ws = spState.workers || [];
        if (!ws.length) { App.toast("No workers in this chat yet."); return; }
        let n = 0;
        for (const w of ws) {
          await Api.hiveSend({ conversationId: cid, from: "mb", to: w.id,
                               act: "query", subject: "What are you up to?" });
          n++;
        }
        App.toast(`Asked ${n} worker(s) for status`);
        await renderSessionWorkers();
      } else if (cmd === "mbsync") {
        const r = await Api.mbSync();
        App.toast(`MB memory synced: ${(r && r.written || []).length} notes`);
        await renderSessionWorkers();
      } else if (cmd === "approvals") {
        body.querySelectorAll(".of-cc-tab").forEach((x) => x.classList.remove("active"));
        const t = body.querySelector('.of-cc-tab[data-cctab="approvals"]');
        if (t) { t.classList.add("active"); window._ofActiveCcTab = "approvals"; }
        body.querySelectorAll(".of-cc-page").forEach((p) => { p.style.display = p.dataset.ccpage === "approvals" ? "" : "none"; });
      } else if (cmd === "newtask") {
        const inp = document.getElementById("chatInput");
        if (inp) { inp.focus(); inp.scrollIntoView({ block: "center" }); }
      }
    }));
    // ASK ME: jump to the composer
    const askGo = body.querySelector("#ofAskGo");
    if (askGo) askGo.addEventListener("click", () => {
      const v = body.querySelector("#ofAskMe").value.trim();
      if (!v) return;
      const inp = document.getElementById("chatInput");
      if (inp) {
        const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value") ||
                  Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
        s.set.call(inp, v);
        inp.dispatchEvent(new Event("input", { bubbles: true }));
        inp.focus();
        body.querySelector("#ofAskMe").value = "";
      }
    });
    // approvals quick actions
    body.querySelectorAll(".of-ap-ok").forEach((b) => b.addEventListener("click", async () => {
      await Api.resolveApproval(b.dataset.id, true);
      App.toast("Approved");
      await renderSessionWorkers();
    }));
    body.querySelectorAll(".of-ap-deny").forEach((b) => b.addEventListener("click", async () => {
      await Api.resolveApproval(b.dataset.id, false, "Denied from command center");
      App.toast("Denied");
      await renderSessionWorkers();
    }));
    // strip cards: click card -> studio; talk -> target the composer
    body.querySelectorAll(".of-strip-card").forEach((c) => c.addEventListener("click", (e) => {
      const wid = c.dataset.wid;
      if (e.target.closest(".of-talk")) return;
      if (wid && wid !== "mb") Workers.openStudio(wid);
    }));
    body.querySelectorAll(".of-talk").forEach((b) => b.addEventListener("click", () => {
      const wid = b.dataset.wid;
      const sel = body.querySelector("#ofTo");
      if (sel) sel.value = wid;
      const subj = body.querySelector("#ofSubject");
      if (subj) subj.focus();
    }));
    const sendBtn = body.querySelector("#ofSend");
    if (sendBtn) sendBtn.addEventListener("click", async () => {
      const to = body.querySelector("#ofTo").value;
      const act = body.querySelector("#ofAct").value;
      const subject = body.querySelector("#ofSubject").value.trim();
      if (!to || !subject) { App.toast("Pick a worker and write a subject."); return; }
      const senderEl = body.querySelector(`.of-desk[data-wid="mb"]`);
      const recvEl = body.querySelector(`.of-desk[data-wid="${CSS.escape(to)}"]`);
      if (senderEl && recvEl) flyEnvelope(body, senderEl, recvEl);
      const r = await Api.hiveSend({ conversationId: cid, from: "mb", to, act, subject });
      if (r && r.error) { App.toast(r.error); return; }
      body.querySelector("#ofSubject").value = "";
      await renderSessionWorkers();
    });
    const editBtn = body.querySelector("#ofBoardEditBtn");
    if (editBtn) editBtn.addEventListener("click", () => {
      body.querySelector("#ofBoardText").style.display = "none";
      body.querySelector("#ofBoardEdit").style.display = "block";
      editBtn.style.display = "none";
      body.querySelector("#ofBoardSave").style.display = "";
      body.querySelector("#ofBoardCancel").style.display = "";
    });
    const saveBtn = body.querySelector("#ofBoardSave");
    if (saveBtn) saveBtn.addEventListener("click", async () => {
      const text = body.querySelector("#ofBoardEdit").value;
      await Api.hiveBoardPut(cid, text, "pm");
      await renderSessionWorkers();
    });
    const cancelBtn = body.querySelector("#ofBoardCancel");
    if (cancelBtn) cancelBtn.addEventListener("click", () => {
      body.querySelector("#ofBoardText").style.display = "";
      body.querySelector("#ofBoardEdit").style.display = "none";
      editBtn.style.display = "";
      saveBtn.style.display = "none";
      cancelBtn.style.display = "none";
    });
  }

  async function refreshSessionTasks() {
    if (!spState.cid) return;
    spState.tasks = await Api.listTasks(null, 100, spState.cid);
    renderSessionTasks();
    renderSessionWorkers();
  }

  function makeTasksSortable(container, cid) {
    if (!container || !cid) return;
    let dragEl = null;
    container.querySelectorAll(".of-task").forEach((row) => {
      row.addEventListener("dragstart", (e) => {
        dragEl = row; row.classList.add("dragging");
        e.dataTransfer.effectAllowed = "move";
      });
      row.addEventListener("dragend", () => row.classList.remove("dragging"));
      row.addEventListener("dragover", (e) => {
        e.preventDefault();
        if (!dragEl || row === dragEl) return;
        const r = row.getBoundingClientRect();
        container.insertBefore(dragEl, e.clientY < r.top + r.height / 2 ? row : row.nextSibling);
      });
      row.addEventListener("drop", async (e) => {
        e.preventDefault();
        if (!dragEl) return;
        const ids = [...container.querySelectorAll(".of-task")].map((r) => r.dataset.task);
        await Api.reorderTasks(cid, ids);
        App.toast("Priority saved");
        await refreshSessionTasks();
      });
    });
  }

  function flyEnvelope(body, senderEl, recvEl) {
    const floor = body.querySelector(".of-floor");
    if (!floor) return;
    const env = document.createElement("div");
    env.className = "of-envelope-fly";
    env.textContent = "\u2709\uFE0F";
    const sr = senderEl.getBoundingClientRect();
    const rr = recvEl.getBoundingClientRect();
    const fr = floor.getBoundingClientRect();
    const sx = sr.left - fr.left + sr.width / 2;
    const sy = sr.top - fr.top + sr.height / 2;
    const tx = rr.left - fr.left + rr.width / 2;
    const ty = rr.top - fr.top + rr.height / 2;
    env.style.setProperty("--sx", `${sx}px`);
    env.style.setProperty("--sy", `${sy}px`);
    env.style.setProperty("--tx", `${tx}px`);
    env.style.setProperty("--ty", `${ty}px`);
    floor.appendChild(env);
    setTimeout(() => env.remove(), 1100);
  }

function renderSessionWorkers() {
    const body = spBody("workers");
    if (!body) return;
    if (window._ofTimer) { clearInterval(window._ofTimer); window._ofTimer = null; }
    const ws = spState.workers;
    if (!ws.length) {
      body.innerHTML = "<span class='muted'>Workers used by this chat will appear here - start a task to assemble the team.</span>";
      return;
    }
    const cid = spState.cid;
    Api.hiveState(cid).then((hive) => {
      if (!document.body.contains(body)) return;
      spState.hive = hive;
      // live heartbeat: overwrite desk statuses from the hive roster
      const live = {};
      (hive.workers || []).forEach((w) => { live[w.id || w.worker_id] = w.status; });
      ws.forEach((w) => { const st = live[w.id] || live[w.worker_id]; if (st) w.status = st; });
      const at = window._ofActiveCcTab || "monitor";
      body.innerHTML = officeFloorHTML(ws, hive, at);
      bindOfficeFloor(body, hive, cid);
      loadCcDynamic(body, cid);
      window._ofTimer = setInterval(() => {
        if (document.getElementById("spPaneWorkers") &&
            document.getElementById("spPaneWorkers").classList.contains("active")) {
          renderSessionWorkers();
        }
      }, 4000);
    }).catch(() => {
      body.innerHTML = ws.map((w) => `
          <div class="sp-worker">
            <span class="vo-avatar">${ofAvatar(w)}</span>
            <div class="sp-worker-info">
              <div class="sp-worker-name">${esc(w.name)}</div>
              <div class="muted">${esc(w.id)} , ${esc(w.status)} , QA pass ${(((w.stats && w.stats.qa_pass_rate) || 0) * 100).toFixed(0)}% , ${(w.stats && w.stats.tasks_completed) || 0} tasks</div>
            </div>
            <button class="btn-secondary sp-studio-btn" data-wid="${esc(w.id)}">Open workspace</button>
          </div>`).join("");
      body.querySelectorAll(".sp-studio-btn").forEach((b) => {
        b.addEventListener("click", () => Workers.openStudio(b.dataset.wid));
      });
    });
  }

  function renderSessionApprovals() {
    const body = spBody("approvals");
    if (!body) return;
    const list = spState.approvals;
    body.innerHTML = list.length
      ? list.map((r) => `
          <div class="approval-row sp-approval">
            <div class="ap-head">
              <span class="verdict-tag">L${r.level}</span>
              <strong>${esc(r.tool)}.${esc(r.action)}</strong>
              <span class="muted">by ${esc(r.workerId)}</span>
            </div>
            <div class="ap-params mono">${esc(JSON.stringify(r.params || {}))}</div>
            <div class="ap-actions">
              <button class="btn-danger ap-deny" data-id="${esc(r.requestId)}">Deny</button>
              <button class="btn-primary ap-approve" data-id="${esc(r.requestId)}">Approve</button>
            </div>
          </div>`).join("")
      : "<span class='muted'>No pending approvals in this chat.</span>";
    body.querySelectorAll(".ap-approve").forEach((b) => b.addEventListener("click", async () => {
      await Api.resolveApproval(b.getAttribute("data-id"), true);
      App.toast("Approved");
      renderSessionPane(spState.cid);
    }));
    body.querySelectorAll(".ap-deny").forEach((b) => b.addEventListener("click", async () => {
      await Api.resolveApproval(b.getAttribute("data-id"), false, "Denied from chat session");
      App.toast("Denied");
      renderSessionPane(spState.cid);
    }));
  }

  function renderSessionResult() {
    const body = spBody("result");
    if (!body) return;
    const tasks = spState.tasks;
    if (!tasks.length) {
      body.innerHTML = "<span class='muted'>No results to visualize yet.</span>";
      return;
    }
    const done = tasks.filter((t) => String(t.state || "").toUpperCase() === "COMPLETED").length;
    const qa = tasks.map((t) => t.qa_score).filter((v) => v != null);
    const avgQa = qa.length ? qa.reduce((a, b) => a + b, 0) / qa.length : null;
    const byState = {};
    tasks.forEach((t) => { byState[t.state] = (byState[t.state] || 0) + 1; });
    const stateOrder = Object.keys(byState).sort((a, b) => byState[b] - byState[a]);
    const maxN = Math.max(1, ...Object.values(byState));
    const artifacts = tasks.reduce((n, t) => n + (t.artifacts || []).length, 0);
    body.innerHTML = `
      <div class="rv-stats">
        <div class="rv-stat"><div class="rv-n">${tasks.length}</div><div class="rv-k">tasks</div></div>
        <div class="rv-stat"><div class="rv-n">${done}</div><div class="rv-k">done</div></div>
        <div class="rv-stat"><div class="rv-n">${avgQa == null ? "-" : avgQa.toFixed(2)}</div><div class="rv-k">avg QA</div></div>
        <div class="rv-stat"><div class="rv-n">${artifacts}</div><div class="rv-k">artifacts</div></div>
      </div>
      <div class="rv-section-label">STATE DISTRIBUTION</div>
      <div class="rv-bars">
        ${stateOrder.map((st) => `
          <div class="rv-bar-row">
            <span class="rv-bar-label">${esc(st)}</span>
            <div class="rv-bar-track"><div class="rv-bar-fill rv-fill-state" style="width:${Math.round((byState[st] / maxN) * 100)}%"></div></div>
            <span class="rv-bar-n">${byState[st]}</span>
          </div>`).join("")}
      </div>
      <div class="rv-section-label">QA SCORE PER TASK</div>
      ${tasks.map((t) => `
        <div class="rv-task" data-task="${t.task_id}">
          <div class="rv-task-head"><span class="sp-task-req">${esc(t.request.slice(0, 40))}</span>${stateBadge(t.state)}</div>
          <div class="rv-bar-track"><div class="rv-bar-fill ${t.qa_score == null ? "rv-fill-na" : (t.qa_score >= 0.8 ? "rv-fill-good" : "rv-fill-mid")}" style="width:${t.qa_score == null ? 4 : Math.round(t.qa_score * 100)}%"></div></div>
          <div class="rv-task-foot"><span class="muted">QA ${t.qa_score == null ? "n/a" : t.qa_score.toFixed(2)} , ${(t.artifacts || []).length} artifacts</span></div>
        </div>`).join("")}
    `;
    body.querySelectorAll("[data-task]").forEach((el) =>
      el.addEventListener("click", () => openTaskDetail(el.getAttribute("data-task"))));
  }

  function switchSessionTab(name) {
    document.querySelectorAll(".ss-tab").forEach((b) =>
      b.classList.toggle("active", b.getAttribute("data-ss-tab") === name));
    document.querySelectorAll(".sp-tab-pane").forEach((p) =>
      p.classList.toggle("active", p.id === "spPane" + name[0].toUpperCase() + name.slice(1)));
    if (name === "project") renderSessionProject();
  }

  async function renderSessionProject() {
    const body = document.getElementById("spProjectBody");
    if (!body) return;
    try {
      const [projects, tasks] = await Promise.all([
        Api.listProjects(), Api.listTasks(null, 100, spState.cid),
      ]);
      const active = (tasks || []).filter((t) => t.project_id);
      const projIds = [...new Set(active.map((t) => t.project_id))];
      body.innerHTML = `
        <div class="sp-label">PROJECTS LINKED TO THIS CHAT</div>
        ${projIds.map((pid) => {
          const pj = (projects || []).find((x) => x.id === pid);
          return `<div class="sp-project-row">${esc(pj ? pj.name : pid)} <span class="muted">${esc(pid)}</span></div>`;
        }).join("") || "<div class='muted'>No project linked yet - tasks created in this chat run under their own task group.</div>"}
        <div class="sp-label" style="margin-top:12px;">ALL PROJECTS</div>
        ${(projects || []).map((pj) => `
          <div class="sp-project-row" data-pid="${esc(pj.id)}">
            <span>${esc(pj.name)}</span><span class="muted">${esc(pj.status || "")}</span>
          </div>`).join("") || "<div class='muted'>No projects yet.</div>"}
        <button class="btn-secondary" id="openAllProjectsBtn" style="margin-top:10px;">Open Projects &amp; PMs view</button>`;
      const ob = document.getElementById("openAllProjectsBtn");
      if (ob) ob.addEventListener("click", () => App.openProjectsView());
      body.querySelectorAll(".sp-project-row[data-pid]").forEach((el) => {
        el.addEventListener("click", () => App.openProject(el.dataset.pid));
      });
    } catch (e) {
      body.innerHTML = `<span class='error'>${esc(e.message)}</span>`;
    }
  }

  function toggleSessionSidebar() {
    const sb = document.getElementById("sessionSidebar");
    if (!sb) return;
    const open = sb.classList.toggle("ss-open");
    const bar = document.getElementById("spResize");
    if (bar) bar.classList.toggle("show", open);
    const tg = document.getElementById("sessionToggle");
    if (tg) { tg.textContent = open ? "Collapse" : "Expand"; tg.setAttribute("aria-expanded", String(open)); tg.setAttribute("aria-label", open ? "Collapse session details" : "Expand session details"); }
    const cst = document.getElementById("chatSidebarToggle");
    if (cst) { cst.textContent = open ? "Hide details" : "Session details"; cst.setAttribute("aria-expanded", String(open)); }
    try { localStorage.setItem("wd_ss_open", open ? "1" : "0"); } catch (e) {}
  }

  function setSessionSidebar(open) {
    const sb = document.getElementById("sessionSidebar");
    if (!sb) return;
    sb.classList.toggle("ss-open", open);
    const bar = document.getElementById("spResize");
    if (bar) bar.classList.toggle("show", open);
    const tg = document.getElementById("sessionToggle");
    if (tg) { tg.textContent = open ? "Collapse" : "Expand"; tg.setAttribute("aria-expanded", String(open)); tg.setAttribute("aria-label", open ? "Collapse session details" : "Expand session details"); }
    const cst = document.getElementById("chatSidebarToggle");
    if (cst) { cst.textContent = open ? "Hide details" : "Session details"; cst.setAttribute("aria-expanded", String(open)); }
  }

  // ---------------- Settings ----------------
  async function renderSettings() {
    const el = document.getElementById("settingsContainer");
    el.innerHTML = "<div class='placeholder'>Loading settings...</div>";
    try {
      const s = await Api.getSettings();
      const mr = s.model_router || {};
      const prov = mr.providers || {};
      el.innerHTML = `
        <div class="settings-grid">
          <div class="setting-card"><div class="sc-label">ENGINE</div>
            <div class="sc-row"><span>max rework cycles</span><code>${esc(s.max_rework_cycles)}</code></div>
            <div class="sc-row"><span>checkpoint keep</span><code>${esc(s.checkpoint_keep)}</code></div>
            <div class="sc-row"><span>lesson promote evidence</span><code>${esc(s.lesson_promote_min_evidence)}</code></div>
            <div class="sc-row"><span>auto-approve (demo)</span><code>${esc(String(s.auto_approve))}</code></div>
          </div>
          <div class="setting-card"><div class="sc-label">MODEL ROUTER (Phase 8)</div>
            <div class="sc-row"><span>instant</span><code>${esc(mr.instant || "-")}</code></div>
            <div class="sc-row"><span>expert</span><code>${esc(mr.expert || "-")}</code></div>
            <div class="sc-row"><span>worker</span><code>${esc(mr.worker || "-")}</code></div>
            <div class="sc-row"><span>local endpoint</span><code>${esc(mr.local_endpoint || "-")}</code></div>
            <div class="sc-row"><span>local model</span><code>${esc(prov.local_model || "-")}</code></div>
            <div class="sc-row"><span>local configured</span><code>${esc(String(!!prov.local_configured))}</code></div>
            <div class="sc-row"><span>OpenRouter configured</span><code>${esc(String(mr.openrouter_configured))}</code></div>
            <div class="sc-row"><span>ChatAnywhere (free relay)</span><code>${esc(String(!!prov.chatanywhere_configured))}</code></div>
            <div class="sc-row"><span>chatanywhere endpoint</span><code>${esc(prov.chatanywhere_endpoint || "-")}</code></div>
            <div class="sc-row"><span>chatanywhere model</span><code>${esc(prov.chatanywhere_model || "-")}</code></div>
            <div class="sc-row" style="align-items:flex-start;"><span>chatanywhere key</span>
              <span style="display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;">
                <input id="caKeyInput" type="password" placeholder="sk-..." style="width:210px;padding:4px 8px;border:1px solid var(--border,#3a3f4b);border-radius:6px;background:#E9F2FF;color:#31415F;font-size:12px;" value="" />
                <button id="caSaveBtn" style="padding:4px 12px;border-radius:6px;border:1px solid #2e8b57;background:#2e8b5722;color:#7ee2a8;font-size:12px;cursor:pointer;">Save</button>
              </span>
            </div>
            <div class="sc-row"><span>free key</span><code>register at chatanywhere.tech, bind GitHub</code></div>
            <div class="sc-row" id="caSaveResult" style="min-height:0;"></div>
            <div class="sc-row"><span>routes recorded</span><code>${(mr.stats && mr.stats.total) ?? "-"}</code></div>
            <div class="sc-row"><span>by provider</span><code>${esc(JSON.stringify((mr.stats && mr.stats.by_provider) || {}))}</code></div>
          </div>
          <div class="setting-card"><div class="sc-label">RECENT ROUTES</div>
            ${(mr.recent || []).map((r) => `
              <div class="tl-row"><span class="tl-ts muted">${esc(r.ts.slice(11, 19))}</span>
                <span class="tl-actor">${esc(r.worker_id)}</span>
                <code>${esc(r.provider)} \u2192 ${esc(r.model)}</code>
                <span class="muted">${esc(r.reason)}</span></div>`).join("")
              || "<div class='muted'>no routing decisions yet</div>"}
          </div>
          <div class="setting-card" style="grid-column:1/-1;"><div class="sc-label">TEST MODEL CALL - Phase 8.2 (route \u2192 invoke \u2192 fallback)</div>
            <textarea id="mcPrompt" rows="2" placeholder="Prompt for the model...">Summarize the idea of a personal AI operating system in one sentence.</textarea>
            <div class="mc-controls">
              <label>capability
                <select id="mcCap">
                  <option value="default">default</option><option value="coding">coding</option>
                  <option value="research">research</option><option value="vision">vision</option>
                </select>
              </label>
              <label>complexity
                <select id="mcComplex">
                  <option value="simple">simple</option><option value="normal" selected>normal</option>
                  <option value="complex">complex</option>
                </select>
              </label>
              <label>privacy
                <select id="mcPrivacy">
                  <option value="public">public</option><option value="sensitive">sensitive</option>
                </select>
              </label>
              <button id="mcRun" class="btn-primary">Route &amp; Call</button>
            </div>
            <div id="mcResult" class="mc-result"><span class="muted">Run a call to see the routed decision, the invoked model and the response.</span></div>
          </div>
          <div class="setting-card"><div class="sc-label">DATA</div>
            <div class="sc-row"><span>db</span><code>${esc(s.db_path)}</code></div>
            <div class="sc-row"><span>project dir</span><code>${esc(s.project_dir)}</code></div>
            <div class="sc-row"><span>app url</span><code>${esc(s.app_url || "-")}</code></div>
          </div>
          <div class="setting-card"><div class="sc-label">RECORD COUNTS</div>
            ${Object.entries(s.counts || {}).map(([k, n]) => `<div class="sc-row"><span>${esc(k)}</span><code>${n}</code></div>`).join("")}
          </div>
          <div class="setting-card" style="grid-column:1/-1;"><div class="sc-label">CACHE & HISTORY</div>
            <div class="muted" style="margin-bottom:8px;">Clears chat sessions, tasks, approvals, audit log and learning lessons. Worker profiles, vault notes and workspace files are preserved.</div>
            <button class="btn-danger" id="clearHistoryBtn">Clear all cache &amp; history</button>
            <div id="clearHistoryResult" class="muted" style="margin-top:8px;"></div>
          </div>
        </div>`;
      wireModelCall();
      const caBtn = document.getElementById("caSaveBtn");
      if (caBtn) caBtn.addEventListener("click", async () => {
        const key = (document.getElementById("caKeyInput") || {}).value || "";
        const res = await Api.saveChatanywhereKey(key.trim());
        const out = document.getElementById("caSaveResult");
        if (out) out.textContent = res.ok ? (res.chatanywhere_configured ? "Saved - ChatAnywhere provider active (hot-applied, no restart)." : "Saved - key cleared, ChatAnywhere disabled.") : ("Error: " + (res.error || "unknown"));
      });
      const chb = document.getElementById("clearHistoryBtn");
      if (chb) chb.addEventListener("click", async () => {
        if (!confirm("Clear all chat history, tasks, approvals, audit and learning lessons? This cannot be undone.")) return;
        const res = await Api.clearHistory("all");
        document.getElementById("clearHistoryResult").textContent = "Cleared: " + (res.wiped || []).join(", ");
        setTimeout(() => location.reload(), 800);
      });
    } catch (e) {
      el.innerHTML = `<div class='error'>${esc(e.message)}</div>`;
    }
  }

  function wireModelCall() {
    const run = document.getElementById("mcRun");
    if (!run) return;
    run.addEventListener("click", async () => {
      const out = document.getElementById("mcResult");
      out.innerHTML = "<span class='muted'>Routing & calling…</span>";
      try {
        const res = await Api.callModelRouter({
          prompt: document.getElementById("mcPrompt").value,
          capability: document.getElementById("mcCap").value,
          complexity: document.getElementById("mcComplex").value,
          privacy: document.getElementById("mcPrivacy").value,
        });
        const d = res.decision;
        const c = res.call;
        out.innerHTML = `
          <div class="mc-decision">route \u2192 <code>${esc(d.provider)}:${esc(d.model)}</code>
            <span class="muted">${esc(d.reason)}</span>${d.privacy_sensitive ? " <span class='chip-mini warn'>PRIVATE</span>" : ""}</div>
          ${c.ok
            ? `<div class="mc-call"><span class="chip-mini ok">OK</span> <code>${esc(c.provider)} \u2192 ${esc(c.model)}</code>
                 <span class="muted">${c.duration_ms} ms${c.fallback_used ? " \u00b7 fallback used" : ""}</span></div>
               <div class="mc-text">${esc(c.text)}</div>`
            : `<div class="mc-call"><span class="chip-mini bad">FAILED</span> all attempts failed</div>
               <div class="mc-attempts">${c.attempts.map((a) => `
                 <div class="tl-row"><code>${esc(a.provider)} \u2192 ${esc(a.model)}</code>
                   <span class="${a.ok ? "ok" : "error"}">${a.ok ? "ok" : esc(String(a.error || "error"))}</span></div>`).join("")}</div>`}
        `;
      } catch (e) {
        out.innerHTML = `<span class='error'>${esc(e.message)}</span>`;
      }
    });
  }


  function wfStatusClass(st) {
    const x = String(st || "").toLowerCase();
    if (x.includes("work") || x.includes("think")) return "working";
    if (x.includes("wait") || x.includes("block")) return "waiting";
    if (x.includes("done") || x.includes("complete")) return "completed";
    return "";
  }

  async function refreshChatWorkflow() {
    const desks = document.getElementById("wfDesks");
    const mbStatus = document.getElementById("wfMbStatus");
    if (!desks) return;
    const ws = spState.workers || [];
    let status = "idle";
    try {
      const hv = await Api.hiveState(spState.cid);
      const roster = hv && hv.roster ? hv.roster : [];
      if (roster.length) {
        ws.forEach((w) => {
          const r = roster.find((x) => x.agent_id === w.id || x.agent_id === w.worker_id);
          if (r) w.status = r.status || w.status;
        });
        const mb = roster.find((x) => x.agent_id === "mb" || x.agent_id === "main_brain");
        if (mb) status = mb.status || status;
        else if (roster.some((x) => x.status && x.status !== "idle")) status = "working";
      } else if (ws.some((w) => w.status && w.status !== "idle")) {
        status = "working";
      }
    } catch (e) { /* keep local status */ }
    if (mbStatus) {
      mbStatus.textContent = status;
      mbStatus.classList.toggle("wf-working", String(status).includes("work"));
    }
    // Worker desks are rendered exclusively by Chat.refreshOfficeFloor
    // (live states + SBR routing reasons). This function keeps the MB status.
  }

  async function renderChatPm() {
    const pane = document.getElementById("chatPmPane");
    if (!pane) return;
    const cid = spState.cid;
    if (!cid) {
      pane.innerHTML = "<div class='muted'>Start a chat to see its Project Manager workspace.</div>";
      return;
    }
    try {
      const [projects, tasks] = await Promise.all([
        Api.listProjects(), Api.listTasks(null, 100, cid),
      ]);
      const ts = tasks || [];
      const active = ts.filter((t) => t.project_id);
      const projIds = [...new Set(active.map((t) => t.project_id))];
      const projNames = projIds.map((pid) => {
        const pj = (projects || []).find((x) => x.id === pid);
        return pj ? pj.name : pid;
      });
      const pmName = "Project Manager";
      const pmSub = projNames.length
        ? `manages project(s): ${projNames.join(", ")}`
        : "awaits a project - tasks created here run under their own task group";
      const done = ts.filter((t) => String(t.state || "").toUpperCase() === "COMPLETED").length;
      const work = ts.filter((t) => !["COMPLETED", "FAILED", "CANCELLED"].includes(String(t.state || "").toUpperCase())).length;
      const fail = ts.filter((t) => ["FAILED", "CANCELLED"].includes(String(t.state || "").toUpperCase())).length;
      pane.innerHTML = `
        <div class="pm-card">
          <div class="pm-avatar">PM</div>
          <div class="pm-meta">
            <div class="pm-name">${esc(pmName)}</div>
            <div class="pm-sub">${esc(pmSub)}</div>
          </div>
          <div class="pm-stat">
            <span>tasks ${ts.length}</span><span>done ${done}</span><span>working ${work}</span><span>failed ${fail}</span>
          </div>
        </div>
        <div class="sp-label">TASKS UNDER THIS PM</div>
        ${ts.map((t) => `
          <div class="pm-task-row" data-task="${esc(t.task_id)}">
            <span class="pm-task-state ${esc(String(t.state || "").toUpperCase())}">${esc(t.state || "PENDING")}</span>
            <span style="flex:1;min-width:0;">${esc(t.request || t.request_text || "")}</span>
            <span class="muted">QA ${t.qa_score != null ? Math.round(t.qa_score * 100) + "%" : "-"}</span>
          </div>`).join("") || "<div class='muted'>No tasks in this chat yet - describe a goal to the Main Brain.</div>"}
        <div class="sp-label">DELIVERABLES</div>
        ${ts.flatMap((t) => (t.artifacts || []).map((a) => a.path)).filter(Boolean).map((pth) => `
          <div class="pm-task-row"><span style="font-size:10px;">📄</span><span style="font-size:11px;word-break:break-all;">${esc(pth)}</span></div>`).join("")
          || "<div class='muted'>No deliverables yet.</div>"}
        <div class="sp-label">QA HISTORY</div>
        <div class="muted" style="font-size:11px;">${ts.length ? "Last QA-2 verdicts: " + ts.map((t) => `${esc(t.state)} (${t.qa_cycles || 0} cycle${(t.qa_cycles||0) === 1 ? "" : "s"})`).join("; ") : "Nothing to verify yet."}</div>`;
      pane.querySelectorAll(".pm-task-row[data-task]").forEach((row) => {
        row.addEventListener("click", () => {
          const tid = row.dataset.task;
          const t = ts.find((x) => x.task_id === tid);
          if (t && typeof openTaskDetail === "function") openTaskDetail(t);
        });
      });
    } catch (e) {
      pane.innerHTML = `<span class='error'>${esc(e.message)}</span>`;
    }
  }

  return { renderProjects, renderTasks, renderPMs, renderKnowledge, renderLearning,
           renderSettings, openTaskDetail, renderSessionPane, switchSessionTab, toggleSessionSidebar,
           refreshChatWorkflow, renderChatPm };
})();
