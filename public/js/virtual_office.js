// 2D Virtual Office View for AI WorkDesk OS
const VirtualOffice = (() => {
  let container = null;
  let workersData = [];
  let pmData = { name: "Project Manager", status: "idle", plan: "" };
  let mbStatus = "idle";
  let activeSpeech = {};

  async function init(elementId) {
    container = document.getElementById(elementId);
    if (!container) return;

    try {
      workersData = await Api.listWorkers();
    } catch (e) {
      console.warn("Could not load workers for virtual office:", e);
    }

    setupEventListeners();
    render();
  }

  function setupEventListeners() {
    Api.on("worker_status_changed", (data) => {
      const w = workersData.find(x => (x.id || x.worker_id) === data.workerId);
      if (w) {
        w.status = data.status;
      }
      activeSpeech[data.workerId] = data.activity || data.status;
      render();
    });

    Api.on("pm_status_changed", (data) => {
      pmData.status = data.status;
      pmData.plan = data.message || "";
      activeSpeech["pm"] = data.message;
      render();
    });

    Api.on("task_state_changed", (data) => {
      if (data.state === "ANALYZING" || data.state === "PLANNING") {
        mbStatus = "thinking";
        activeSpeech["mb"] = `Supervising: ${data.reason}`;
      } else if (data.state === "DONE") {
        mbStatus = "idle";
        activeSpeech["mb"] = "Task completed successfully.";
      }
      render();
    });
  }

  function getStatusBadge(status) {
    const s = (status || "available").toLowerCase();
    if (s === "working" || s === "executing") return `<span class="vo-badge vo-badge-working">⚡ Working</span>`;
    if (s === "thinking" || s === "planning") return `<span class="vo-badge vo-badge-thinking">💭 Thinking</span>`;
    if (s === "waiting_approval" || s === "waiting") return `<span class="vo-badge vo-badge-waiting">⏳ Waiting</span>`;
    if (s === "completed" || s === "done") return `<span class="vo-badge vo-badge-done">✓ Done</span>`;
    if (s === "error" || s === "reworking") return `<span class="vo-badge vo-badge-error">⚠️ ${s}</span>`;
    return `<span class="vo-badge vo-badge-idle">🟢 Ready</span>`;
  }

  function render() {
    if (!container) return;

    const desksHtml = workersData.map(w => {
      const speech = activeSpeech[w.id];
      const stats = w.stats || w.statistics || {};
      return `
        <div class="vo-desk" data-worker-id="${w.id || w.worker_id}">
          <div class="vo-desk-top">
            <div class="vo-avatar">${w.avatar || '🤖'}</div>
            <div class="vo-worker-info">
              <div class="vo-name">${w.name}</div>
              <div class="vo-role">${String(w.description || (w.capabilities || []).join(", ") || w.worker_id || "").split(",")[0]}</div>
            </div>
            ${getStatusBadge(w.status)}
          </div>
          ${speech ? `<div class="vo-speech-bubble">${speech}</div>` : ''}
          <div class="vo-stats-mini">
            <span>Pass: ${((stats.qa_pass_rate != null ? stats.qa_pass_rate : (stats.qaPassRate || 0)) * 100).toFixed(0)}%</span>
            <span>Tasks: ${stats.tasks_completed != null ? stats.tasks_completed : (stats.tasksCompleted || 0)}</span>
            <span>Autonomy: L${(w.permissions && w.permissions.maxAutonomyLevel) || 1}</span>
          </div>
        </div>
      `;
    }).join("");

    container.innerHTML = `
      <div class="vo-office-layout">
        <!-- Executive Section: Main Brain & Lifetime PM -->
        <div class="vo-executive-suite">
          <div class="vo-room-title">🏛️ EXECUTIVE SUITE & PM DESK</div>
          <div class="vo-exec-desks">
            
            <div class="vo-desk vo-desk-mb">
              <div class="vo-desk-top">
                <div class="vo-avatar">🧠</div>
                <div class="vo-worker-info">
                  <div class="vo-name">Main Brain</div>
                  <div class="vo-role">OS Kernel & Global Intelligence</div>
                </div>
                ${getStatusBadge(mbStatus)}
              </div>
              ${activeSpeech["mb"] ? `<div class="vo-speech-bubble">${activeSpeech["mb"]}</div>` : ''}
              <div class="vo-stats-mini">
                <span>Global Authority</span>
                <span>Active Routing</span>
              </div>
            </div>

            <div class="vo-desk vo-desk-pm">
              <div class="vo-desk-top">
                <div class="vo-avatar">👔</div>
                <div class="vo-worker-info">
                  <div class="vo-name">Project Manager</div>
                  <div class="vo-role">Lifetime Project Leader</div>
                </div>
                ${getStatusBadge(pmData.status)}
              </div>
              ${activeSpeech["pm"] ? `<div class="vo-speech-bubble">${activeSpeech["pm"]}</div>` : ''}
              <div class="vo-stats-mini">
                <span>Project Memory: Active</span>
                <span>Selective Rework: Ready</span>
              </div>
            </div>

          </div>
        </div>

        <!-- Open Plan Floor: Persistent Workers -->
        <div class="vo-floor-section">
          <div class="vo-room-title">🏢 WORKDESK FLOOR (PERSISTENT EMPLOYEES)</div>
          <div class="vo-desks-grid">
            ${desksHtml}
          </div>
        </div>
      </div>
    `;
  }

  return { init, render };
})();
