// Dynamic Work Graph DAG Visualization for AI WorkDesk OS
const WorkGraph = (() => {
  let container = null;
  let currentState = {
    user: "idle",
    mainBrain: "idle",
    qa1: "idle",
    pm: "idle",
    workers: {},
    artifactBuilder: "idle",
    qa2: "idle",
    finalizer: "idle",
  };

  function init(elementId) {
    container = document.getElementById(elementId);
    if (!container) return;
    render();
    setupListeners();
  }

  function setupListeners() {
    Api.on("task_state_changed", (data) => {
      handleStateChange(data.state, data);
    });
    Api.on("qa1_audit_completed", (data) => {
      currentState.qa1 = data.status === "PASS" ? "passed" : "failed";
      render();
    });
    Api.on("pm_status_changed", (data) => {
      currentState.pm = data.status;
      render();
    });
    Api.on("worker_status_changed", (data) => {
      currentState.workers[data.workerId] = data.status;
      render();
    });
    Api.on("qa2_audit_completed", (data) => {
      currentState.qa2 = data.result === "PASS" ? "passed" : "rework";
      render();
    });
  }

  function handleStateChange(state, data) {
    switch (state) {
      case "ANALYZING":
        currentState.user = "active";
        currentState.mainBrain = "active";
        currentState.qa1 = "active";
        break;
      case "CLARIFICATION_REQUIRED":
        currentState.qa1 = "failed";
        currentState.mainBrain = "clarifying";
        break;
      case "PLANNING":
        currentState.qa1 = "passed";
        currentState.mainBrain = "done";
        currentState.pm = "active";
        break;
      case "WORKING":
        currentState.pm = "active";
        break;
      case "QA_2":
        currentState.artifactBuilder = "done";
        currentState.qa2 = "active";
        break;
      case "REWORK":
        currentState.qa2 = "rework";
        currentState.pm = "reworking";
        break;
      case "FINALIZING":
        currentState.qa2 = "passed";
        currentState.finalizer = "active";
        break;
      case "DONE":
        currentState.finalizer = "done";
        currentState.mainBrain = "done";
        break;
      case "CANCELLED":
        resetStates("cancelled");
        break;
    }
    render();
  }

  function resetStates(stateVal = "idle") {
    Object.keys(currentState).forEach(k => {
      if (k === "workers") currentState.workers = {};
      else currentState[k] = stateVal;
    });
  }

  function getStatusClass(status) {
    if (!status || status === "idle") return "node-idle";
    if (status === "active" || status === "working" || status === "executing") return "node-active";
    if (status === "passed" || status === "done" || status === "completed") return "node-passed";
    if (status === "failed" || status === "rework" || status === "error") return "node-failed";
    if (status === "clarifying" || status === "planning") return "node-thinking";
    return "node-idle";
  }

  function render() {
    if (!container) return;

    const workerNodes = Object.entries(currentState.workers).map(([wid, st]) => {
      const cls = getStatusClass(st);
      return `<div class="dag-worker-node ${cls}">
        <div class="dag-icon">⚙️</div>
        <div class="dag-label">${wid}</div>
        <div class="dag-sub">${st}</div>
      </div>`;
    }).join("") || `<div class="dag-worker-node node-idle"><div class="dag-icon">👥</div><div class="dag-label">Workers</div><div class="dag-sub">Awaiting assign</div></div>`;

    container.innerHTML = `
      <div class="dag-canvas">
        <div class="dag-tier">
          <div class="dag-node ${getStatusClass(currentState.user)}">
            <div class="dag-icon">👤</div>
            <div class="dag-label">USER</div>
            <div class="dag-sub">Goal Request</div>
          </div>
        </div>

        <div class="dag-connector">↓</div>

        <div class="dag-tier">
          <div class="dag-node ${getStatusClass(currentState.mainBrain)}">
            <div class="dag-icon">🧠</div>
            <div class="dag-label">MAIN BRAIN</div>
            <div class="dag-sub">OS Kernel & Router</div>
          </div>
        </div>

        <div class="dag-connector">↓</div>

        <div class="dag-tier">
          <div class="dag-node dag-gate ${getStatusClass(currentState.qa1)}">
            <div class="dag-icon">🛡️-1</div>
            <div class="dag-label">REQUIREMENT QA</div>
            <div class="dag-sub">${currentState.qa1 === "failed" ? "Ambiguity Gate ⚠️" : "Pre-execution"}</div>
          </div>
        </div>

        <div class="dag-connector">↓</div>

        <div class="dag-tier">
          <div class="dag-node ${getStatusClass(currentState.pm)}">
            <div class="dag-icon">👔</div>
            <div class="dag-label">PROJECT MANAGER</div>
            <div class="dag-sub">Lifetime Employee</div>
          </div>
        </div>

        <div class="dag-connector">↓ (Task Group Parallel Execution)</div>

        <div class="dag-tier dag-workers-row">
          ${workerNodes}
        </div>

        <div class="dag-connector">↓</div>

        <div class="dag-tier">
          <div class="dag-node ${getStatusClass(currentState.artifactBuilder)}">
            <div class="dag-icon">📦</div>
            <div class="dag-label">ARTIFACT BUILDER</div>
            <div class="dag-sub">Synthesize Outputs</div>
          </div>
        </div>

        <div class="dag-connector">↓</div>

        <div class="dag-tier">
          <div class="dag-node dag-gate ${getStatusClass(currentState.qa2)}">
            <div class="dag-icon">🛡️-2</div>
            <div class="dag-label">OUTPUT QA</div>
            <div class="dag-sub">${currentState.qa2 === "rework" ? "Selective Rework ↺" : "Post-execution"}</div>
          </div>
        </div>

        <div class="dag-connector">↓</div>

        <div class="dag-tier">
          <div class="dag-node ${getStatusClass(currentState.finalizer)}">
            <div class="dag-icon">✨</div>
            <div class="dag-label">DELIVERED</div>
            <div class="dag-sub">Verified Result</div>
          </div>
        </div>
      </div>
    `;
  }

  return { init, render, resetStates };
})();
