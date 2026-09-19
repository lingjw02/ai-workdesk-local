/* ============================================================
 * workers.js - Worker Registry, Worker Studio, Design New Worker
 * Phase 11: click a worker -> personal live workspace (simulated
 * system: code worker opens their code page, research worker shows
 * their browser view), design new worker from a GitHub skill URL,
 * merge into similar workers, and edit existing workers.
 * ============================================================ */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const notify = (msg, ok = true) => {
    const el = document.getElementById("wdStatus");
    if (el) { el.textContent = msg; el.className = ok ? "vault-status ok" : "vault-status err"; }
  };

  const studioState = { workerId: null, data: null, activeFile: null, files: [] };

  function skillsOf(w) { return (w.skills || []).map((s) => s.capability || s.name).filter(Boolean); }
  function toolsOf(w) { return (w.tools || []).map((t) => t.tool).filter(Boolean); }

  /* ---------------- Registry ---------------- */
  async function renderRegistry() {
    const grid = $("workerRegistryGrid");
    if (!grid) return;
    grid.innerHTML = `<div class="placeholder">Loading worker registry...</div>`;
    let workers = [];
    try { workers = await Api.listWorkers(); }
    catch (e) { grid.innerHTML = `<span class="error">${esc(e.message)}</span>`; return; }
    if (!workers.length) {
      grid.innerHTML = `<div class="placeholder">No workers yet - design one from a GitHub skill.</div>`;
      return;
    }
    grid.innerHTML = workers.map((w) => {
      const status = (w.status || "idle").toLowerCase();
      const stats = `${w.tasks_completed || 0} done , ${w.qa_passed || 0} QA pass , ${(w.failure_rate ?? 0).toFixed(2)} fail`;
      const studio = (w.studio_type || w.role_class || "WORKER").toLowerCase();
      const icon = studio === "code" ? "👨‍💻" : studio === "research" ? "🔎" :
                   studio === "docs" ? "✍️" : studio === "sheets" ? "📊" :
                   studio === "media" ? "🎬" : studio === "design" ? "🎨" : "🤖";
      return `
      <div class="wreg-card" data-wid="${esc(w.worker_id)}">
        <div class="wreg-head">
          <div class="wreg-avatar">${icon}</div>
          <div>
            <div class="wreg-name">${esc(w.name || w.worker_id)}</div>
            <div class="wreg-role">${esc(w.role_class || "WORKER")}</div>
          </div>
          <span class="wreg-status ${status}">${status}</span>
        </div>
        <div class="wreg-skills">${skillsOf(w).slice(0, 5).map((s) => `<span class="wreg-skill">${esc(s)}</span>`).join("") || ""}</div>
        <div class="wreg-tools">${toolsOf(w).slice(0, 6).map((t) => `<span class="wreg-tool">${esc(t)}</span>`).join("") || ""}</div>
        <div class="wreg-stats">${stats}</div>
        <div class="wreg-actions">
          <button class="btn-primary wreg-edit">Edit Profile</button>
        </div>
      </div>`;
    }).join("");

    grid.querySelectorAll(".wreg-card").forEach((card) => {
      const wid = card.dataset.wid;
      card.querySelector(".wreg-edit").addEventListener("click", () => openDesign(wid));
    });
    renderSkillMarket();
  }

  async function renderSkillMarket() {
    const grid = document.getElementById("skillMarketGrid");
    const cnt = document.getElementById("smCount");
    if (!grid) return;
    let data = null;
    try { data = await Api.skillMarket(); }
    catch (e) { grid.innerHTML = `<span class="error">Failed loading skill market: ${esc(e.message)}</span>`; return; }
    const skills = data.skills || [];
    if (cnt) cnt.textContent = `${skills.length} skill(s) in registry`;
    if (!skills.length) { grid.innerHTML = `<div class="placeholder">No skills registered yet.</div>`; return; }
    grid.innerHTML = skills.map((s) => `
      <div class="sm-card">
        <div class="sm-head">
          <span class="sm-name">${esc(s.name)}</span>
          <span class="sm-cap">${esc(s.capability)}</span>
        </div>
        <div class="sm-owners">
          ${s.owners.length
            ? s.owners.map((o) => `<span class="sm-owner">✓ ${esc(o.name)}</span>`).join("")
            : `<span class="muted">not owned by any worker</span>`}
        </div>
        ${s.installable.length ? `
        <div class="sm-install">
          <select class="sm-select" data-skill="${esc(s.name)}">
            <option value="">Install onto…</option>
            ${s.installable.map((w2) => `<option value="${esc(w2.worker_id)}">${esc(w2.name)}</option>`).join("")}
          </select>
          <button class="btn-primary btn-sm sm-go" data-skill="${esc(s.name)}" disabled>Install</button>
        </div>` : ""}
      </div>`).join("");
    grid.querySelectorAll(".sm-select").forEach((sel) => {
      sel.addEventListener("change", () => {
        const go = grid.querySelector(`.sm-go[data-skill="${CSS.escape(sel.dataset.skill)}"]`);
        if (go) go.disabled = !sel.value;
      });
    });
    grid.querySelectorAll(".sm-go").forEach((b) => {
      b.addEventListener("click", async () => {
        const sel = grid.querySelector(`.sm-select[data-skill="${CSS.escape(b.dataset.skill)}"]`);
        if (!sel || !sel.value) return;
        b.disabled = true; b.textContent = "Installing…";
        try {
          const res = await Api.installSkill(sel.value, b.dataset.skill);
          if (res && res.error) { App.toast("Install failed: " + res.error); b.disabled = false; b.textContent = "Install"; return; }
          App.toast(`Skill ${b.dataset.skill} installed → worker ready for SBR routing`);
          await renderRegistry();
          await renderSkillMarket();
        } catch (err) {
          App.toast("Install failed: " + err.message);
          b.disabled = false; b.textContent = "Install";
        }
      });
    });
  }

  function openStudio(workerId) {
    studioState.workerId = workerId;
    App.showView("worker-studio");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    const btn = document.getElementById("navWorkersBtn");
    if (btn) btn.classList.add("active");
    renderStudio(workerId);
  }

  function openDesign(existingId) {
    App.showView("worker-design");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    const btn = document.getElementById("navDesignBtn");
    if (btn) btn.classList.add("active");
    renderDesign(existingId);
  }

  /* ---------------- Studio ---------------- */
  async function renderStudio(workerId) {
    const panel = $("workerStudioPanel");
    panel.innerHTML = `<div class="placeholder">Loading worker workspace...</div>`;
    let data;
    try { data = await Api.workerStudio(workerId); }
    catch (e) { panel.innerHTML = `<span class="error">${esc(e.message)}</span>`; return; }
    if (data.error) { panel.innerHTML = `<span class="error">${esc(data.error)}</span>`; return; }
    studioState.data = data;
    const w = data.worker || {};
    const studio = data.studio_type || "general";
    $("studioTitle").textContent = `${w.name || workerId} - ${studio} workspace`;
    $("studioHeaderActions").innerHTML = `
      <button class="btn-secondary" id="studioBackBtn">← Registry</button>
      <button class="btn-secondary" id="studioEditBtn">Edit Worker</button>`;
    $("studioBackBtn").addEventListener("click", () => {
      App.showView("workers");
      document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
      const b = document.getElementById("navWorkersBtn"); if (b) b.classList.add("active");
      renderRegistry();
    });
    $("studioEditBtn").addEventListener("click", () => openDesign(workerId));

    const identity = `
      <div class="studio-identity">
        <div class="wreg-avatar big">${esc(w.role_class || "WORKER")[0]}</div>
        <div>
          <div class="wreg-name">${esc(w.name || workerId)}</div>
          <div class="wreg-role">${esc(w.role_class || "WORKER")} , ${esc(studio)} studio</div>
          <div class="wreg-stats">${w.tasks_completed || 0} completed , ${w.qa_passed || 0} QA pass , ${(w.failure_rate ?? 0).toFixed(2)} fail rate</div>
        </div>
      </div>`;

    panel.innerHTML = `
      ${identity}
      <div class="studio-layout">
        <div class="studio-live">
          <div class="studio-live-title">LIVE VIEW - ${esc(studio.toUpperCase())}</div>
          <div id="studioLiveBody"><div class="placeholder">Loading live view...</div></div>
        </div>
        <aside class="studio-side">
          <div class="studio-side-block">
            <div class="ws-file-title">SKILLS</div>
            <div class="wreg-skills">${skillsOf(w).map((s) => `<span class="wreg-skill">${esc(s)}</span>`).join("") || "<span class='muted'>-</span>"}</div>
          </div>
          <div class="studio-side-block">
            <div class="ws-file-title">TOOLS & PERMISSIONS</div>
            ${toolsOf(w).map((t) => `<div class="studio-tool"><span>${esc(t)}</span><span class="muted">read/write</span></div>`).join("") || "<span class='muted'>-</span>"}
          </div>
          <div class="studio-side-block">
            <div class="ws-file-title">RECENT TASKS</div>
            ${(data.tasks || []).map((t) => `<div class="studio-task"><span class="muted">${esc(t.state)}</span> ${esc(t.request.slice(0, 48))}</div>`).join("") || "<span class='muted'>No tasks yet</span>"}
          </div>
          <div class="studio-side-block">
            <div class="ws-file-title">ACTIVITY FEED</div>
            ${(data.feed || []).map((f) => `<div class="studio-feed"><span class="muted">${esc((f.ts || "").slice(11, 19))}</span> ${esc(f.action || f.tool || "")}</div>`).join("") || "<span class='muted'>No audited activity yet</span>"}
          </div>
        </aside>
      </div>`;

    const live = $("studioLiveBody");
    if (studio === "code") renderCodeLive(live);
    else if (studio === "research") renderResearchLive(live);
    else if (studio === "docs") renderDocsLive(live);
    else if (studio === "sheets") renderSheetsLive(live);
    else renderGeneralLive(live, studio);
  }

  async function listFiles(filterPrefix, exts) {
    const r = await Api.getWorkspaceFiles();
    return (r.files || []).filter((f) =>
      (filterPrefix ? f.path.startsWith(filterPrefix) : true) &&
      (!exts || exts.includes(f.path.split(".").pop().toLowerCase())));
  }

  async function renderCodeLive(live) {
    live.innerHTML = `
      <div class="code-toolbar">
        <input id="stCodeFile" placeholder="code/file.py" />
        <button class="btn-primary" id="stCodeLoad">Open</button>
        <button class="btn-primary" id="stCodeRun">Run</button>
      </div>
      <div id="stCodeFileList" class="ws-file-list" style="max-height:140px;margin-bottom:8px;"></div>
      <textarea id="stCodeEditor" spellcheck="false" style="width:100%;height:300px;background:#F0F5FF;color:#31415F;border:1px solid rgba(255,255,255,0.1);border-radius:10px;padding:12px;font-family:Consolas,monospace;font-size:13px;"></textarea>
      <div id="stCodeOutput" style="margin-top:8px;background:rgba(0,0,0,0.25);border-radius:10px;padding:10px;font-family:Consolas,monospace;font-size:13px;white-space:pre-wrap;"></div>`;
    const files = await listFiles("code/");
    studioState.files = files;
    const fl = $("stCodeFileList");
    fl.innerHTML = files.map((f) => `<div class="ws-file-row" data-p="${esc(f.path)}">${esc(f.path)}</div>`).join("") ||
      `<div class="muted" style="padding:6px;">No code files yet - type below and Run.</div>`;
    fl.querySelectorAll(".ws-file-row").forEach((el) => el.addEventListener("click", async () => {
      const r = await Api.readWorkspace(el.dataset.p);
      if (!r.error) { $("stCodeFile").value = el.dataset.p; $("stCodeEditor").value = r.content; }
    }));
    $("stCodeLoad").addEventListener("click", async () => {
      const p = $("stCodeFile").value.trim();
      if (!p) return;
      const r = await Api.readWorkspace(p);
      if (r.error) notify(r.error, false);
      else $("stCodeEditor").value = r.content;
    });
    $("stCodeRun").addEventListener("click", async () => {
      const out = $("stCodeOutput");
      out.textContent = "Running...";
      const r = await Api.runCode($("stCodeEditor").value || "print('empty editor')");
      out.textContent = `exit ${r.returncode}\n${r.stdout || ""}${r.stderr ? "\n" + r.stderr : ""}`;
    });
  }

  function renderResearchLive(live) {
    const feed = studioState.data.feed || [];
    live.innerHTML = `
      <div class="browser-monitor">
        <div class="bm-bar">
          <span class="bm-indicator"></span><span>Research worker browser session</span>
        </div>
        <div class="bm-url-row">
          <input id="bmUrl" placeholder="https://example.com - open in the worker's browser view" />
          <button class="btn-primary" id="bmGo">Browse</button>
          <button class="btn-secondary" id="bmExample">example.com</button>
        </div>
        <div class="bm-viewport">
          <iframe id="bmFrame" title="worker browser view" sandbox="allow-scripts allow-same-origin"></iframe>
          <div class="bm-placeholder" id="bmPlaceholder">
            The researcher's browser view. Enter a URL to see what it sees,<br/>
            or check the activity feed below.
          </div>
        </div>
        <div class="ws-file-title" style="margin-top:10px;">BROWSING ACTIVITY</div>
        <div class="bm-feed">
          ${feed.map((f) => `<div class="bm-feed-item"><span class="muted">${esc((f.ts || "").slice(11, 19))}</span> ${esc(f.action || f.tool || "activity")}</div>`).join("") || "<div class='muted'>No browsing activity recorded yet.</div>"}
        </div>
      </div>`;
    const frame = $("bmFrame");
    const ph = $("bmPlaceholder");
    const go = (u) => {
      if (!/^https?:\/\//.test(u)) u = "https://" + u;
      frame.src = u;
      ph.style.display = "none";
    };
    $("bmGo").addEventListener("click", () => go($("bmUrl").value.trim()));
    $("bmExample").addEventListener("click", () => { $("bmUrl").value = "https://example.com"; go("https://example.com"); });
    $("bmUrl").addEventListener("keydown", (e) => { if (e.key === "Enter") go($("bmUrl").value.trim()); });
  }

  async function renderDocsLive(live) {
    live.innerHTML = `
      <div class="code-toolbar">
        <input id="stDocFile" placeholder="docs/file.html" />
        <button class="btn-primary" id="stDocOpen">Open</button>
      </div>
      <div id="stDocList" class="ws-file-list" style="max-height:140px;margin-bottom:8px;"></div>
      <textarea id="stDocEditor" spellcheck="false" style="width:100%;height:300px;background:#fbfaf6;color:#1a1b1c;border-radius:10px;padding:12px;font-size:14px;"></textarea>`;
    const files = await listFiles("docs/", ["html", "md", "txt"]);
    const fl = $("stDocList");
    fl.innerHTML = files.map((f) => `<div class="ws-file-row" data-p="${esc(f.path)}">${esc(f.path)}</div>`).join("") ||
      `<div class="muted" style="padding:6px;">No documents yet.</div>`;
    fl.querySelectorAll(".ws-file-row").forEach((el) => el.addEventListener("click", async () => {
      const r = await Api.readWorkspace(el.dataset.p);
      if (!r.error) { $("stDocFile").value = el.dataset.p; $("stDocEditor").value = r.content; }
    }));
    $("stDocOpen").addEventListener("click", async () => {
      const p = $("stDocFile").value.trim(); if (!p) return;
      const r = await Api.readWorkspace(p);
      if (r.error) notify(r.error, false); else $("stDocEditor").value = r.content;
    });
  }

  async function renderSheetsLive(live) {
    live.innerHTML = `
      <div class="code-toolbar">
        <input id="stSheetFile" placeholder="sheets/data.csv" />
        <button class="btn-primary" id="stSheetOpen">Open</button>
      </div>
      <div id="stSheetList" class="ws-file-list" style="max-height:140px;margin-bottom:8px;"></div>
      <textarea id="stSheetEditor" spellcheck="false" style="width:100%;height:300px;background:#F0F5FF;color:#31415F;border-radius:10px;padding:12px;font-family:Consolas,monospace;font-size:13px;" placeholder="CSV grid - edit rows here"></textarea>`;
    const files = await listFiles("sheets/", ["csv"]);
    const fl = $("stSheetList");
    fl.innerHTML = files.map((f) => `<div class="ws-file-row" data-p="${esc(f.path)}">${esc(f.path)}</div>`).join("") ||
      `<div class="muted" style="padding:6px;">No sheets yet.</div>`;
    fl.querySelectorAll(".ws-file-row").forEach((el) => el.addEventListener("click", async () => {
      const r = await Api.readWorkspace(el.dataset.p);
      if (!r.error) { $("stSheetFile").value = el.dataset.p; $("stSheetEditor").value = r.content; }
    }));
    $("stSheetOpen").addEventListener("click", async () => {
      const p = $("stSheetFile").value.trim(); if (!p) return;
      const r = await Api.readWorkspace(p);
      if (r.error) notify(r.error, false); else $("stSheetEditor").value = r.content;
    });
  }

  function renderGeneralLive(live, studio) {
    const w = studioState.data.worker || {};
    live.innerHTML = `
      <div class="studio-general">
        <div class="ws-file-title">ROLE DESCRIPTION</div>
        <p class="muted">${esc(w.description || "A general-purpose AI employee with the skills and tools listed on the right.")}</p>
        <div class="ws-file-title" style="margin-top:14px;">TOOLS AVAILABLE</div>
        <div class="wreg-skills">${toolsOf(w).map((t) => `<span class="wreg-tool">${esc(t)}</span>`).join("") || "<span class='muted'>filesystem only</span>"}</div>
        <div class="ws-file-title" style="margin-top:14px;">NEXT STEPS</div>
        <div class="studio-general-next">
          <button class="btn-secondary" onclick="Workers.jump('code')">Code Studio</button>
          <button class="btn-secondary" onclick="Workers.jump('docs')">Documents</button>
          <button class="btn-secondary" onclick="Workers.jump('sheets')">Sheets</button>
          <button class="btn-secondary" onclick="Workers.jump('slides')">Slides</button>
          <button class="btn-secondary" onclick="Workers.jump('media')">Media</button>
        </div>
      </div>`;
  }

  function jump(view) {
    const btnMap = { code: "navCodeBtn", docs: "navDocsBtn", sheets: "navSheetsBtn",
                     slides: "navSlidesBtn", media: "navMediaBtn" };
    const b = document.getElementById(btnMap[view]);
    if (b) b.click();
  }

  /* ---------------- Design New Worker ---------------- */
  function renderDesign(existingId) {
    const panel = $("workerDesignPanel");
    panel.innerHTML = `
      <div class="design-wizard">
        <div class="design-step-title">1 , Paste a GitHub skill URL</div>
        <div class="muted" style="margin-bottom:8px;">
          The WorkDesk reads the skill definition (SKILL.md), designs the worker for you, and
          checks whether an existing worker should absorb it instead of creating a duplicate.
        </div>
        <div class="design-url-row">
          <input id="designUrl" placeholder="https://github.com/owner/repo  (or a path with /tree/branch/...)" />
          <button class="btn-primary" id="designAnalyze">Design Worker</button>
        </div>
        <div id="designResult" class="design-result"></div>
        <div id="wdStatus" class="vault-status"></div>
      </div>`;
    const analyze = async () => {
      const url = $("designUrl").value.trim();
      const out = $("designResult");
      if (!url) { notify("Paste a GitHub URL first", false); return; }
      out.innerHTML = `<div class="placeholder">Fetching ${esc(url)} and reading SKILL.md...</div>`;
      let r;
      try { r = await Api.designWorker(url); }
      catch (e) { out.innerHTML = `<span class="error">${esc(e.message)}</span>`; return; }
      if (r.error) {
        out.innerHTML = `<div class="notice">${esc(r.detail || r.error)}</div>`;
        return;
      }
      if (r.candidates) {
        // Repo has no root SKILL.md: the backend scanned sub-folders for us.
        out.innerHTML = `
          <div class="design-step-title">2 , SKILL.md found in sub-folders (${r.candidates.length})</div>
          <div class="muted" style="margin:6px 0 8px;">${esc(r.detail)} - click one to design the worker from it.</div>
          <div class="design-candidates">
            ${r.candidates.map((c) => `
              <button class="design-cand" data-path="${esc(c.path)}">
                <span class="dc-name">${esc(c.name)}</span>
                <span class="dc-path muted">${esc(c.path)}</span>
              </button>`).join("")}
          </div>`;
        out.querySelectorAll(".design-cand").forEach((b) => b.addEventListener("click", async () => {
          const path = b.getAttribute("data-path");
          out.innerHTML = `<div class="placeholder">Reading ${esc(path)}...</div>`;
          const r2 = await Api.designWorker(url, path);
          if (r2.error) { out.innerHTML = `<div class="notice">${esc(r2.detail || r2.error)}</div>`; return; }
          renderCandidate(r2);
        }));
        return;
      }
      renderCandidate(r);
    };
    const renderCandidate = (r) => {
      const out = $("designResult");
      const c = r.candidate;
      out.innerHTML = `
        <div class="design-candidate">
          <div class="design-step-title">2 , Designed worker</div>
          <div class="design-edit-row"><label>Name</label><input id="dcName" value="${esc(c.name)}" /></div>
          <div class="design-edit-row"><label>Role</label><input id="dcRole" value="${esc(c.role)}" /></div>
          <div class="design-edit-row"><label>Studio</label><select id="dcStudio">
            ${["code", "research", "docs", "sheets", "slides", "pdf", "media", "design", "general"]
              .map((t) => `<option ${t === c.studio_type ? "selected" : ""}>${t}</option>`).join("")}
          </select></div>
          <div class="design-edit-row"><label>Description</label><textarea id="dcDesc" rows="3">${esc(c.description)}</textarea></div>
          <div class="design-edit-row"><label>Skills</label><input id="dcSkills" value="${esc(c.skills.map((s) => s.name).join(", "))}" /></div>
          <div class="design-edit-row"><label>Tools</label><input id="dcTools" value="${esc(c.tools.map((t) => t.tool).join(", "))}" /></div>
          <div class="design-edit-row"><label>Personality</label><input id="dcPersona" value="${esc((c.personality.traits || []).join(", "))}" /></div>
          <div class="design-edit-row"><label>Behavior rules</label><input id="dcRules" value="${esc((c.behavior_rules || []).join("; "))}" /></div>
          <div class="design-source muted">skill source: ${esc(c.skill_source || "")}</div>
        </div>
        <div class="design-step-title">3 , Similar workers</div>
        <div class="design-matches">
          ${(r.matches || []).map((m) => `
            <label class="design-match">
              <input type="radio" name="mergeTarget" value="${esc(m.worker_id)}" />
              <span><strong>${esc(m.name)}</strong> - ${m.score} similarity , overlap: ${esc(m.overlap.join(", "))}</span>
            </label>`).join("") || "<div class='muted'>No similar workers - this will be created as new.</div>"}
        </div>
        <div class="design-actions">
          <button class="btn-primary" id="dcCreate">Create New Worker</button>
          <button class="btn-secondary" id="dcMerge">Merge into Selected</button>
        </div>`;
      const buildProfile = () => ({
        name: $("dcName").value.trim(),
        role_class: $("dcRole").value.trim().toUpperCase().replace(/[^A-Z]/g, "_") || "WORKER",
        studio_type: $("dcStudio").value,
        description: $("dcDesc").value.trim(),
        skills: $("dcSkills").value.split(",").map((s) => s.trim()).filter(Boolean).map((s) => ({
          name: s, primary: true, capability: s.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
          tools_required: ["FILESYSTEM"],
        })),
        tools: $("dcTools").value.split(",").map((t) => t.trim()).filter(Boolean).map((t) => ({
          tool: t, permissions: { read: true, write: true },
        })),
        personality: { traits: $("dcPersona").value.split(",").map((s) => s.trim()).filter(Boolean), tone: "professional", communication_style: "concise status updates" },
        behavior_rules: $("dcRules").value.split(";").map((s) => s.trim()).filter(Boolean),
        permissions: {},
        memory_rules: { group_memory: true, own_experience: true, cross_project: "NEVER" },
      });
      $("dcCreate").addEventListener("click", async () => {
        const res = await Api.applyWorker(buildProfile(), "create");
        if (res.ok) { notify(`Worker created: ${res.worker_id}`); openStudio(res.worker_id); }
        else notify(res.error || "create failed", false);
      });
      $("dcMerge").addEventListener("click", async () => {
        const sel = document.querySelector('input[name="mergeTarget"]:checked');
        if (!sel) { notify("Select a worker to merge into", false); return; }
        const res = await Api.applyWorker(buildProfile(), "merge", sel.value);
        if (res.ok) { notify(`Merged into ${sel.value}`); openStudio(res.worker_id || sel.value); }
        else notify(res.error || "merge failed", false);
      });
    };
    $("designAnalyze").addEventListener("click", analyze);
    $("designUrl").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });
    if (existingId) {
      // edit mode: prefill from an existing worker
      (async () => {
        const r = await Api.workerStudio(existingId);
        if (r.error) return;
        const w = r.worker || {};
        $("designUrl").value = `edit://${existingId}`;
        $("designUrl").disabled = true;
        const c = {
          name: w.name, role: w.role_class, studio_type: r.studio_type,
          description: w.description || "",
          skills: (w.skills || []).map((s) => s.name || s.capability),
          tools: (w.tools || []).map((t) => t.tool),
          personality: { traits: (w.personality || {}).traits || [] },
          behavior_rules: w.behavior_rules || [],
        };
        $("designResult").innerHTML = `
          <div class="design-candidate">
            <div class="design-step-title">2 , Edit worker <span class="muted">(${esc(existingId)})</span></div>
            <div class="design-edit-row"><label>Name</label><input id="dcName" value="${esc(c.name)}" /></div>
            <div class="design-edit-row"><label>Role</label><input id="dcRole" value="${esc(c.role)}" /></div>
            <div class="design-edit-row"><label>Studio</label><select id="dcStudio">
              ${["code", "research", "docs", "sheets", "slides", "pdf", "media", "design", "general"]
                .map((t) => `<option ${t === r.studio_type ? "selected" : ""}>${t}</option>`).join("")}
            </select></div>
            <div class="design-edit-row"><label>Description</label><textarea id="dcDesc" rows="3">${esc(c.description)}</textarea></div>
            <div class="design-edit-row"><label>Skills</label><input id="dcSkills" value="${esc(c.skills.join(", "))}" /></div>
            <div class="design-edit-row"><label>Tools</label><input id="dcTools" value="${esc(c.tools.join(", "))}" /></div>
            <div class="design-edit-row"><label>Personality</label><input id="dcPersona" value="${esc(c.personality.traits.join(", "))}" /></div>
            <div class="design-edit-row"><label>Behavior rules</label><input id="dcRules" value="${esc(c.behavior_rules.join("; "))}" /></div>
          </div>
          <div class="design-actions"><button class="btn-primary" id="dcUpdate">Save Changes</button></div>`;
        $("dcUpdate").addEventListener("click", async () => {
          const patch = {
            name: $("dcName").value.trim(),
            description: $("dcDesc").value.trim(),
            skills: $("dcSkills").value.split(",").map((s) => s.trim()).filter(Boolean).map((s) => ({
              name: s, primary: true, capability: s.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
              tools_required: ["FILESYSTEM"],
            })),
            tools: $("dcTools").value.split(",").map((t) => t.trim()).filter(Boolean).map((t) => ({
              tool: t, permissions: { read: true, write: true },
            })),
            personality: { traits: $("dcPersona").value.split(",").map((s) => s.trim()).filter(Boolean), tone: "professional", communication_style: "concise status updates" },
            behavior_rules: $("dcRules").value.split(";").map((s) => s.trim()).filter(Boolean),
          };
          const res = await Api.updateWorker(existingId, patch);
          if (res.ok) { notify("Worker updated"); openStudio(existingId); }
          else notify(res.error || "update failed", false);
        });
      })();
    }
  }

  window.Workers = { renderRegistry, openStudio, openDesign, renderStudio, renderDesign, jump };
})();
