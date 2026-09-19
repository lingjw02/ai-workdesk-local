/* ============================================================
 * vault.js - Obsidian-style note vault (Phase 11)
 * File tree | markdown editor + preview | [[wiki links]] | search
 * ============================================================ */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const state = {
    section: "my",
    current: null,
    files: [],
    editorDirty: false,
  };

  function notify(msg, ok = true) {
    const el = document.getElementById("vaultStatus");
    if (el) {
      el.textContent = msg;
      el.className = ok ? "vault-status ok" : "vault-status err";
      setTimeout(() => { if (el) el.textContent = ""; }, 2600);
    }
  }

  function mdToHtml(md) {
    let t = String(md || "");
    // code blocks first
    t = t.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) =>
      `<pre class="vault-code"><code>${esc(code)}</code></pre>`);
    // wiki links -> clickable
    t = t.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (m, target, label) =>
      `<a class="vault-wikilink" data-target="${esc(target.trim())}">${esc(label || target)}</a>`);
    // headers
    t = t.replace(/^### (.*)$/gm, "<h3>$1</h3>")
         .replace(/^## (.*)$/gm, "<h2>$1</h2>")
         .replace(/^# (.*)$/gm, "<h1>$1</h1>");
    // bold / italic / inline code
    t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
         .replace(/\*([^*]+)\*/g, "<em>$1</em>")
         .replace(/`([^`]+)`/g, "<code>$1</code>");
    // lists
    t = t.replace(/^- (.*)$/gm, "<li>$1</li>");
    t = t.replace(/(<li>[\s\S]*?<\/li>)(?!\s*<li>)/g, "<ul>$1</ul>");
    // links
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
      `<a href="$2" target="_blank" rel="noopener">$1</a>`);
    // hashtags -> chips (avoid html attr leftovers)
    t = t.replace(/#([\w\u4e00-\u9fa5][\w\u4e00-\u9fa5-]*)/g,
      `<span class="vault-tag" data-tag="$1">#$1</span>`);
    // paragraphs
    t = t.split(/\n{2,}/).map((p) => {
      if (/^\s*<(h\d|ul|pre|ol)/.test(p)) return p;
      return `<p>${p.replace(/\n/g, "<br/>")}</p>`;
    }).join("\n");
    return t;
  }

  function renderTree() {
    const box = $("vaultTree");
    if (!box) return;
    if (!state.files.length) {
      box.innerHTML = `<div class="muted" style="padding:10px;font-size:12px;">No notes yet.</div>`;
      return;
    }
    box.innerHTML = state.files.map((f) => `
      <div class="vault-file ${state.current === f.path ? "active" : ""}" data-path="${esc(f.path)}">
        <span class="vault-file-ico">📄</span>
        <span class="vault-file-name">${esc(f.name)}</span>
      </div>`).join("");
    box.querySelectorAll(".vault-file").forEach((el) => {
      el.addEventListener("click", () => openNote(el.dataset.path));
    });
  }

  async function refreshTree() {
    const r = await Api.vaultTree(state.section);
    state.files = r.files || [];
    renderTree();
  }

  async function openNote(path) {
    state.current = path;
    state.editorDirty = false;
    const r = await Api.vaultRead(state.section, path);
    if (r.error) { notify(r.error, false); return; }
    const ed = $("vaultEditor");
    ed.value = r.content;
    ed.dataset.path = path;
    renderPreview();
    renderLinks(r.links || []);
    $("vaultFileName").value = path;
    updateWordCount();
    renderTree();
    notify(`Opened ${path}`);
  }

  function renderPreview() {
    const box = $("vaultPreview");
    const ed = $("vaultEditor");
    box.innerHTML = mdToHtml(ed.value);
    box.querySelectorAll(".vault-wikilink").forEach((a) => {
      a.addEventListener("click", () => {
        const target = a.dataset.target;
        const hit = state.files.find((f) => f.name === target + ".md" || f.path === target);
        if (hit) openNote(hit.path);
        else notify(`No note named "${target}" - create it?`, false);
      });
    });
  }

  function renderLinks(links) {
    const box = $("vaultLinks");
    if (!links.length) { box.innerHTML = `<div class="muted" style="font-size:12px;">No [[wiki links]] in this note.</div>`; return; }
    box.innerHTML = links.map((l) => {
      const exists = state.files.some((f) => f.name === l + ".md");
      return `<span class="vault-link-chip ${exists ? "" : "missing"}" data-l="${esc(l)}">[[${esc(l)}]]</span>`;
    }).join("");
    box.querySelectorAll(".vault-link-chip").forEach((c) => {
      c.addEventListener("click", () => {
        const hit = state.files.find((f) => f.name === c.dataset.l + ".md");
        if (hit) openNote(hit.path);
        else {
          const path = c.dataset.l + ".md";
          $("vaultEditor").value = `# ${c.dataset.l}\n\n`;
          $("vaultEditor").dataset.path = path;
          $("vaultFileName").value = path;
          state.current = path;
          renderPreview();
          notify("New note scaffolded - Save to create it.");
        }
      });
    });
  }

  async function saveNote() {
    const ed = $("vaultEditor");
    const path = $("vaultFileName").value.trim() || ed.dataset.path;
    if (!path) { notify("No filename", false); return; }
    const r = await Api.vaultSave(state.section, path, ed.value);
    if (r.ok) {
      state.editorDirty = false;
      state.current = path;
      await refreshTree();
      renderPreview();
      updateWordCount();
      notify(`Saved ${path} (${r.bytes} bytes)`);
    } else notify(r.error || "save failed", false);
  }

  async function newNote() {
    state.current = null;
    const ed = $("vaultEditor");
    ed.value = "";
    ed.dataset.path = "";
    $("vaultFileName").value = "untitled.md";
    renderPreview();
    renderLinks([]);
    updateWordCount();
    notify("New note - type markdown, then Save.");
  }

  async function deleteNote() {
    const ed = $("vaultEditor");
    const path = ed.dataset.path;
    if (!path) return;
    if (!confirm(`Delete ${path}?`)) return;
    const r = await Api.vaultDelete(state.section, path);
    if (r.ok) {
      ed.value = ""; ed.dataset.path = "";
      $("vaultFileName").value = "untitled.md";
      state.current = null;
      await refreshTree();
      renderPreview();
      renderLinks([]);
      notify("Deleted");
    } else notify(r.error || "delete failed", false);
  }

  async function doSearch() {
    const q = $("vaultSearchInput").value.trim();
    const box = $("vaultSearchResults");
    if (!q) { box.innerHTML = ""; return; }
    const r = await Api.vaultSearch(state.section, q);
    box.innerHTML = (r.hits || []).map((h) => `
      <div class="vault-hit" data-p="${esc(h.path)}">
        <div class="vault-hit-path">${esc(h.path)}</div>
        <div class="vault-hit-snippet">${esc(h.snippet)}</div>
      </div>`).join("") || `<div class="muted">No matches.</div>`;
    box.querySelectorAll(".vault-hit").forEach((el) => {
      el.addEventListener("click", () => openNote(el.dataset.p));
    });
  }

  function switchSection(section) {
    state.section = section;
    render();  // rebuild pane: section-specific banner / MB memory panel
  }

  function render(initialSection) {
    if (initialSection && (initialSection === "my" || initialSection === "mb")) {
      state.section = initialSection;
    }
    const p = $("vaultPanel");
    p.innerHTML = `
      <div class="p10-tabs" id="vaultTabs">
        <button class="p10-tab ${state.section === "my" ? "active" : ""}" data-t="my">My Vault</button>
        <button class="p10-tab ${state.section === "mb" ? "active" : ""}" data-t="mb">&#129504; Main Brain Memory</button>
      </div>
      ${state.section === "mb" ? `
      <div class="mb-banner">
        <span>Main Brain 自动记录它的知识：学习的经验、需要知道的信息、待办事项。</span>
        <button class="btn-primary btn-sm" id="mbSyncBtn">⟳ Sync Main Brain</button>
      </div>` : ""}
      <div class="vault-layout">
        <aside class="vault-side">
          <div class="vault-search-row">
            <input id="vaultSearchInput" placeholder="Search notes..." />
          </div>
          <div id="vaultSearchResults" class="vault-search-results"></div>
          <div class="vault-side-head">
            <span class="ws-file-title">FILES</span>
            <button class="btn-secondary" id="vaultNewBtn" title="New note">+</button>
          </div>
          <div id="vaultTree" class="vault-tree"></div>
        </aside>
        <div class="vault-main">
          <div class="code-toolbar">
            <input id="vaultFileName" value="untitled.md" />
            <span id="vaultWordCount" class="vault-wordcount"></span>
            <button class="btn-primary" id="vaultSaveBtn">Save</button>
            <button class="btn-secondary" id="vaultExportBtn">⇩ Export .md</button>
            <button class="btn-secondary" id="vaultDeleteBtn">Delete</button>
          </div>
          <div class="vault-editor-row">
            <textarea id="vaultEditor" spellcheck="false" placeholder="# Note title&#10;&#10;Start writing markdown... [[link to another note]]"></textarea>
            <div id="vaultPreview" class="vault-preview"></div>
          </div>
          <div class="vault-links-row">
            <span class="ws-file-title">WIKI LINKS</span>
            <div id="vaultLinks"></div>
          </div>
          ${state.section === "mb" ? `
          <div class="mb-memory-box">
            <div class="ws-file-title">GLOBAL MEMORY - MAIN BRAIN 长期记住</div>
            <div id="mbMemoryList" class="mb-memory-list"></div>
            <div class="mb-memory-edit">
              <input id="mbMemKey" placeholder="key (e.g. 用户偏好)" />
              <input id="mbMemVal" placeholder="value" />
              <button class="btn-primary btn-sm" id="mbMemAdd">+ 记录</button>
            </div>
          </div>` : ""}
          <div id="vaultStatus" class="vault-status"></div>
        </div>
      </div>
      <div id="mbChatDock" class="mb-chat-dock">
        <div class="mb-chat-head">💬 Tell Main Brain what to store in the Vault</div>
        <div id="mbChatLog" class="mb-chat-log"></div>
        <div class="mb-chat-input-row">
          <input id="mbChatInput" placeholder='e.g. 记住：每周一检查服务器日志并存入 Vault , "save this: ..."' />
          <button class="btn-primary btn-sm" id="mbChatSend">Send to MB</button>
        </div>
      </div>`;
    document.querySelectorAll("#vaultTabs .p10-tab").forEach((t) =>
      t.addEventListener("click", () => switchSection(t.dataset.t)));
    const mbSyncBtn = $("mbSyncBtn");
    if (mbSyncBtn) mbSyncBtn.addEventListener("click", mbSync);
    const mbMemAdd = $("mbMemAdd");
    if (mbMemAdd) mbMemAdd.addEventListener("click", mbMemAddHandler);
    const chatSend = $("mbChatSend");
    const chatInp = $("mbChatInput");
    if (chatSend && chatInp) {
      const sendChat = async () => {
        const msg = chatInp.value.trim();
        if (!msg) return;
        chatInp.value = "";
        const log = $("mbChatLog");
        if (log) {
          log.innerHTML += `<div class="mb-chat-user">🧑 ${esc(msg)}</div>`;
          log.innerHTML += `<div class="mb-chat-mb">⏳ Main Brain is thinking…</div>`;
          log.scrollTop = log.scrollHeight;
        }
        const r = await Api.mbVaultChat(msg).catch(() => ({ ok: false, error: "backend unavailable" }));
        if (log) {
          log.innerHTML = log.innerHTML.replace(/<div class="mb-chat-mb">⏳.*?<\/div>$/, "");
          log.innerHTML += `<div class="mb-chat-mb">🧠 ${esc(r.ok ? r.reply : (r.error || "failed"))}</div>`;
          log.scrollTop = log.scrollHeight;
        }
        await refreshTree();
      };
      chatSend.addEventListener("click", sendChat);
      chatInp.addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
    }
    if (state.section === "mb") renderMbMemory();
    $("vaultSaveBtn").addEventListener("click", saveNote);
    $("vaultNewBtn").addEventListener("click", newNote);
    $("vaultDeleteBtn").addEventListener("click", deleteNote);
    $("vaultSearchInput").addEventListener("input", doSearch);
    $("vaultEditor").addEventListener("input", () => {
      state.editorDirty = true;
      updateWordCount();
      renderPreview();
    });
    const exportBtn = $("vaultExportBtn");
    if (exportBtn) exportBtn.addEventListener("click", exportNote);
    const prev = $("vaultPreview");
    if (prev) prev.addEventListener("click", (e) => {
      const tag = e.target.closest(".vault-tag");
      if (!tag) return;
      const q = $("vaultSearchInput");
      if (q) { q.value = tag.dataset.tag; doSearch(); }
    });
    updateWordCount();
    refreshTree().then(() => {
      const first = state.files[0];
      if (first) openNote(first.path);
      else newNote();
    });
  }

  function updateWordCount() {
    const el = $("vaultWordCount");
    const ed = $("vaultEditor");
    if (!el || !ed) return;
    const n = (ed.value || "").length;
    const words = (ed.value || "").trim() ? (ed.value.trim().split(/\s+/).length) : 0;
    el.textContent = `${words} words , ${n} chars`;
  }

  function exportNote() {
    const ed = $("vaultEditor");
    const fn = ($("vaultFileName").value || "note").replace(/[\\/:*?"<>|]/g, "_");
    const blob = new Blob([ed.value || ""], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fn.endsWith(".md") ? fn : fn + ".md";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 3000);
    notify(`Exported ${a.download}`);
  }

  async function mbSync() {
    notify("Main Brain syncing knowledge into memory vault...");
    try {
      const r = await Api.mbSync();
      notify(`Main Brain memory synced (${r.count} notes)`);
      await refreshTree();
      renderMbMemory();
    } catch (e) { notify(e.message || "sync failed", false); }
  }

  async function renderMbMemory() {
    const list = $("mbMemoryList");
    if (!list) return;
    const mem = await Api.getMemory().catch(() => ({ globalMemory: {} }));
    const g = mem.globalMemory || {};
    const entries = Object.entries(g);
    list.innerHTML = entries.length
      ? entries.map(([k, v]) =>
          `<div class="mb-mem-row"><span class="mb-mem-key">${esc(k)}</span><span class="mb-mem-val">${esc(typeof v === "string" ? v : JSON.stringify(v))}</span></div>`).join("")
      : `<div class="muted">还没有全局记忆 -- Main Brain 学会的偏好会出现在这里。</div>`;
  }

  async function mbMemAddHandler() {
    const k = $("mbMemKey").value.trim();
    const v = $("mbMemVal").value.trim();
    if (!k || !v) { notify("Key and value required", false); return; }
    await Api.updateMemory({ [k]: v });
    $("mbMemKey").value = ""; $("mbMemVal").value = "";
    await renderMbMemory();
    await mbSync();
    notify("记入 Main Brain memory");
  }

  window.Vault = { render, openNote, switchSection };
})();
