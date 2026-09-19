const Workspace = (() => {
  let projectId = null;
  let project = null;
  let selectedWorker = null;
  let activeTab = "graph"; // graph, office, deliverables
  let currentActiveTaskId = null;
  let floating = false;

  const els = {};

  function init() {
    els.wsName = document.getElementById("wsName");
    els.wsChips = document.getElementById("wsChips");
    els.canvasWrap = document.getElementById("canvasWrap");
    els.workGraph = document.getElementById("workGraphContainer");
    els.virtualOffice = document.getElementById("virtualOfficeContainer");
    els.deliverables = document.getElementById("deliverablesContainer");
    els.deliverablesList = document.getElementById("deliverablesList");
    els.workerRows = document.getElementById("workerRows");
    els.detailTitle = document.getElementById("detailTitle");
    els.detailPanel = document.getElementById("detailPanel");
    els.pmInput = document.getElementById("pmInput");
    els.pmSendBtn = document.getElementById("pmSendBtn");
    els.stopBtn = document.getElementById("stopTaskBtn");
    els.drawer = document.getElementById("terminalDrawer");
    els.handle = document.getElementById("terminalHandle");
    els.terminalBody = document.getElementById("terminalBody");
    els.popOutBtn = document.getElementById("popOutBtn");

    // Tab switcher
    document.querySelectorAll(".ws-tab").forEach(tab => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".ws-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        switchWorkspaceTab(tab.getAttribute("data-tab"));
      });
    });

    els.pmSendBtn.addEventListener("click", sendTaskToPM);
    els.pmInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendTaskToPM();
    });

    els.stopBtn.addEventListener("click", emergencyStop);

    els.handle.addEventListener("click", (e) => {
      if (floating || e.target.id === "popOutBtn") return;
      els.drawer.classList.toggle("open");
    });
    els.popOutBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      floating = !floating;
      els.drawer.classList.toggle("floating", floating);
      els.drawer.classList.add("open");
      els.popOutBtn.textContent = floating ? "dock" : "pop out";
      if (!floating) { els.drawer.style.left = ""; els.drawer.style.top = ""; }
    });

    setupWebSocketListeners();
  }

  function setupWebSocketListeners() {
    Api.on("worker_status_changed", (data) => {
      appendTerminalLine(data.workerId, `${data.activity || data.status}`);
      refreshProjectState();
    });
    Api.on("pm_status_changed", (data) => {
      appendTerminalLine("pm", `[PM] ${data.message || data.status}`);
      refreshProjectState();
    });
    Api.on("task_state_changed", (data) => {
      appendTerminalLine("os", `[OS State] ${data.previousState} -> ${data.state}: ${data.reason}`);
      currentActiveTaskId = data.taskId;
    });
    Api.on("qa2_audit_completed", (data) => {
      appendTerminalLine("qa-2", `[QA-2] Result: ${data.result} (Score: ${(data.score * 100).toFixed(0)}%) - ${data.summary}`);
    });
  }

  function switchWorkspaceTab(tabName) {
    activeTab = tabName;
    els.workGraph.style.display = tabName === "graph" ? "block" : "none";
    els.virtualOffice.style.display = tabName === "office" ? "block" : "none";
    els.deliverables.style.display = tabName === "deliverables" ? "block" : "none";

    if (tabName === "graph") WorkGraph.render();
    if (tabName === "office") VirtualOffice.render();
    if (tabName === "deliverables") renderDeliverables();
  }

  function appendTerminalLine(who, text) {
    const line = document.createElement("div");
    line.className = `term-line who-${who}`;
    line.innerHTML = `<div class="who">${who}</div><div class="txt">${App.escapeHtml(text)}</div>`;
    els.terminalBody.appendChild(line);
    els.terminalBody.scrollTop = els.terminalBody.scrollHeight;
  }

  function renderDeliverables() {
    if (!project) return;
    const delivs = project.deliverables || {};
    const entries = Object.entries(delivs);
    if (!entries.length) {
      els.deliverablesList.innerHTML = `<div class="placeholder">No deliverables generated yet. Instruct the PM to begin work.</div>`;
      return;
    }
    els.deliverablesList.innerHTML = entries.map(([filename, content]) => `
      <div class="deliv-item">
        <div class="deliv-item-title">📄 ${App.escapeHtml(filename)}</div>
        <pre class="deliv-item-content"><code>${App.escapeHtml(String(content))}</code></pre>
      </div>
    `).join("");
  }

  function renderHeader() {
    if (!project) return;
    els.wsName.textContent = project.name || project.id || "Project Workspace";
    els.wsChips.innerHTML = (project.workers || []).map(w => `<div class="ws-chip">${w}</div>`).join("");
  }

  function renderWorkerRows() {
    if (!project) return;
    const rows = (project.workers || []).map(w => {
      const st = (project.nodes && project.nodes[w]) ? project.nodes[w].status : "idle";
      return `<div class="ov-worker-row ${st}" data-key="${w}">
        <div class="n-dot"></div>
        <div class="name">${w}</div>
        <div class="status">${st}</div>
      </div>`;
    }).join("");
    els.workerRows.innerHTML = rows;
    els.workerRows.querySelectorAll("[data-key]").forEach(el => {
      el.addEventListener("click", () => selectWorker(el.getAttribute("data-key")));
    });
  }

  function selectWorker(key) {
    selectedWorker = key;
    els.detailTitle.textContent = key.toUpperCase();
    if (project.nodes && project.nodes[key]) {
      const node = project.nodes[key];
      els.detailPanel.innerHTML = `
        <div class="detail-note">
          <div class="meta">Worker Status: ${node.status}</div>
          <div>${JSON.stringify(node, null, 2)}</div>
        </div>
      `;
    } else {
      els.detailPanel.innerHTML = `<div class="placeholder">No activity recorded for ${key}.</div>`;
    }
  }

  async function refreshProjectState() {
    if (!projectId) return;
    try {
      project = await Api.getProject(projectId);
      renderHeader();
      renderWorkerRows();
      if (activeTab === "deliverables") renderDeliverables();
    } catch (e) {
      console.warn("Error refreshing project state:", e);
    }
  }

  async function sendTaskToPM() {
    const text = els.pmInput.value.trim();
    if (!text) return;
    els.pmInput.value = "";
    els.pmSendBtn.disabled = true;
    appendTerminalLine("you", text);

    try {
      const result = await Api.dispatchProjectTask(projectId, text);
      await refreshProjectState();
      App.toast("Task completed and verified by QA-2");
    } catch (e) {
      App.toast(`Task error: ${e.message}`);
    } finally {
      els.pmSendBtn.disabled = false;
    }
  }

  async function emergencyStop() {
    if (!currentActiveTaskId || !projectId) {
      App.toast("No active running task to cancel.");
      return;
    }
    try {
      await Api.cancelTask(projectId, currentActiveTaskId);
      App.toast("Emergency Stop: Task Cancelled Safely");
    } catch (e) {
      App.toast(`Cancellation error: ${e.message}`);
    }
  }

  async function load(id) {
    projectId = id;
    selectedWorker = null;
    project = await Api.getProject(id);
    renderHeader();
    renderWorkerRows();
    switchWorkspaceTab("graph");
    await refreshProjectState();
  }

  return { init, load };
})();
