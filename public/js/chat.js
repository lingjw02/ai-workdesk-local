const Chat = (() => {
  let conversationId = null;
  let mode = "instant";
  let chatMode = "chat"; // chat | project
  let searchOn = false;
  let attachments = [];
  let sending = false;
  let lastClarificationTask = null;
  let floorTimer = null;

  const els = {};

  function init() {
    els.log = document.getElementById("chatLog");
    els.title = document.getElementById("chatTitle");
    els.input = document.getElementById("chatInput");
    els.sendBtn = document.getElementById("sendBtn");
    els.searchToggle = document.getElementById("searchToggle");
    els.deepthink = document.getElementById("deepthinkSelect");
    els.attachBtn = document.getElementById("attachBtn");
    els.fileInput = document.getElementById("fileInput");
    els.attachList = document.getElementById("attachList");
    els.clarificationBanner = document.getElementById("clarificationBanner");
    els.clarificationQuestion = document.getElementById("clarificationQuestion");
    els.clarificationExplanation = document.getElementById("clarificationExplanation");
    els.clarificationOptions = document.getElementById("clarificationOptions");

    document.querySelectorAll("#composer .pill").forEach((p) => {
      p.addEventListener("click", () => {
        document.querySelectorAll("#composer .pill").forEach((x) => x.classList.remove("active"));
        p.classList.add("active");
        mode = p.getAttribute("data-mode");
        if (mode === "vision") els.attachBtn.click();
      });
    });

    // chat mode switch
    document.querySelectorAll("#chatModeSwitch .cm-btn").forEach((b) => {
      b.addEventListener("click", () => {
        document.querySelectorAll("#chatModeSwitch .cm-btn").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        chatMode = b.getAttribute("data-chatmode");
        updateModeHints();
      });
    });
    updateModeHints();

    els.searchToggle.addEventListener("click", () => {
      searchOn = !searchOn;
      els.searchToggle.classList.toggle("on", searchOn);
    });

    els.attachBtn.addEventListener("click", () => els.fileInput.click());
    els.fileInput.addEventListener("change", handleFiles);

    els.input.addEventListener("input", () => {
      els.input.style.height = "auto";
      els.input.style.height = Math.min(els.input.scrollHeight, 180) + "px";
    });
    els.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
    els.sendBtn.addEventListener("click", () => send());

    initBrowserModal();
  }

  function updateModeHints() {
    const ph = els.input;
    if (ph) ph.placeholder = chatMode === "project"
      ? "Describe a goal - the Main Brain will assemble a project team and work live..."
      : "Ask the Main Brain anything...";
  }

  function handleFiles(e) {
    const files = Array.from(e.target.files || []);
    files.forEach((f) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = reader.result;
        const base64 = dataUrl.split(",")[1];
        attachments.push({ mediaType: f.type || "image/png", data: base64, previewUrl: dataUrl });
        renderAttachments();
      };
      reader.readAsDataURL(f);
    });
    e.target.value = "";
  }

  function renderAttachments() {
    els.attachList.innerHTML = attachments.map((a, i) =>
      `<div class="attach-chip"><img src="${a.previewUrl}" /><div class="x" data-i="${i}">✕</div></div>`
    ).join("");
    els.attachList.querySelectorAll(".x").forEach((x) => {
      x.addEventListener("click", () => { attachments.splice(Number(x.getAttribute("data-i")), 1); renderAttachments(); });
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function formatText(text) {
    let clean = String(text);
    const parts = clean.split(/```([\s\S]*?)```/g);
    return parts.map((p, i) => {
      if (i % 2 === 1) {
        const firstNl = p.indexOf("\n");
        const code = firstNl === -1 ? p : p.slice(firstNl + 1);
        return `<pre><code>${escapeHtml(code)}</code></pre>`;
      }
      let formatted = escapeHtml(p);
      formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');
      formatted = formatted.replace(/\n/g, '<br/>');
      return formatted;
    }).join("");
  }

  function clearEmptyState() {
    const empty = document.getElementById("chatEmptyState");
    if (empty) empty.remove();
  }

  function appendMessage(role, text, images) {
    clearEmptyState();
    const row = document.createElement("div");
    row.className = `msg-row ${role}`;
    const avatar = role === "user" ? "You" : "MB";
    const thumbs = images && images.length
      ? `<div class="msg-thumbs">${images.map((i) => `<img src="${i.previewUrl}" />`).join("")}</div>` : "";
    row.innerHTML = role === "user"
      ? `<div class="msg-bubble">${thumbs}${formatText(text)}</div>`
      : `<div class="avatar">${avatar}</div><div class="msg-bubble">${formatText(text)}</div>`;
    els.log.appendChild(row);
    els.log.scrollTop = els.log.scrollHeight;
    return row;
  }

  // typewriter for assistant messages (like a real agent talking)
  function typewriter(text, speed = 14) {
    return new Promise((resolve) => {
      clearEmptyState();
      const row = document.createElement("div");
      row.className = "msg-row assistant";
      row.innerHTML = `<div class="avatar">MB</div><div class="msg-bubble typewriter"></div>`;
      els.log.appendChild(row);
      els.log.scrollTop = els.log.scrollHeight;
      const bubble = row.querySelector(".msg-bubble");
      const full = String(text);
      let i = 0;
      const step = () => {
        const chunk = 3;
        if (i < full.length) {
          i = Math.min(full.length, i + chunk);
          bubble.innerHTML = formatText(full.slice(0, i)) + (i < full.length ? '<span class="caret"></span>' : "");
          els.log.scrollTop = els.log.scrollHeight;
          setTimeout(step, speed);
        } else {
          bubble.innerHTML = formatText(full);
          els.log.scrollTop = els.log.scrollHeight;
          resolve(row);
        }
      };
      step();
    });
  }

  function appendTyping() {
    clearEmptyState();
    const row = document.createElement("div");
    row.className = "msg-row assistant";
    row.id = "typingRow";
    row.innerHTML = `<div class="avatar">🧠</div><div class="msg-bubble typing-dots"><span></span><span></span><span></span> Main Brain working…</div>`;
    els.log.appendChild(row);
    els.log.scrollTop = els.log.scrollHeight;
  }

  function removeTyping() {
    const t = document.getElementById("typingRow");
    if (t) t.remove();
  }

  // ---- result card (QA-2 completed) ----
  function appendResultCard(taskResult) {
    if (!taskResult) return;
    clearEmptyState();
    const row = document.createElement("div");
    row.className = "msg-row assistant result-row";
    const qa = (taskResult.qa2Report && taskResult.qa2Report.result) || "PASS";
    const qaScore = (taskResult.qa2Report && taskResult.qa2Report.score) != null ? taskResult.qa2Report.score : 1.0;
    const pmPlan = taskResult.pmPlan || "";
    const delivs = taskResult.deliverables || {};
    const delivNames = Object.keys(delivs);
    const delivHtml = delivNames.length
      ? delivNames.map((n) => {
          const v = delivs[n];
          const size = typeof v === "string" ? (v.length / 1024).toFixed(1) + " KB" : (v && v.total != null ? "data" : "");
          return `<div class="rc-deliv"><span class="rc-file">📄 ${escapeHtml(n)}</span>${size ? `<span class="muted">${size}</span>` : ""}</div>`;
        }).join("")
      : '<div class="muted">No file deliverables.</div>';
    const qaCycles = /QA-2 cycles:\s*(\d+)/.exec(pmPlan);
    const compCount = /Decomposed into (\d+) component/.exec(pmPlan);
    row.innerHTML = `
      <div class="avatar">🧠</div>
      <div class="result-card">
        <div class="rc-head ${qa === "PASS" ? "pass" : "fail"}">
          <span class="rc-badge">${qa === "PASS" ? "✅" : "❌"} Task Group Execution Completed</span>
          <span class="rc-qa">QA-2 Verified: <b>${escapeHtml(qa)}</b> , score ${(Number(qaScore) * 100).toFixed(0)}</span>
        </div>
        <div class="rc-body">
          <div class="rc-row"><span class="rc-key">PM Plan</span><span>${escapeHtml(pmPlan || "-")}</span></div>
          ${compCount ? `<div class="rc-row"><span class="rc-key">Components</span><span>${escapeHtml(compCount[1])}</span></div>` : ""}
          ${qaCycles ? `<div class="rc-row"><span class="rc-key">QA-2 cycles</span><span>${escapeHtml(qaCycles[1])}</span></div>` : ""}
          <div class="rc-row"><span class="rc-key">Deliverables</span></div>
          <div class="rc-delivs">${delivHtml}</div>
        </div>
        <div class="rc-actions">
          <button class="btn-primary rc-view" id="rcViewBtn">View in Workspace</button>
        </div>
      </div>`;
    els.log.appendChild(row);
    els.log.scrollTop = els.log.scrollHeight;
    const vb = row.querySelector("#rcViewBtn");
    if (vb) vb.addEventListener("click", () => {
      if (window.App && App.showView) App.showView("workspace");
    });
    return row;
  }

  function showClarificationBanner(clarification) {
    if (!clarification) return;
    els.clarificationQuestion.textContent = clarification.question;
    els.clarificationExplanation.textContent = clarification.contextExplanation || "Select or enter your preferred direction:";
    els.clarificationOptions.innerHTML = (clarification.options || []).map(opt => `
      <button class="cb-opt-btn">${escapeHtml(opt)}</button>
    `).join("");

    els.clarificationOptions.querySelectorAll(".cb-opt-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const choice = btn.textContent;
        els.clarificationBanner.style.display = "none";
        send(choice, lastClarificationTask);
      });
    });

    els.clarificationBanner.style.display = "flex";
  }

  async function send(overrideText = null, clarificationContext = null) {
    const text = overrideText !== null ? overrideText : els.input.value.trim();
    if ((!text && attachments.length === 0) || sending) return;
    sending = true;
    els.sendBtn.disabled = true;

    const imgsForBubble = attachments.slice();
    appendMessage("user", text, imgsForBubble);
    if (overrideText === null) {
      els.input.value = "";
      els.input.style.height = "auto";
    }
    const payloadImages = attachments.map((a) => ({ mediaType: a.mediaType, data: a.data }));
    attachments = [];
    renderAttachments();
    appendTyping();
    startFloorWatch();

    try {
      const data = await Api.sendChat({
        conversationId,
        mode,
        chatMode,
        deepthink: els.deepthink.value,
        search: searchOn,
        text,
        clarificationResponse: clarificationContext ? text : null,
      });

      conversationId = data.conversationId;
      removeTyping();

      // MB natural-language reply (typewriter)
      if (data.reply) {
        await typewriter(data.reply);
      }

      // Result card for completed complex tasks
      if (data.taskResult && data.taskResult.status === "DONE" && data.taskResult.complexity === "complex") {
        appendResultCard(data.taskResult);
      }

      App.refreshSessionPane();

      // Check if QA-1 flagged ambiguity
      if (data.taskResult && data.taskResult.status === "CLARIFICATION_REQUIRED") {
        lastClarificationTask = data.taskResult;
        showClarificationBanner(data.taskResult.clarification);
      } else {
        els.clarificationBanner.style.display = "none";
        lastClarificationTask = null;
      }

      await App.refreshSidebar();
      stopFloorWatch();
      refreshOfficeFloor();
    } catch (e) {
      removeTyping();
      appendMessage("assistant", `⚠ ${e.message}`);
    }

    sending = false;
    els.sendBtn.disabled = false;
    els.input.focus();
  }

  // ---- Office Floor (left panel): live worker desks ----
  async function refreshOfficeFloor() {
    try {
      const tasks = await Api.listTasks(null, 100, conversationId);
      const workers = await Api.listWorkers();
      const floor = document.getElementById("wfDesks");
      if (!floor) return;
      const activeTasks = (tasks || []).filter((t) => t.conversation_id === conversationId || t.conversationId === conversationId);
      // derive worker states from active task + its workerLogs
      const wStates = {};
      activeTasks.forEach((t) => {
        const logs = t.worker_logs || t.workerLogs || [];
        (logs || []).forEach((l) => { wStates[l.worker_id || l.workerId] = { state: l.state || "working", note: l.note || l.reason || "" }; });
        if (t.state) wStates._task = t.state;
      });
      const mbStatus = document.getElementById("wfMbStatus");
      if (mbStatus) mbStatus.textContent = wStates._task ? wStates._task.toLowerCase() : "idle";

      // SBR routing reasons (from this chat's tasks) -> worker -> {skill, score, reason}
      const sbrMap = {};
      (tasks || []).forEach((t) => {
        (t.team_routes || []).forEach((r) => { if (r.worker && !sbrMap[r.worker]) sbrMap[r.worker] = r; });
      });

      const cards = (workers || []).slice(0, 6).map((w) => {
        const wid = w.worker_id || w.id;
        const st = wStates[wid];
        const state = st ? st.state : (w.status || "available");
        const note = st ? st.note : "";
        const sbr = sbrMap[wid];
        const sbrTip = sbr ? `SBR: ${sbr.skill} → ${sbr.worker} , score ${sbr.score} - ${sbr.reason}` : "";
        const skillTag = sbr ? `<span class="wf-desk-skill" title="${escapeHtml(sbrTip)}">${escapeHtml(sbr.skill)}</span>` : "";
        return `<div class="wf-desk" data-wid="${escapeHtml(wid)}" data-name="${escapeHtml(w.name || wid)}" title="${escapeHtml(sbrTip)}">
          <div class="wf-desk-hex">${escapeHtml((w.name || wid || "?").slice(0, 2).toUpperCase())}</div>
          <div class="wf-desk-name">${escapeHtml(w.name || wid)}</div>
          <div class="wf-desk-status st-${state.toLowerCase().replace(/[^a-z]/g, "")}">${escapeHtml(state)}</div>
          ${skillTag}
          ${note ? `<div class="wf-desk-note">${escapeHtml(note)}</div>` : ""}
          <button class="btn-secondary btn-sm wf-open" data-wid="${escapeHtml(wid)}" data-name="${escapeHtml(w.name || wid)}">Open workspace</button>
        </div>`;
      }).join("");
      floor.innerHTML = cards + (activeTasks.length === 0 ? "" : `<div class="wf-floor-live">● live - ${activeTasks.length} task(s) running</div>`);
      const footW = document.getElementById("wfFootWorkers");
      const footA = document.getElementById("wfFootActive");
      if (footW) footW.textContent = `${(workers || []).length} workers`;
      if (footA) {
        const activeNow = (workers || []).filter((w) => {
          const wid = w.worker_id || w.id;
          const st = wStates[wid];
          return st ? st.state !== "idle" && st.state !== "available" : false;
        }).length;
        footA.textContent = activeNow ? `${activeNow} active` : "0 active";
      }
      floor.querySelectorAll(".wf-desk").forEach((d) => {
        d.addEventListener("click", (e) => {
          if (e.target.closest(".wf-open")) return;
          const wid = d.getAttribute("data-wid");
          const name = d.getAttribute("data-name");
          openWorkerDesk(wid, name);
        });
      });
      floor.querySelectorAll(".wf-open").forEach((b) => {
        b.addEventListener("click", (e) => {
          e.stopPropagation();
          openWorkerDesk(b.getAttribute("data-wid"), b.getAttribute("data-name"));
        });
      });
    } catch (e) { /* keep quiet */ }
  }

  function startFloorWatch() {
    stopFloorWatch();
    refreshOfficeFloor();
    floorTimer = setInterval(refreshOfficeFloor, 2500);
  }

  function stopFloorWatch() {
    if (floorTimer) { clearInterval(floorTimer); floorTimer = null; }
  }

  // click a worker desk -> open its real working surface
  function openWorkerDesk(wid, name) {
    const w = String(wid || "").toLowerCase();
    const n = String(name || "").toLowerCase();
    if (w.includes("coder") || n.includes("coder") || n.includes("code") || w === "coder") {
      if (window.App && App.showView) App.showView("code");
      else if (window.App && App.openCodeStudio) App.openCodeStudio();
    } else if (w.includes("research") || n.includes("research") || n.includes("researcher")) {
      openBrowserModal();
    } else {
      // generic profile peek
      appendMessage("assistant", `**${name}** - worker is on standby. Open its dedicated surface: Coder → Code Studio, Researcher → Live Browser, Data → Data workspace.`);
    }
  }

  // ---- Researcher live browser ----
  function initBrowserModal() {
    const open = document.getElementById("browserModal");
    const close = document.getElementById("browserClose");
    const go = document.getElementById("browserGo");
    const q = document.getElementById("browserQuery");
    if (!open) return;
    if (close) close.addEventListener("click", () => { open.style.display = "none"; });
    open.addEventListener("click", (e) => { if (e.target === open) open.style.display = "none"; });
    const run = async () => {
      const query = (q.value || "").trim();
      if (!query) return;
      const status = document.getElementById("browserStatus");
      const results = document.getElementById("browserResults");
      status.textContent = `🔎 Researcher is searching: "${query}"…`;
      results.innerHTML = "";
      try {
        const r = await fetch(`/api/search?q=${encodeURIComponent(query)}&count=5`);
        const data = await r.json();
        if (data.error) { status.textContent = "⚠ Search failed: " + data.error; return; }
        status.textContent = `✔ ${(data.results || []).length} results found - researcher browsing…`;
        results.innerHTML = (data.results || []).map((res, i) => `
          <div class="browser-result">
            <div class="br-idx">${i + 1}</div>
            <div class="br-body">
              <a class="br-title" href="${escapeHtml(res.url || "#")}" target="_blank" rel="noopener">${escapeHtml(res.title || "(untitled)")}</a>
              <div class="br-url">${escapeHtml(res.url || "")}</div>
              <div class="br-snippet">${escapeHtml(res.snippet || res.content || "")}</div>
            </div>
          </div>`).join("") || '<div class="muted">No results.</div>';
      } catch (e) {
        status.textContent = "⚠ " + e.message;
      }
    };
    if (go) go.addEventListener("click", run);
    if (q) q.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  }

  function openBrowserModal() {
    const open = document.getElementById("browserModal");
    if (open) open.style.display = "flex";
    const q = document.getElementById("browserQuery");
    if (q) q.focus();
  }

  function emptyStateHtml() {
    return `<div class="chat-empty" id="chatEmptyState"><h2>What are we working on?</h2><p>Ask a question, explore an idea, or give your team a goal. Your tasks and outputs stay together here.</p></div>`;
  }

  async function startNew() {
    conversationId = null;
    attachments = [];
    renderAttachments();
    els.title.textContent = "New conversation";
    els.log.innerHTML = emptyStateHtml();
    els.clarificationBanner.style.display = "none";
    stopFloorWatch();
    refreshOfficeFloor();
    App.refreshSessionPane(null);
  }

  async function load(id) {
    const conv = await Api.getConversation(id);
    conversationId = conv.id;
    if (conv.chatMode) {
      chatMode = conv.chatMode;
      document.querySelectorAll("#chatModeSwitch .cm-btn").forEach((x) => x.classList.toggle("active", x.getAttribute("data-chatmode") === chatMode));
      updateModeHints();
    }
    els.title.textContent = conv.title || "Chat";
    els.log.innerHTML = "";
    els.clarificationBanner.style.display = "none";
    App.refreshSessionPane(conv.id);
    if (!conv.messages || conv.messages.length === 0) {
      els.log.innerHTML = emptyStateHtml();
      return;
    }
    conv.messages.forEach((m) => {
      if (m.role === "assistant" && m.taskResult && m.taskResult.status === "DONE" && m.taskResult.complexity === "complex") {
        appendMessage("assistant", m.text || "");
        appendResultCard(m.taskResult);
      } else {
        appendMessage(m.role, m.text || "");
      }
    });
    refreshOfficeFloor();
  }

  function getConversationId() {
    return conversationId;
  }

  return { init, send, startNew, load, getConversationId, refreshOfficeFloor };
})();
