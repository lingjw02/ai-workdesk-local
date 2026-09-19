// AI WorkDesk — local personal AI server
// Run with: npm install && npm start
// Then open http://localhost:PORT in your browser.

require("dotenv").config();
const express = require("express");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const app = express();
const PORT = process.env.PORT || 3787;
const DATA_DIR = path.join(__dirname, "data");
const CONV_DIR = path.join(DATA_DIR, "conversations");
const PROJ_DIR = path.join(DATA_DIR, "projects");
const MEMORY_FILE = path.join(DATA_DIR, "memory.json");

for (const d of [DATA_DIR, CONV_DIR, PROJ_DIR]) {
  if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
}
if (!fs.existsSync(MEMORY_FILE)) fs.writeFileSync(MEMORY_FILE, "{}");

app.use(express.json({ limit: "30mb" }));
app.use(express.static(path.join(__dirname, "public")));

// ---------------------------------------------------------------------------
// tiny file-backed storage
// ---------------------------------------------------------------------------
function readJSON(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); }
  catch (e) { return fallback; }
}
function writeJSON(file, obj) {
  fs.writeFileSync(file, JSON.stringify(obj, null, 2));
}
function newId() { return crypto.randomUUID(); }

// ---------------------------------------------------------------------------
// model / mode configuration
// ---------------------------------------------------------------------------
// Model IDs are OpenRouter slugs — "provider/model", e.g. "anthropic/claude-sonnet-4.5".
// Browse the full list at https://openrouter.ai/models and swap any of these in .env.
const MODELS = {
  instant: process.env.INSTANT_MODEL || "openai/gpt-4o-mini",
  expert: process.env.EXPERT_MODEL || "anthropic/claude-sonnet-4.5",
  vision: process.env.EXPERT_MODEL || "anthropic/claude-sonnet-4.5",
  worker: process.env.WORKER_MODEL || "anthropic/claude-sonnet-4.5",
};
// Reasoning-effort tuning is skipped for "instant" (fast/cheap models often
// don't support it); sent for everything else, with a fallback below in case
// the chosen model rejects the parameter.
const REASONING_CAPABLE = new Set(["expert", "vision", "worker"]);

const EFFORT_MAP = { low: "low", normal: "medium", long: "high" };
const MAXTOKENS_MAP = { low: 1024, normal: 2048, long: 4096 };

// ---------------------------------------------------------------------------
// OpenRouter API call (OpenAI-compatible chat completions)
// ---------------------------------------------------------------------------
async function callOpenRouterRaw(body) {
  const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
      "HTTP-Referer": process.env.APP_URL || "http://localhost:3787",
      "X-Title": process.env.APP_NAME || "AI WorkDesk",
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    const msg = (data && data.error && data.error.message) || res.statusText;
    const err = new Error(`OpenRouter API error (${res.status}): ${msg}`);
    err.status = res.status;
    throw err;
  }
  const choice = data.choices && data.choices[0];
  const text = choice && choice.message ? String(choice.message.content || "").trim() : "";
  return text;
}

async function callClaude({ modeKey, system, messages, deepthink }) {
  if (!process.env.OPENROUTER_API_KEY) {
    throw new Error("No OPENROUTER_API_KEY set. Copy .env.example to .env and add your OpenRouter key.");
  }
  const model = MODELS[modeKey] || MODELS.worker;
  const level = deepthink || "normal";
  const fullMessages = system ? [{ role: "system", content: system }, ...messages] : messages;
  const body = { model, max_tokens: MAXTOKENS_MAP[level] || 2048, messages: fullMessages };

  if (REASONING_CAPABLE.has(modeKey)) {
    try {
      return await callOpenRouterRaw({ ...body, reasoning: { effort: EFFORT_MAP[level] || "medium" } });
    } catch (e) {
      // Some models on OpenRouter reject the reasoning param outright — retry plain.
      if (e.status === 400) return await callOpenRouterRaw(body);
      throw e;
    }
  }
  return await callOpenRouterRaw(body);
}

function toApiContent(blocks) {
  if (typeof blocks === "string") return blocks;
  if (!Array.isArray(blocks)) return "";
  const hasImage = blocks.some((b) => b.type === "image_url");
  if (!hasImage) {
    const t = blocks.find((b) => b.type === "text");
    return t ? t.text : "";
  }
  return blocks;
}

function extractJSON(text) {
  let t = String(text).replace(/```json/gi, "").replace(/```/g, "").trim();
  const start = t.indexOf("{");
  const end = t.lastIndexOf("}");
  if (start === -1 || end === -1) throw new Error("No JSON object found in model response");
  return JSON.parse(t.slice(start, end + 1));
}

function parseCodeFiles(text) {
  const files = {};
  const fenceRe = /```[a-zA-Z0-9_+-]*\n([\s\S]*?)```/g;
  let m, idx = 0;
  while ((m = fenceRe.exec(text)) !== null) {
    idx++;
    const block = m[1];
    const nl = block.indexOf("\n");
    const firstLine = nl === -1 ? block : block.slice(0, nl);
    const rest = nl === -1 ? "" : block.slice(nl + 1);
    const fm = firstLine.match(/(?:\/\/|#|--)\s*FILE:\s*(.+)/i);
    const filename = fm ? fm[1].trim() : `file_${idx}.txt`;
    files[filename] = fm ? rest : block;
  }
  if (Object.keys(files).length === 0) files["notes.txt"] = text.trim();
  return files;
}

// ---------------------------------------------------------------------------
// web search (Brave Search API — optional)
// ---------------------------------------------------------------------------
async function webSearch(query, count = 5) {
  if (!process.env.BRAVE_API_KEY) return null;
  try {
    const url = `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=${count}`;
    const res = await fetch(url, {
      headers: { Accept: "application/json", "X-Subscription-Token": process.env.BRAVE_API_KEY },
    });
    if (!res.ok) return null;
    const data = await res.json();
    const results = (data.web && data.web.results) || [];
    return results.slice(0, count).map((r) => ({ title: r.title, url: r.url, snippet: r.description }));
  } catch (e) {
    return null;
  }
}
function formatSearchBlock(results, query) {
  if (!results || results.length === 0) {
    return `[No live web search results available for "${query}" — BRAVE_API_KEY is not set, or the search failed. Reasoning from general knowledge only.]`;
  }
  return (
    `[LIVE WEB SEARCH RESULTS for "${query}"]\n` +
    results.map((r, i) => `${i + 1}. ${r.title}\n   ${r.snippet}\n   ${r.url}`).join("\n")
  );
}

// ---------------------------------------------------------------------------
// memory (durable user preferences, used across chat + workspace)
// ---------------------------------------------------------------------------
function loadMemory() { return readJSON(MEMORY_FILE, {}); }
function saveMemoryPatch(patch) {
  const mem = loadMemory();
  Object.assign(mem, patch);
  writeJSON(MEMORY_FILE, mem);
  return mem;
}

// =============================================================================
// NORMAL CHAT
// =============================================================================
function convPath(id) { return path.join(CONV_DIR, `${id}.json`); }

app.get("/api/conversations", (req, res) => {
  const files = fs.readdirSync(CONV_DIR).filter((f) => f.endsWith(".json"));
  const list = files.map((f) => {
    const c = readJSON(path.join(CONV_DIR, f), null);
    if (!c) return null;
    return { id: c.id, title: c.title, updatedAt: c.updatedAt };
  }).filter(Boolean).sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""));
  res.json(list);
});

app.post("/api/conversations", (req, res) => {
  const id = newId();
  const conv = { id, title: "New chat", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), messages: [] };
  writeJSON(convPath(id), conv);
  res.json(conv);
});

app.get("/api/conversations/:id", (req, res) => {
  const conv = readJSON(convPath(req.params.id), null);
  if (!conv) return res.status(404).json({ error: "not found" });
  res.json(conv);
});

app.delete("/api/conversations/:id", (req, res) => {
  try { fs.unlinkSync(convPath(req.params.id)); } catch (e) {}
  res.json({ ok: true });
});

const MB_PERSONA = (memory) => {
  const memStr = Object.keys(memory).length
    ? Object.entries(memory).map(([k, v]) => `${k}: ${v}`).join("; ")
    : "none yet";
  return `You are the Main Brain of the user's personal local AI desk. Be direct, warm, and genuinely useful. Known durable user preferences: ${memStr}.
If the user just stated a genuinely durable preference worth remembering long-term (tone, language, formatting, recurring context), end your reply with one line exactly in this format on its own: [[REMEMBER: key=value]] — omit this line entirely otherwise. This line will be stripped before the user sees your reply.`;
};

app.post("/api/chat", async (req, res) => {
  try {
    const { conversationId, mode = "instant", deepthink = "normal", search = false, text = "", images = [] } = req.body;
    let conv = conversationId ? readJSON(convPath(conversationId), null) : null;
    if (!conv) {
      const id = conversationId || newId();
      conv = { id, title: text.slice(0, 48) || "New chat", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), messages: [] };
    }

    let searchBlock = "";
    if (search && text.trim()) {
      const results = await webSearch(text.trim());
      searchBlock = formatSearchBlock(results, text.trim()) + "\n\n";
    }

    const contentBlocks = [{ type: "text", text: searchBlock + text }];
    for (const img of images || []) {
      contentBlocks.push({ type: "image_url", image_url: { url: `data:${img.mediaType};base64,${img.data}` } });
    }

    conv.messages.push({ role: "user", content: contentBlocks });

    const apiMessages = conv.messages.map((m) => ({ role: m.role, content: toApiContent(m.content) }));
    const memory = loadMemory();
    const modeKey = mode === "vision" ? "vision" : mode === "expert" ? "expert" : "instant";
    let reply = await callClaude({ modeKey, system: MB_PERSONA(memory), messages: apiMessages, deepthink });

    const rememberMatch = reply.match(/\[\[REMEMBER:\s*([^=]+)=([^\]]+)\]\]/);
    if (rememberMatch) {
      saveMemoryPatch({ [rememberMatch[1].trim()]: rememberMatch[2].trim() });
      reply = reply.replace(rememberMatch[0], "").trim();
    }

    conv.messages.push({ role: "assistant", content: [{ type: "text", text: reply }] });
    conv.updatedAt = new Date().toISOString();
    if (conv.title === "New chat" && text) conv.title = text.slice(0, 48);
    writeJSON(convPath(conv.id), conv);

    res.json({ conversationId: conv.id, reply, memory: loadMemory() });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get("/api/memory", (req, res) => res.json(loadMemory()));

// =============================================================================
// WORKSPACE (projects, workers, PM orchestration)
// =============================================================================
function projPath(id) { return path.join(PROJ_DIR, `${id}.json`); }

const WORKER_META = {
  researcher: { name: "Researcher", desc: "gathers & synthesizes information" },
  coder: { name: "Coder", desc: "writes & maintains code files" },
  documenter: { name: "Documenter", desc: "drafts & maintains the project document" },
};

function emptyNode() { return { status: "idle", log: [] }; }

app.get("/api/projects", (req, res) => {
  const files = fs.readdirSync(PROJ_DIR).filter((f) => f.endsWith(".json"));
  const list = files.map((f) => {
    const p = readJSON(path.join(PROJ_DIR, f), null);
    if (!p) return null;
    return { id: p.id, name: p.name, workers: p.workers, updatedAt: p.updatedAt, status: p.pm.status };
  }).filter(Boolean).sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""));
  res.json(list);
});

app.post("/api/projects", (req, res) => {
  const { name, workers } = req.body;
  const id = newId();
  const chosen = (workers && workers.length ? workers : ["researcher", "coder", "documenter"]).filter((w) => WORKER_META[w]);
  const nodes = {};
  chosen.forEach((w) => { nodes[w] = emptyNode(); if (w === "coder") nodes[w].files = {}; if (w === "documenter") nodes[w].doc = ""; if (w === "researcher") nodes[w].notes = []; });
  const project = {
    id,
    name: name || "Untitled project",
    workers: chosen,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    pm: { status: "idle" },
    nodes,
    messages: [],
    terminal: [],
  };
  writeJSON(projPath(id), project);
  res.json(project);
});

app.get("/api/projects/:id", (req, res) => {
  const p = readJSON(projPath(req.params.id), null);
  if (!p) return res.status(404).json({ error: "not found" });
  res.json(p);
});

app.delete("/api/projects/:id", (req, res) => {
  try { fs.unlinkSync(projPath(req.params.id)); } catch (e) {}
  res.json({ ok: true });
});

function term(project, who, text) {
  project.terminal.push({ ts: new Date().toISOString(), who, text });
}
function persist(project) {
  project.updatedAt = new Date().toISOString();
  writeJSON(projPath(project.id), project);
}

const PM_SYSTEM = (project, memory) => {
  const memStr = Object.keys(memory).length ? Object.entries(memory).map(([k, v]) => `${k}: ${v}`).join("; ") : "none yet";
  const workerList = project.workers.map((w) => `${w} (${WORKER_META[w].desc})`).join(", ");
  return `You are the Project Manager (PM) for the local workspace project "${project.name}". Active workers on this project: ${workerList}.
Known durable user preferences: ${memStr}.

Read the user's latest message and decide whether to answer it directly or delegate to one or more of the active workers. Respond with STRICT JSON only, no markdown fences, no prose outside the JSON:
{"reply":"a short message to the user (1-3 sentences) about what you're doing or answering","assign":{"researcher":"precise instruction, only if researcher is active and genuinely needed","coder":"precise instruction, only if coder is active and genuinely needed","documenter":"precise instruction, only if documenter is active and genuinely needed"}}
Only include a worker key in "assign" if that worker is in the active worker list AND needs to act right now. If nothing needs delegating, set "assign" to {} and just reply.`;
};

const WORKER_SYSTEM = {
  researcher: `You are the Researcher on this project. You'll be given an instruction and possibly live web search results. Produce a concise research note: 3-6 bullet findings, each a clear takeaway, citing source titles when search results were provided. If no live search results were given, say so plainly in one line and reason from general knowledge instead. Keep it under 220 words. Output only the note.`,
  coder: `You are the Coder on this project. Given the instruction, produce the necessary code. Output ONLY one or more fenced code blocks; the first line inside each block must be a comment "FILE: filename.ext" in that language's comment style (// FILE: app.js or # FILE: app.py), followed by the full file content. You may output multiple files. After the code block(s) add at most 2 sentences on key decisions.`,
  documenter: `You are the Documenter on this project. Given the instruction and the project's current document (if any), write the full replacement content for the shared project document in clean markdown. Output ONLY the markdown document content, no meta commentary.`,
};

async function runResearcher(project, instruction) {
  const node = project.nodes.researcher;
  node.status = "working"; persist(project);
  let searchBlock = "";
  const results = await webSearch(instruction);
  searchBlock = formatSearchBlock(results, instruction) + "\n\n";
  const note = await callClaude({
    modeKey: "worker",
    system: WORKER_SYSTEM.researcher,
    messages: [{ role: "user", content: searchBlock + "Instruction: " + instruction }],
    deepthink: "normal",
  });
  node.notes.push({ ts: new Date().toISOString(), instruction, note });
  node.status = "done";
  term(project, "researcher", note);
  persist(project);
  return note;
}

async function runCoder(project, instruction) {
  const node = project.nodes.coder;
  node.status = "working"; persist(project);
  const existing = Object.keys(node.files).length
    ? "Existing files:\n" + Object.entries(node.files).map(([f, c]) => `--- ${f} ---\n${c}`).join("\n\n") + "\n\n"
    : "";
  const out = await callClaude({
    modeKey: "worker",
    system: WORKER_SYSTEM.coder,
    messages: [{ role: "user", content: existing + "Instruction: " + instruction }],
    deepthink: "normal",
  });
  const files = parseCodeFiles(out);
  Object.assign(node.files, files);
  node.status = "done";
  term(project, "coder", `Updated ${Object.keys(files).join(", ")}`);
  persist(project);
  return files;
}

async function runDocumenter(project, instruction) {
  const node = project.nodes.documenter;
  node.status = "working"; persist(project);
  const context = node.doc ? `Current document:\n${node.doc}\n\n` : "";
  const doc = await callClaude({
    modeKey: "worker",
    system: WORKER_SYSTEM.documenter,
    messages: [{ role: "user", content: context + "Instruction: " + instruction }],
    deepthink: "normal",
  });
  node.doc = doc;
  node.status = "done";
  term(project, "documenter", "Document updated");
  persist(project);
  return doc;
}

const WORKER_RUNNERS = { researcher: runResearcher, coder: runCoder, documenter: runDocumenter };

app.post("/api/projects/:id/message", async (req, res) => {
  const project = readJSON(projPath(req.params.id), null);
  if (!project) return res.status(404).json({ error: "not found" });
  const { text } = req.body;
  try {
    project.messages.push({ role: "user", text, ts: new Date().toISOString() });
    term(project, "you", text);
    project.pm.status = "working"; persist(project);

    const memory = loadMemory();
    const recentTerminal = project.terminal.slice(-12).map((t) => `[${t.who}] ${t.text}`).join("\n");
    const pmMessages = [{ role: "user", content: `Recent project activity:\n${recentTerminal}\n\nUser's new message: ${text}` }];
    const raw = await callClaude({ modeKey: "worker", system: PM_SYSTEM(project, memory), messages: pmMessages, deepthink: "normal" });

    let decision;
    try { decision = extractJSON(raw); }
    catch (e) { decision = { reply: raw, assign: {} }; }

    project.messages.push({ role: "pm", text: decision.reply, ts: new Date().toISOString() });
    term(project, "pm", decision.reply);
    project.pm.status = "idle"; persist(project);

    const assign = decision.assign || {};
    const jobs = Object.keys(assign).filter((w) => project.workers.includes(w) && WORKER_RUNNERS[w]);
    await Promise.all(jobs.map((w) => WORKER_RUNNERS[w](project, assign[w]).catch((e) => {
      project.nodes[w].status = "fail";
      term(project, w, `Error: ${e.message}`);
      persist(project);
    })));

    const finalProject = readJSON(projPath(project.id), project);
    res.json(finalProject);
  } catch (e) {
    project.pm.status = "fail";
    persist(project);
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, () => {
  console.log(`\n  AI WorkDesk running → http://localhost:${PORT}\n`);
  if (!process.env.OPENROUTER_API_KEY) {
    console.log("  ⚠  No OPENROUTER_API_KEY found. Copy .env.example to .env and add your key.\n");
  }
  if (!process.env.BRAVE_API_KEY) {
    console.log("  ℹ  No BRAVE_API_KEY set — live web search is disabled until you add one.\n");
  }
});
