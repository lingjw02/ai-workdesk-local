const App = (() => {
  let collapsed = false;
  let currentApprovalRequestId = null;

  function toast(msg) {
    const el = document.createElement("div");
    el.className = "toast";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  const SCENE_NAMES = {
    dashboard: "HOME",
    chat: "CONVERSATION",
    workers: "WORKERS",
    "worker-design": "WORKER CREATOR",
    "worker-studio": "WORKER STUDIO",
    pms: "PROJECT MANAGERS",
    vault: "MEMORY VAULT",
    timer: "UTILITIES / TIME",
    calc: "UTILITIES / CALC",
    code: "CODE STUDIO",
    suite: "OFFICE SUITE",
    media: "MEDIA LIBRARY",
    remote: "REMOTE DEVICE",
    audit: "OS AUDIT",
    settings: "SETTINGS",
    workspace: "WORKSPACE",
  };
  function updateYStatus(name) {
    const title = SCENE_NAMES[name] || name;
    const scene = document.getElementById("ysScene");
    if (scene) scene.textContent = title;
    const heading = document.getElementById("studioPageTitle");
    if (heading) heading.textContent = title.toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
    const hint = document.getElementById("ysCmd");
    if (hint) hint.textContent = name === "chat" ? "Enter to send · Shift + Enter for a new line" : "Ctrl + K to find a page or conversation";
    document.dispatchEvent(new CustomEvent("studio:view", { detail: name }));
  }
  function showView(name) {
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    const target = document.getElementById(`view-${name}`);
    if (target) target.classList.add("active");
    updateYStatus(name);
  }

  function icon(kind) {
    const m = { chat: "i-message", project: "i-folder", worker: "i-users", audit: "i-scroll" }[kind];
    return m ? `<svg class="ico-svg" aria-hidden="true"><use href="#${m}"/></svg>` : "•";
  }

  async function refreshSidebar() {
    try {
      const [chats, projects] = await Promise.all([Api.listConversations(), Api.listProjects()]);
      const chatList = document.getElementById("chatList");
      chatList.innerHTML = chats.length
        ? chats.map((c) => `<div class="side-item" data-chat="${c.id}">
            <span class="ico">${icon("chat")}</span><span class="label">${escapeHtml(c.title || "Untitled")}</span>
            <button class="side-del" data-del="${c.id}" title="Delete conversation">✕</button></div>`).join("")
        : `<div class="side-empty label">No chats yet</div>`;
      chatList.querySelectorAll("[data-chat]").forEach((el) => {
        el.addEventListener("click", (e) => {
          if (e.target.classList.contains("side-del")) return;
          openChat(el.getAttribute("data-chat"));
        });
      });
      chatList.querySelectorAll(".side-del").forEach((el) => {
        el.addEventListener("click", async (e) => {
          e.stopPropagation();
          const id = el.getAttribute("data-del");
          await Api.deleteConversation(id);
          toast("Conversation deleted");
          await refreshSidebar();
          if (Chat.getConversationId() === id) await Chat.startNew();
        });
      });

      const projList = document.getElementById("projectList");
      if (projList) projList.innerHTML = projects.length
        ? projects.map((p) => `<div class="side-item" data-project="${p.id}"><span class="ico">${icon("project")}</span><span class="label">${escapeHtml(p.name || "Untitled")}</span></div>`).join("")
        : `<div class="side-empty label">No workspaces yet</div>`;
      if (projList) projList.querySelectorAll("[data-project]").forEach((el) => {
        el.addEventListener("click", () => openProject(el.getAttribute("data-project")));
      });
    } catch (e) {
      console.error("Sidebar refresh error:", e);
    }
  }

  function markActiveSidebar(kind, id) {
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    if (kind === "chat") {
      const el = document.querySelector(`[data-chat="${id}"]`);
      if (el) el.classList.add("active");
    } else if (kind === "project") {
      const el = document.querySelector(`[data-project="${id}"]`);
      if (el) el.classList.add("active");
    }
  }

  async function openChat(id) {
    showView("chat");
    await Chat.load(id);
    markActiveSidebar("chat", id);
  }

  async function openProject(id) {
    showView("workspace");
    await Workspace.load(id);
    markActiveSidebar("project", id);
  }

  function wireYuimiTop() { /* Navigation is owned by the studio sidebar. */ }

  async function openWorkersView() {
    showView("workers");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    document.getElementById("navWorkersBtn").classList.add("active");
    await Workers.renderRegistry();
  }

  async function openAuditView() {
    showView("audit");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    document.getElementById("navAuditBtn").classList.add("active");
    await renderAuditLogs();
  }

  async function renderWorkersRegistry() {
    const grid = document.getElementById("workerRegistryGrid");
    grid.innerHTML = "<div class='placeholder'>Loading worker employees...</div>";
    try {
      const workers = await Api.listWorkers();
      if (!workers.length) {
        grid.innerHTML = "<div class='placeholder'>No workers yet - design one from a GitHub skill.</div>";
        return;
      }
      grid.innerHTML = workers.map(w => {
        const skills = (w.skills || []).map(s => s.skill_id || s.name || "");
        const tools = (w.tools || []).map(t => typeof t === "string" ? t : (t.tool || ""));
        return `
        <div class="worker-card">
          <div class="vo-desk-top">
            <span class="vo-avatar">🤖</span>
            <div class="vo-worker-info">
              <div class="vo-name">${App.escapeHtml(w.name)}</div>
              <div class="vo-role">${App.escapeHtml(w.worker_id)} , ${App.escapeHtml(w.status)}</div>
            </div>
          </div>
          <div class="wc-skills">${skills.map(s => `<span class="chip-mini">${App.escapeHtml(s)}</span>`).join("") || "<span class='muted'>no skills</span>"}</div>
          <div style="font-size:12px;color:var(--muted)">
            <strong>Role:</strong> ${App.escapeHtml(w.role_class || "WORKER")}<br>
            <strong>Allowed Tools:</strong> ${tools.join(", ") || "-"}<br>
            <strong>Behavior:</strong> ${App.escapeHtml((w.behavior_rules || []).join("; ")) || "-"}
          </div>
          <div class="vo-stats-mini">
            <span>QA Pass: ${((w.qa_pass_rate || 0) * 100).toFixed(0)}%</span>
            <span>Tasks: ${w.tasks_completed}</span>
            <span>Triggered: ${w.times_triggered}</span>
            <span>Fail rate: ${((w.failure_rate || 0) * 100).toFixed(0)}%</span>
          </div>
        </div>`;
      }).join("");
    } catch (e) {
      grid.innerHTML = `<div class='error'>Failed loading workers: ${e.message}</div>`;
    }
  }

  async function renderAuditLogs() {
    const container = document.getElementById("auditLogContainer");
    container.innerHTML = "<div class='placeholder'>Loading audit entries...</div>";
    try {
      const logs = await Api.getAuditLogs(60);
      if (!logs.length) {
        container.innerHTML = "<div class='placeholder'>No audit events recorded yet.</div>";
        return;
      }
      container.innerHTML = logs.map(l => `
        <div class="audit-item">
          <div class="audit-item-top">
            <span>Actor: <strong>${l.actor}</strong> (${l.role})</span>
            <span>${l.timestamp}</span>
          </div>
          <div class="audit-event">${l.eventType}</div>
          <div style="margin-top:4px;color:var(--muted);white-space:pre-wrap;">${JSON.stringify(l.details, null, 2)}</div>
        </div>
      `).join("");
    } catch (e) {
      container.innerHTML = `<div class='error'>Failed loading logs: ${e.message}</div>`;
    }
  }

  // Per-chat session pane: this conversation's own office + approvals.
  function refreshSessionPane(conversationId) {
    const cid = conversationId === undefined ? Chat.getConversationId() : conversationId;
    Views.renderSessionPane(cid);
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function setupApprovalListener() {
    Api.on("approval_required", (req) => {
      currentApprovalRequestId = req.requestId;
      const modal = document.getElementById("approvalModal");
      document.getElementById("approvalLevelBadge").textContent = `Permission Level ${req.level} Approval Required`;
      document.getElementById("approvalWorkerText").textContent = `Worker [${req.workerId}] requests execution of '${req.tool}.${req.action}'`;
      document.getElementById("approvalDetails").textContent = JSON.stringify(req.params, null, 2);
      modal.style.display = "flex";
      toast(`⚠️ Action Approval Required from Worker ${req.workerId}`);
    });

    document.getElementById("confirmApprovalBtn").addEventListener("click", async () => {
      if (!currentApprovalRequestId) return;
      await Api.resolveApproval(currentApprovalRequestId, true);
      document.getElementById("approvalModal").style.display = "none";
      toast("Action Approved");
      currentApprovalRequestId = null;
      refreshSessionPane();
    });

    document.getElementById("rejectApprovalBtn").addEventListener("click", async () => {
      if (!currentApprovalRequestId) return;
      await Api.resolveApproval(currentApprovalRequestId, false, "Denied by user");
      document.getElementById("approvalModal").style.display = "none";
      toast("Action Denied");
      currentApprovalRequestId = null;
      refreshSessionPane();
    });
  }

  // ---- Phase 7: navigation & view renderers ----
  function openProjectsView() {
    showView("projects");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    document.getElementById("navProjectsBtn").classList.add("active");
    Views.renderProjects();
  }
  async function openTasksView() {
    showView("tasks");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    document.getElementById("navTasksBtn").classList.add("active");
    await Views.renderTasks();
  }
  function openPMsView() {
    showView("pms");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    document.getElementById("navPmsBtn").classList.add("active");
    Views.renderPMs();
  }
  function openKnowledgeView() {
    showView("vault");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    document.getElementById("navKnowledgeBtn").classList.add("active");
    Vault.render("mb");  // Knowledge & Memory is the Main Brain Memory vault now
  }
  function openToolsView(name) {
    showView(name);
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    const btn = document.getElementById("nav" + name[0].toUpperCase() + name.slice(1) + "Btn");
    if (btn) btn.classList.add("active");
    Tools.render(name);
    if (Tools.bindFsButtons) Tools.bindFsButtons();
  }
  const toolNavs = {
    timer: "navTimerBtn", calc: "navCalcBtn",
    code: "navCodeBtn", suite: "navSuiteBtn",
    media: "navMediaBtn", remote: "navRemoteBtn",
  };
  async function openWorkspaceView() {
    showView("workspace");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    const btn = document.getElementById("navWorkspaceBtn");
    if (btn) btn.classList.add("active");
    try {
      const projects = await Api.listProjects();
      const target = (projects && projects.length) ? projects[0].id : "default";
      if (!Workspace.els || !Workspace.els.wsName) Workspace.init();
      await Workspace.load(target);
    } catch (e) {
      console.error("workspace open failed", e);
      if (!Workspace.els || !Workspace.els.wsName) Workspace.init();
    }
  }
  function openVaultView() {
    showView("vault");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    const btn = document.getElementById("navVaultBtn");
    if (btn) btn.classList.add("active");
    Vault.render();
  }
  function openDesignView() {
    showView("worker-design");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    const btn = document.getElementById("navDesignBtn");
    if (btn) btn.classList.add("active");
    Workers.renderDesign(null);
  }
  function openDashboardView() {
    showView("dashboard");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    const btn = document.getElementById("navDashBtn");
    if (btn) btn.classList.add("active");
    Dashboard.render();
  }
  function wirePhase10() {
    Object.entries(toolNavs).forEach(([name, id]) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("click", () => openToolsView(name));
    });
    const wsNav = document.getElementById("navWorkspaceBtn");
    if (wsNav) wsNav.addEventListener("click", openWorkspaceView);
    const db = document.getElementById("navDashBtn");
    if (db) db.addEventListener("click", openDashboardView);
    const vv = document.getElementById("navVaultBtn");
    if (vv) vv.addEventListener("click", openVaultView);
    const dv = document.getElementById("navDesignBtn");
    if (dv) dv.addEventListener("click", openDesignView);
    const od = document.getElementById("openDesignWorkerBtn");
    if (od) od.addEventListener("click", openDesignView);
  }
  function openSettingsView() {
    showView("settings");
    document.querySelectorAll(".side-item").forEach((el) => el.classList.remove("active"));
    document.getElementById("navSettingsBtn").classList.add("active");
    Views.renderSettings();
  }

  function wirePhase7() {
    const elProjects = document.getElementById("navProjectsBtn");
    if (elProjects) elProjects.addEventListener("click", openProjectsView);
    const elTasks = document.getElementById("navTasksBtn");
    if (elTasks) elTasks.addEventListener("click", openTasksView);
    document.getElementById("navPmsBtn").addEventListener("click", openPMsView);
    document.getElementById("navKnowledgeBtn").addEventListener("click", openKnowledgeView);
    document.getElementById("navSettingsBtn").addEventListener("click", openSettingsView);
    document.getElementById("refreshProjectsBtn").addEventListener("click", Views.renderProjects);
    document.getElementById("refreshTasksBtn").addEventListener("click", Views.renderTasks);
    document.getElementById("refreshPmsBtn").addEventListener("click", Views.renderPMs);
    document.getElementById("refreshSettingsBtn").addEventListener("click", Views.renderSettings);
    const lr = document.getElementById("learningRefreshBtn");
    if (lr) lr.addEventListener("click", () => Views.renderLearning());
    const ls = document.getElementById("learningScope");
    if (ls) ls.addEventListener("change", () => Views.renderLearning());
    // live refresh on engine events (state changes, worker activity)
    Api.on("task_state_changed", () => {
      if (document.getElementById("view-tasks").classList.contains("active")) Views.renderTasks();
      if (document.getElementById("view-projects").classList.contains("active")) Views.renderProjects();
      if (document.getElementById("view-chat").classList.contains("active")) refreshSessionPane();
    });
    Api.on("worker_status_changed", () => {
      if (document.getElementById("view-chat").classList.contains("active")) refreshSessionPane();
    });
    Api.on("pm_status_changed", () => {
      if (document.getElementById("view-pms").classList.contains("active")) Views.renderPMs();
      if (document.getElementById("view-chat").classList.contains("active")) refreshSessionPane();
    });
    Api.on("qa2_audit_completed", () => {
      if (document.getElementById("view-tasks").classList.contains("active")) Views.renderTasks();
      if (document.getElementById("view-chat").classList.contains("active")) refreshSessionPane();
    });
  }

  function wireStatic() {
    document.getElementById("collapseBtn").addEventListener("click", () => {
      collapsed = !collapsed;
      document.getElementById("sidebar").classList.toggle("collapsed", collapsed);
      document.getElementById("collapseBtn").textContent = collapsed ? "»" : "«";
    });

    document.getElementById("newChatItem").addEventListener("click", async () => {
      showView("chat");
      await Chat.startNew();
      await refreshSidebar();
    });

    document.getElementById("navWorkersBtn").addEventListener("click", openWorkersView);
    document.getElementById("navAuditBtn").addEventListener("click", openAuditView);
    document.getElementById("refreshAuditBtn").addEventListener("click", renderAuditLogs);

    document.getElementById("newProjectBtn").addEventListener("click", async () => {
      document.getElementById("projectNameInput").value = "";
      const workerListEl = document.getElementById("modalWorkerCheckboxes");
      const workers = await Api.listWorkers();
      workerListEl.innerHTML = workers.map(w => `
        <label class="worker-check">
          <input type="checkbox" value="${w.worker_id}" checked />
          <div><div class="wc-name">${w.name} ${w.role_class || ""}</div><div class="wc-desc">${(w.skills || []).map(s => s.skill_id || s.name || "").join(", ") || "no skills"}</div></div>
        </label>
      `).join("");
      document.getElementById("newProjectModal").classList.add("open");
    });

    document.getElementById("cancelProjectBtn").addEventListener("click", () => {
      document.getElementById("newProjectModal").classList.remove("open");
    });

    document.getElementById("createProjectBtn").addEventListener("click", async () => {
      const name = document.getElementById("projectNameInput").value.trim() || "Untitled Project Workspace";
      const workers = Array.from(document.querySelectorAll("#modalWorkerCheckboxes input:checked")).map((i) => i.value);
      if (workers.length === 0) { toast("Pick at least one worker."); return; }
      const project = await Api.createProject({ name, workers });
      document.getElementById("newProjectModal").classList.remove("open");
      await refreshSidebar();
      await openProject(project.id);
    });

    setupApprovalListener();
  }

  function wireSpResize() { /* Studio owns the lower session dock. */ }

  async function boot() {
    wireStatic();
    wireYuimiTop();
    wirePhase7();
    wirePhase10();
    wireSpResize();
    // Dashboard first - never let a chat boot hang the command center.
    try { showView("dashboard"); Dashboard.render(); } catch (e) { console.warn("Dashboard render:", e); }
    Chat.init();
    Workspace.init();
    // Legacy workspace components must never block the core boot.
    try { WorkGraph.init("workGraphContainer"); } catch (e) { console.warn("WorkGraph init skipped:", e); }
    try { await VirtualOffice.init("virtualOfficeContainer"); } catch (e) { console.warn("VirtualOffice init skipped:", e); }
    await refreshSidebar();
    await Chat.startNew();
    refreshSessionPane(null);
  }

  document.addEventListener("DOMContentLoaded", boot);

  return { toast, showView, openChat, openProject, refreshSidebar, escapeHtml,
           openTasksView, openProjectsView, refreshSessionPane, openWorkersView, openDesignView, openVaultView, openKnowledgeView, openToolsView, openAuditView };
})();
