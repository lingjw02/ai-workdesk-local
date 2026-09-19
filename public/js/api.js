// AI WorkDesk OS - Client API and Real-time WebSocket bridge
const Api = {
  ws: null,
  listeners: {},

  initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    try {
      this.ws = new WebSocket(wsUrl);
      this.ws.onopen = () => {
        console.log("🟢 WebSocket connected to AI WorkDesk OS engine");
      };
      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          const type = message.type;
          const data = message.data;
          if (this.listeners[type]) {
            this.listeners[type].forEach(fn => fn(data));
          }
          if (this.listeners["*"]) {
            this.listeners["*"].forEach(fn => fn(type, data));
          }
        } catch (e) {
          console.warn("Failed parsing WS message:", e);
        }
      };
      this.ws.onclose = () => {
        console.log("WebSocket closed, attempting reconnect in 2s...");
        setTimeout(() => this.initWebSocket(), 2000);
      };
      this.ws.onerror = (err) => {
        console.error("WebSocket error:", err);
      };
    } catch (e) {
      console.error("Could not initialize WebSocket:", e);
    }
  },

  on(eventType, callback) {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = [];
    }
    this.listeners[eventType].push(callback);
  },

  async listConversations() {
    return (await fetch("/api/conversations")).json();
  },
  async createConversation() {
    return (await fetch("/api/conversations", { method: "POST" })).json();
  },
  async getConversation(id) {
    return (await fetch(`/api/conversations/${id}`)).json();
  },
  async deleteConversation(id) {
    return (await fetch(`/api/conversations/${id}`, { method: "DELETE" })).json();
  },
  async sendChat(payload) {
    if (this.chatPending) throw new Error("Main Brain is already replying. Please wait.");
    this.chatPending = true;
    try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Chat request failed");
    return data;
    } finally { this.chatPending = false; }
  },

  async listProjects() {
    return (await fetch("/api/projects")).json();
  },
  async createProject(payload) {
    const res = await fetch("/api/projects", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    return res.json();
  },
  async getProject(id) {
    return (await fetch(`/api/projects/${id}`)).json();
  },
  async deleteProject(id) {
    return (await fetch(`/api/projects/${id}`, { method: "DELETE" })).json();
  },
  async dispatchProjectTask(id, text, clarificationResponse = null) {
    const res = await fetch(`/api/projects/${id}/task`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, clarificationResponse }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "Task dispatch failed");
    return data;
  },
  async cancelTask(projectId, taskId) {
    const res = await fetch(`/api/projects/${projectId}/cancel`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ task_id: taskId }),
    });
    return res.json();
  },

  async listWorkers() {
    return (await fetch("/api/workers")).json();
  },
  async createWorker(worker) {
    const res = await fetch("/api/workers", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(worker),
    });
    return res.json();
  },

  async getMemory(projectId = null) {
    const q = projectId ? `?projectId=${projectId}` : "";
    return (await fetch(`/api/memory${q}`)).json();
  },
  async updateMemory(patch) {
    const res = await fetch("/api/memory", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(patch),
    });
    return res.json();
  },

  async listApprovals(conversationId = null) {
    const q = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
    return (await fetch(`/api/approvals${q}`)).json();
  },
  async resolveApproval(requestId, approved, userComment = null) {
    const res = await fetch("/api/approvals/resolve", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ requestId, approved, userComment }),
    });
    return res.json();
  },

  async getAuditLogs(limit = 50) {
    return (await fetch(`/api/audit?limit=${limit}`)).json();
  },

  // ---- Remote Device (working area) ----
  async remoteDevices() {
    return (await fetch("/api/remote/devices")).json();
  },
  async registerRemoteDevice(name, host, os = "") {
    const resp = await fetch("/api/remote/devices", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, host, os }),
    });
    return resp.json();
  },
  async sendRemoteCommand(deviceId, command) {
    const resp = await fetch(`/api/remote/${encodeURIComponent(deviceId)}/command`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command }),
    });
    return resp.json();
  },

  // ---- SBR: skill market + gap-driven worker creation ----
  async skillMarket() {
    return (await fetch("/api/skill-market")).json();
  },
  async installSkill(workerId, skillName) {
    const resp = await fetch("/api/skill-market/install", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ worker_id: workerId, skill_name: skillName }),
    });
    return resp.json();
  },
  async createCapabilityWorker(capability, name = null) {
    const resp = await fetch("/api/workers/create-capability", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capability, name }),
    });
    return resp.json();
  },

  // ---- Phase 7/8: WorkDesk read models ----
  async listTasks(projectId = null, limit = 200, conversationId = null) {
    const parts = [`limit=${limit}`];
    if (projectId) parts.push(`projectId=${encodeURIComponent(projectId)}`);
    if (conversationId) parts.push(`conversation_id=${encodeURIComponent(conversationId)}`);
    return (await fetch(`/api/tasks?${parts.join("&")}`)).json();
  },
  async getTaskDetail(taskId) {
    const res = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`);
    if (!res.ok) throw new Error("Task not found");
    return res.json();
  },
  async resumeTask(taskId) {
    return (await fetch(`/api/tasks/${encodeURIComponent(taskId)}/resume`, { method: "POST" })).json();
  },
  async listPMs() {
    return (await fetch("/api/pms")).json();
  },
  async getVirtualOffice(conversationId = null) {
    const q = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
    return (await fetch(`/api/virtual-office${q}`)).json();
  },
  async getSettings() {
    return (await fetch("/api/settings")).json();
  },
  async getModelRouter() {
    return (await fetch("/api/model-router")).json();
  },
  async saveChatanywhereKey(apiKey) {
    const r = await fetch("/api/settings/chatanywhere", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey }),
    });
    return r.json();
  },
  async getLearning(scope = "") {
    const q = scope ? `?scope=${encodeURIComponent(scope)}` : "";
    return (await fetch(`/api/learning${q}`)).json();
  },
  // ---- Phase 10: workspace files + notes + code ----
  async getWorkspaceFiles() {
    return (await fetch("/api/workspace/files")).json();
  },
  async readWorkspace(path) {
    return (await fetch(`/api/workspace/read?path=${encodeURIComponent(path)}`)).json();
  },
  async saveWorkspace(path, content) {
    const resp = await fetch("/api/workspace/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, content }),
    });
    return resp.json();
  },
  async uploadWorkspace(files, subdir = "") {
    const fd = new FormData();
    if (subdir) fd.append("subdir", subdir);
    for (const f of files) fd.append("files", f);
    const resp = await fetch("/api/workspace/upload", { method: "POST", body: fd });
    return resp.json();
  },
  async deleteWorkspaceFile(path) {
    const resp = await fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`, { method: "DELETE" });
    return resp.json();
  },
  workspaceFileUrl(path) {
    return `/api/workspace/file?path=${encodeURIComponent(path)}`;
  },
  async runCode(code, language = "python") {
    const resp = await fetch("/api/code/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, language }),
    });
    return resp.json();
  },
  async getNotes(section = "") {
    const q = section ? `?section=${encodeURIComponent(section)}` : "";
    return (await fetch(`/api/notes${q}`)).json();
  },
  async saveNote(payload) {
    const resp = await fetch("/api/notes/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return resp.json();
  },
  async deleteNote(noteId) {
    const resp = await fetch("/api/notes/delete", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_id: noteId }),
    });
    return resp.json();
  },
  async callModelRouter(payload) {
    const resp = await fetch("/api/model-router/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
  },

  async mbVaultChat(message) {
    const resp = await fetch("/api/vault/mb-chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
  },

  // ---- Phase 12: Main Brain auto-sync ----
  async mbSync() {
    const res = await fetch("/api/vault/mb-sync", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || "mb-sync failed");
    return data;
  },

  // ---- Phase 11: vault (obsidian) ----
  async vaultTree(section = "my") {
    return (await fetch(`/api/vault/tree?section=${encodeURIComponent(section)}`)).json();
  },
  async vaultRead(section, path) {
    return (await fetch(`/api/vault/read?section=${encodeURIComponent(section)}&path=${encodeURIComponent(path)}`)).json();
  },
  async vaultSave(section, path, content) {
    const resp = await fetch("/api/vault/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ section, path, content }),
    });
    return resp.json();
  },
  async vaultDelete(section, path) {
    const resp = await fetch(`/api/vault/file?section=${encodeURIComponent(section)}&path=${encodeURIComponent(path)}`, { method: "DELETE" });
    return resp.json();
  },
  async vaultSearch(section, q) {
    return (await fetch(`/api/vault/search?section=${encodeURIComponent(section)}&q=${encodeURIComponent(q)}`)).json();
  },

  // ---- Phase 11: clear history ----
  async clearHistory(scope = "all") {
    const resp = await fetch("/api/clear-history", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope }),
    });
    return resp.json();
  },

  // ---- Phase 11: worker design / studio ----
  async designWorker(githubUrl, subdir = null) {
    const resp = await fetch("/api/workers/design", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ github_url: githubUrl, subdir }),
    });
    return resp.json();
  },
  async applyWorker(profile, mode = "create", mergeInto = null) {
    const resp = await fetch("/api/workers/apply", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile, mode, merge_into: mergeInto }),
    });
    return resp.json();
  },
  async updateWorker(workerId, patch) {
    const resp = await fetch(`/api/workers/${encodeURIComponent(workerId)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    return resp.json();
  },
  async workerStudio(workerId) {
    return (await fetch(`/api/workers/${encodeURIComponent(workerId)}/studio`)).json();
  },

  // ---- Local filesystem (read-only browse) ----
  async localScan(path) {
    const r = await fetch("/api/local/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path || "" }),
    });
    if (!r.ok) {
      let msg = r.status + " " + r.statusText;
      try { msg = (await r.json()).detail || msg; } catch (e) { /* keep */ }
      throw new Error(msg);
    }
    return r.json();
  },

  async localRead(path) {
    const r = await fetch(`/api/local/read?path=${encodeURIComponent(path)}`);
    if (!r.ok) {
      let msg = r.status + " " + r.statusText;
      try { msg = (await r.json()).detail || msg; } catch (e) { /* keep */ }
      throw new Error(msg);
    }
    return r.json();
  },

  fontSimheiUrl() {
    return "/api/font/simhei";
  },

  // ---- Phase 13: Hive (office floor coordination) ----
  async hiveSend({ conversationId, from, to, act, subject, body = "", inReplyTo = null }) {
    const resp = await fetch("/api/hive/messages", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, from, to, act,
                             subject, body, in_reply_to: inReplyTo }),
    });
    return resp.json();
  },
  async hiveMessages(conversationId, agentId = null) {
    const q = new URLSearchParams();
    if (conversationId) q.set("conversation_id", conversationId);
    if (agentId) q.set("agent_id", agentId);
    return (await fetch(`/api/hive/messages?${q}`)).json();
  },
  async hiveBoardGet(conversationId) {
    const q = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
    return (await fetch(`/api/hive/board${q}`)).json();
  },
  async hiveBoardPut(conversationId, text, scribe = "pm") {
    const resp = await fetch("/api/hive/board", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, text, scribe }),
    });
    return resp.json();
  },
  async hiveState(conversationId) {
    const q = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
    return (await fetch(`/api/hive/state${q}`)).json();
  },
  async reorderTasks(conversationId, taskIds) {
    const resp = await fetch("/api/tasks/reorder", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, task_ids: taskIds }),
    });
    return resp.json();
  }
};

// Initialize WebSocket automatically on load
Api.initWebSocket();
