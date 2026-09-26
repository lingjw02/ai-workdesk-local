<div align="center">

# AI WorkDesk OS / EMILIA LAB

### A personal AI operating system for Windows. One Main Brain understands your goals, plans and supervises work, assembles persistent AI employees, coordinates project teams, verifies results through QA, learns from history, and drives the machine with user-approved autonomy.

**The AI model is not the product. The product is the WorkDesk orchestration system around the model.**

Local First · USER > Main Brain > PM > Worker · QA-1 Requirement Gate + QA-2 Output Gate with Selective Rework · Skill-Based Routing (SBR) · 4-Layer Memory Isolation · 4-Level Permission System · Hybrid Local/Cloud Model Router · Visual Office Floor · Obsidian-Style Vault · Boot Splash & Desktop Companion

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Uvicorn-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/Database-SQLite%20(WAL)-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![WebSockets](https://img.shields.io/badge/Streaming-WebSockets-orange?style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Privacy First](https://img.shields.io/badge/Privacy-100%25%20Local--First-success?style=flat-square)](#-privacy--security-invariants)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](./LICENSE)

🌐 **English** · [中文](./README.zh.md)　|　[📥 Quick Start](#-quick-start-in-30-seconds) · [✨ Highlights](#-highlights) · [🏗️ Architecture](#️-the-vision) · [🖥️ Current Build](#-current-build-emilia-lab-studio) · [🗺️ Roadmap](#-roadmap)

</div>

---

## 💡 The One-Sentence Concept

A Windows-based personal AI operating system where one **Main Brain** understands the user's goals, plans and supervises work, creates or selects persistent **AI employees** (Workers) with specialized skills, coordinates project teams under **Project Managers (PM)**, verifies results through **QA**, learns from historical experience, and controls computer tools with **user-approved autonomy**.

The user tells the system **the goal, not every individual step**. Main Brain figures out the work. That is what makes it an AI OS rather than merely an agent framework.

---

## ✨ Highlights

- 🧠 **Main Brain Orchestrator**: Understands natural language, runs Requirement QA, plans execution, selects or creates workers, routes models, manages permissions, owns global memory, supervises PMs, and holds final authority over every decision.
- 🏢 **Hierarchical Authority**: `USER > MAIN BRAIN > PROJECT MANAGER > WORKER`. Escalation runs in the same order whenever a decision exceeds a level's mandate.
- 🛡️ **Dual QA Verification Gates**:
  - **QA-1 (Pre-Execution)**: Detects ambiguity, contradictions, missing information, and capability gaps before any token is spent.
  - **QA-2 (Post-Execution)**: Audits accuracy, truthfulness, completeness, requirement compliance, formatting, logic, and source validity. On failure it produces a structured FailureReport and triggers **selective rework** - only the failed worker and its downstream dependencies are redone, never the whole project.
- 📦 **Persistent AI Employees**: Workers and PMs are not disposable agents. They keep identity, personality, skills, tools, permissions, memory rules, experience, and performance statistics across sessions and projects.
- 🔀 **Skill-Based Routing (SBR)**: The system routes work through the right skill, worker, and model for the task. The worker never cares whether the model behind it is local or cloud; the routing layer decides by complexity, privacy, cost, speed, context size, capability, and user preference.
- 🧩 **Worker Creation from GitHub Skills**: Paste any GitHub repository URL containing `SKILL.md` files. The system recursively scans sub-folders, reads skill frontmatter, and auto-designs a worker - no manual naming needed. Similar workers can be merged; every worker remains editable afterward.
- 🔒 **4-Level Permission System**: `Automatic (safe routine) → Notify (execute then inform) → Ask (user must approve) → Explicit (high-impact action requires direct confirmation)`. Having a tool never means unlimited permission to use it.
- 🧠 **4-Layer Memory Isolation**: Global Memory, Project Memory, Worker Memory, and Group Memory are strictly separated. Cross-project access is NEVER automatic; Main Brain grants it explicitly.
- 📝 **Obsidian-Style Vault**: Your personal notes and Main Brain's living memory (global-memory, lessons, todo, pm-knowledge) live side by side with `[[wiki links]]`, full-text search, and a built-in chat to tell Main Brain what to store.
- 🖥️ **Visual Office & Work Graph**: Every chat session carries a resizable "THIS CHAT SESSION" panel with TASKS / OFFICE / APPROVALS / RESULT / PROJECT tabs, plus an Office Workflow View in the main chat area.
- 🎬 **Boot Experience**: Animated Main Brain startup sequence (SVG draw-on, status stagger, progress line) that respects `prefers-reduced-motion` and is skippable.
- 🌸 **Emilia Desktop Companion**: A floating character companion with state machines, typing reaction, and strictly loopback-local vision.

---

## 🏗️ The Vision

### Ultimate Architecture

```
                         ┌───────────┐
                         │   USER    │
                         └─────┬─────┘
                               ▼
                     ╔══════════════════╗
                     ║    MAIN BRAIN    ║
                     ║  Understand      ║
                     ║  Think  Plan     ║
                     ║  Delegate        ║
                     ║  Remember        ║
                     ║  Verify  Protect ║
                     ╚════════╤═════════╝
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
     KNOWLEDGE             PROJECTS             WORKERS
      LIBRARY                 │                    │
                              ▼                    ▼
                            PMs                 SKILLS
                              │                    │
                              └─────────┬──────────┘
                                        ▼
                                   TASK GROUPS
                                        │
                               ┌────────┼────────┐
                               ▼        ▼        ▼
                            Worker   Worker   Worker
                               │        │        │
                               └────────┼────────┘
                                        ▼
                                       QA
                                        │
                                 ┌──────┴──────┐
                                 ▼             ▼
                               FAIL           PASS
                                 │             │
                                 ▼             ▼
                                PM           FINAL
                                 │             │
                                 ▼             ▼
                              REWORK          USER
```

### The Main Brain (MB)

The global intelligence and authority. It knows the WorkDesk not by stuffing everything into one context, but through access to the right memory, knowledge, and registry systems.

| Responsibility | Purpose |
| :--- | :--- |
| Requirement understanding | Turn natural language into structured requirements |
| Requirement QA | Detect ambiguity, contradiction, and missing information |
| Reprompt assistance | Help the user refine vague requests |
| Worker selection | Find suitable existing workers |
| Worker creation | Request/create new skills when capability is missing |
| Task planning | Decide how the work should be executed |
| Model routing | Decide local vs cloud model / API per task |
| Permission management | Decide when user approval is required |
| Global memory | Remember long-term information |
| Knowledge library | Access WorkDesk and project knowledge |
| Project supervision | Monitor PMs and major decisions |
| Final authority | MB sits above PM and Workers |

### Project Manager (PM)

A persistent project employee, not a disposable agent. The PM is assigned when a project is created and remains attached for its whole lifetime, becoming the project's institutional memory:

- Project knowledge · Project decisions · Previous tasks · Worker performance · Failures · Successful workflows · Lessons learned · Project conventions
- It never automatically reads unrelated project memories.

### Workers

Persistent AI employees. A Worker is essentially: **Identity + Personality + Skillset + Tools + Permissions + Memory rules + Experience + Performance**.

- **Skills**: Primary skills, secondary skills, expertise
- **Tools**: Browser, terminal, filesystem, code studio, office suite, media, etc.
- **Permissions**: Allowed applications, allowed folders, read/write/delete rights, approval requirements
- **Memory**: Group memory, authorized project memory, worker experience
- **Statistics**: Times triggered, tasks completed, QA pass rate, failure rate, average execution time
- **Status**: Available · Working · Waiting · Needs MB · Needs User · Offline

### Worker Creation System

Five paths into the worker registry:

1. GitHub skill repository (recursive sub-folder scan)
2. Skill Creator Worker (a meta-worker that designs other workers)
3. User manually creates
4. PM requests a new worker
5. **Capability gap detection**: Main Brain discovers "no existing worker can properly perform this task", checks whether an existing worker can be upgraded, then upgrades or creates.

---

## 🛡️ Dual QA Systems

### QA-1: Requirement QA (before work begins)

Verifies that MB understood the user:

- Is anything ambiguous? · Are there contradictions? · Are the requirements complete enough? · Is the requested output clearly defined? · Is the task feasible?

Example: user says "Make a presentation about my project." MB understands the topic, but slide count and language are unknown. QA-1 FAILS with a clarification request, and MB asks the user.

### QA-2: Output QA (after execution)

Verifies: Accuracy · Truthfulness · Correctness · Completeness · Requirement compliance · Output preferences · Formatting · Logic · Technical functionality · Source validity.

```
QA
 │
 ▼
Failure Report
 │
 ▼
PM identifies responsible worker
 │
 ▼
Redo only the failed portion
 │
 ▼
QA again
```

This prevents the whole project from being restarted unnecessarily.

---

## 🧠 Memory Architecture

```
                         MEMORY
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    Global Memory       Project Memory       Worker Memory
         │                   │                   └── Identity
         │                   │                       Experience
         │                   │                       Performance
         │                   └── PM / project knowledge
         └── User preferences
             WorkDesk settings
             Global knowledge
             Long-term decisions
```

**Group Memory** exists underneath a project/task group for short-term collaboration.

| Actor | Access |
| :--- | :--- |
| Main Brain | Global + authorized project/group information |
| PM | Own project + current group |
| Worker | Current group + own profile/experience |
| Cross-project | NEVER automatic; Main Brain grants permission |

---

## 📚 Learning System

Workers and PMs improve from history - but there is no uncontrolled self-rewriting.

```
Task → Result → QA → Experience → Lesson Candidate → Evidence / Confidence → Stored Lesson
```

Example: Excel worker produced incorrect formulas. QA confirmed. Lesson candidate: "Formula validation should happen after formatting." Evidence: 3 similar cases. Confidence: High. The AI learns from evidence, not from trusting its own previous conclusions.

---

## 🗂️ Task Groups

A Task Group is a temporary working team: PM + Workers + shared requirements + shared files + shared artifacts + group memory + communication + task state.

- Workers communicate directly within the group.
- Important decisions escalate: **Worker → PM → MB → User**.
- A worker waiting for the user does not freeze the group. The task engine supports **asynchronous execution**.

---

## 🔧 Tools & Permissions

### Tool Ecosystem

| Now | Later |
| :--- | :--- |
| Filesystem, Terminal, Web Search, Code Studio, Office Suite (PDF), Media, Vault, Remote Device | Email, Discord, Slack, GitHub, Databases, Design tools, other Windows applications |

### 4-Level Permission System

| Level | Behavior |
| :--- | :--- |
| Automatic | Safe routine actions |
| Notify | Execute, then tell the user |
| Ask | User must approve |
| Explicit | High-impact action requires direct confirmation |

Examples: Read a project file → Automatic. Create a new project file → Automatic / Notify. Modify important project configuration → Ask. Install software / delete important files / external actions → Explicit approval.

---

## 🔀 Model Routing & SBR

```
                 Main Brain
                      │
                 Model Router
         ┌────────────┼────────────┐
         ▼            ▼            ▼
      Local AI     Cloud AI     Other API
```

The router considers: task complexity, privacy, cost, speed, context size, model capability, tool requirements, and user preference. **Skill-Based Routing (SBR)** means the whole system routes each request through the right skill → right worker → right model, while the worker definition itself stays model-agnostic.

Example: private file analysis → Local. Complex reasoning → Cloud. Simple classification → Local. Specialized API task → Selected API.

---

## 👁️ Visualization

Two views make the AI's work visible:

1. **Work Graph** - MB → PM → Workers → QA → DONE flow per task.
2. **Virtual Office / Office Workflow View** - a digital workplace with worker states: Idle · Working · Thinking/Planning · Waiting · Talking to another Worker · Asking PM · Waiting for User · Completed · Error.

Both live **inside every chat session**, not as separate pages - because each chat has its own workers and flow.

---

## 🛡️ Reliability: The Four Safety Systems

1. **Audit Log** - who decided, which worker acted, which tool was used, what files changed, why MB decided, what QA rejected, what rework changed. Decision/event metadata, not hidden chain-of-thought.
2. **Checkpointing** - before major actions: current state → checkpoint → worker action → rollback if damaged.
3. **Cancellation** - the user can always say "Stop": MB stops the group, cancels workers, safely terminates active tools, preserves current state. A powerful autonomous AI without a good emergency brake is a recipe for disaster.
4. **Resume** - task state, checkpoints, memory, and artifacts are persistent, surviving application restart, computer restart, API failure, worker failure, and network failure.

---

## 🖥️ Current Build: EMILIA LAB Studio

EMILIA LAB is the current user-facing identity of AI WorkDesk OS: a calm personal AI studio on Windows, served from `http://localhost:3787`.

### Design System

- **Palette**: Graphite canvas, raised charcoal surfaces, single pale cool-blue accent (`#5B8DEF`), high-contrast off-white text
- **Typography**: Locally available Segoe UI (familiar Windows operation); monospace reserved for code and measurements
- **Shape**: 8px controls, 12px large panels, sparse decoration, borders define surfaces
- **Motion**: Liquid, restrained; `prefers-reduced-motion` honored (boot splash degrades to Tier-3 fades only)
- **Identity**: EMILIA LAB wordmark, Emilia character portrait in nav footer and home welcome area, Main Brain boot splash animation

### Pages (sidebar)

| Group | Views |
| :--- | :--- |
| HOME | Home dashboard, New chat, Projects, Tasks |
| Recent chats | Conversation history |
| Your team | Workers, Worker registry, Worker design (GitHub skill import), Project managers, Team memory (Vault) |
| Workspace | Office suite (PDF studio), Code studio, Media room, Remote device |
| Utilities | Timer · Alarm · Stopwatch, Calculator |
| System | Audit log, Settings |

### Feature Status in This Build

| Feature | Status |
| :--- | :--- |
| Main Brain agentic chat with office workflow view | ✅ |
| THIS CHAT SESSION panel (TASKS / OFFICE / APPROVALS / RESULT / PROJECT), resizable | ✅ |
| QA-1 / QA-2 gates with selective rework | ✅ |
| Worker registry + GitHub skill worker design (recursive folder scan) | ✅ |
| Persistent PMs with project memory | ✅ |
| Vault notes (personal + Main Brain auto memory, `[[wikilinks]]`, MB chat box) | ✅ |
| Office suite: PDF viewer, in-page text editing, Save Edits, Export PDF, fullscreen | ✅ |
| Code studio (editor + file tree + run) | ✅ |
| Media room: preview stage + transport controls, lightbox, size badges, subtitles | ✅ |
| Remote device: local info, registration, pairing token, device list, session commands | ✅ |
| Timer / Alarm / Stopwatch, Calculator | ✅ |
| Hybrid model router (OpenRouter, ChatAnywhere, local endpoint) | ✅ |
| Audit log, checkpoints, cancellation, resume | ✅ |
| Boot splash animation (skippable, reduced-motion aware) | ✅ |
| Emilia desktop companion (state machine, bongo typing, loopback vision) | ✅ |
| Local filesystem browsing inside chat (C: / D: / project folders) | ✅ |

### Tech Stack

- **Backend**: Python 3.11+ · FastAPI · Uvicorn · WebSockets · SQLite (WAL)
- **Frontend**: Vanilla HTML / CSS / JS (no framework), SVG icon system, ECharts-free deterministic components
- **Vendors**: pdf.js + pdf-lib (PDF render/edit), html2canvas
- **Models**: OpenRouter (cloud experts) · ChatAnywhere (free relay) · Ollama / LM Studio (local, privacy-first)

---

## ⚡ Quick Start in 30 Seconds

### Prerequisites

- **Python 3.11+**
- **Git**
- *(Optional)* [Ollama](https://ollama.com/) or [LM Studio](https://lmstudio.ai/) for offline inference
- *(Optional)* Node.js 18+ for running frontend tests

### 1. Clone the Repository

```bash
git clone https://github.com/lingjw02/ai-workdesk-local.git
cd ai-workdesk-local
```

### 2. Set Up Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` to enable your desired providers:

```env
# Cloud expert models via OpenRouter (Optional)
OPENROUTER_API_KEY=sk-or-v1-...

# Local privacy model via Ollama / LM Studio (Optional)
LOCAL_ENDPOINT=http://localhost:11434/v1
LOCAL_MODEL=qwen2.5:7b

# Free relay via ChatAnywhere (Optional)
CHATANYWHERE_API_KEY=sk-...

# Web Search API (Optional - defaults to keyless Bing search if left empty)
BRAVE_API_KEY=
```

### 4. Launch the Server

**Option A - Windows Double-Click Launcher (Fastest):**
Double-click [`start_workdesk.bat`](./start_workdesk.bat) in the project root.

**Option B - Terminal:**

```bash
python main.py
# or with npm
npm start
```

Open your browser at:

```
http://localhost:3787
```

---

## 🏗️ Implementation Architecture

```
WINDOWS DESKTOP
        │
        ▼
┌─────────────────────────────┐
│         UI LAYER            │  Vanilla HTML/CSS/JS, SVG icons, studio shell
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│       ORCHESTRATION         │  Main Brain · Task Manager · PM Manager
│                             │  Worker Manager · QA Manager · Permission Manager
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│       AGENT RUNTIME         │  PMs · Workers · Skills (SBR)
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│       MEMORY / DATA         │  Global · Project · Group · Experience
│                             │  Knowledge Library · Audit Logs · SQLite (WAL)
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│          TOOLS              │  Filesystem · Terminal · Browser · Code Studio
│                             │  PDF Suite · Media · Remote Device
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│        MODEL ROUTER         │  Local Models · Cloud APIs · User API Keys
└─────────────────────────────┘
```

### Task Lifecycle & Dual QA Execution Flow

```
User Submits Request
   │
   ▼
[Main Brain Intent Classifier] ──(General Chat/Question)──► [Direct Answer, No Task Created]
   │ (Actionable Task)
   ▼
[QA-1 Requirement Intake Gate]
   ├─► Ambiguous / Conflicting / Missing Inputs ──► Clarify with User
   ├─► Missing Capability in Worker Pool ─────────► Worker Creator (GitHub skill)
   └─► Verified & Complete (QA-1 PASS)
         │
         ▼
   [PM Plans Task Group (Decomposition & Team Selection)]
         │
         ▼
   [Model Router + SBR] ──► Sensitive → Local · Deep reasoning → Cloud
         │
         ▼
   [Autonomous Workers Execute (async, parallel)]
         │
         ▼
   [QA-2 Output Verification Gate]
         ├─► FAIL ──► FailureReport ──► Selective Rework (only failed node)
         └─► PASS ──► Deliver Output ──► Promote evidence-gated lessons
```

---

## 🧪 Testing & Quality Assurance

### Run Python Unit Tests

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```

Covers core state machines, progressive feature suites, hybrid router fallbacks, vault APIs, and loopback companion vision safety.

### Run Frontend & Companion Tests (Node.js)

```bash
node --test tests/pet-state.test.cjs tests/pet-awareness.test.cjs tests/dashboard.test.cjs
```

### Run End-to-End Pipeline Test

With the server running (`python main.py`), execute in another terminal:

```powershell
python test_pipeline.py
```

Validates workspace creation, intent parsing, subtask dispatch, worker output, and QA-2 audit scoring.

---

## 🛡️ Privacy & Security Invariants

1. **Local-First Data Storage**: All conversations, task states, artifacts, vault notes, and audits are stored locally in `data/workdesk.db`. No telemetry leaves your machine.
2. **Secrets Protection**: Credentials live strictly in `.env` (Git-ignored). `.env.example` provides sanitized templates without active keys.
3. **Sandbox Safeguards**: Filesystem operations are path-bounded to the workspace; the terminal tool enforces an immutable safety blacklist against dangerous commands.
4. **Companion Vision Isolation**: Visual frames stay in memory only, reject non-loopback origins, mask password fields, and are never written to disk.
5. **Permission Gates**: Every worker action passes the 4-level permission system; high-impact actions always require explicit user confirmation.

---

## 🗺️ Roadmap

The build follows a phased plan: specification → core engine → Main Brain → worker ecosystem → PM lifetime → tool control → QA/rework → Windows UI → model router → learning system → AI OS expansion.

- [x] **Phase 0**: System specification (protocols: MB / PM / Worker / QA / Task / Memory / Permission / Tool; lifecycles; error handling)
- [x] **Phase 1**: Core engine (task engine, worker registry, PM registry, agent runtime, message bus, state machine, memory manager)
- [x] **Phase 2**: Main Brain (requirement understanding, QA-1, clarification, worker selection, task classification, task groups, permissions, global memory)
- [x] **Phase 3**: Worker ecosystem (research, coding, data, document, file, QA workers; registry, profiles, installation, statistics)
- [x] **Phase 4**: PM lifetime system (persistent PM identity, project memory, group memory, history, worker performance, lessons)
- [x] **Phase 5**: Tool control (filesystem, terminal, browser, code studio, office suite, media)
- [x] **Phase 6**: QA/rework engine (QA-1, QA-2, structured failure reports, selective rework, retry limits, escalation)
- [x] **Phase 7**: EMILIA LAB Windows WorkDesk UI (chat, projects, task groups, workers, PMs, vault, permissions, audit, settings; work graph; office workflow view; boot splash)
- [x] **Phase 8**: Model router (local models, cloud APIs, multiple providers, task-based routing, privacy routing, fallbacks)
- [x] **Phase 9**: Learning system (evidence-gated lessons; PM / worker / MB learning with strict memory boundaries)
- [ ] **Phase 10 (Planned)**: AI OS expansion - Windows application control, email/calendar, GitHub, databases, automation, scheduled work, background agents, notifications, long-running projects, LAN distributed workers, Tauri desktop wrapper, local speech interaction

---

## ❓ FAQ

<details>
<summary><b>Can I use AI WorkDesk OS without paid API keys?</b></summary>
<br/>
<b>Yes, absolutely!</b>
Install and start Ollama, configure <code>LOCAL_ENDPOINT=http://localhost:11434/v1</code> and <code>LOCAL_MODEL=qwen2.5:7b</code> in your <code>.env</code>, and all orchestration and chat run completely offline. You can also use the free ChatAnywhere relay.
</details>

<details>
<summary><b>How do the QA-1 and QA-2 gates save tokens?</b></summary>
<br/>
Traditional agents jump straight into generation on vague prompts, wasting tokens on flawed outputs.<br/>
- <b>QA-1</b> is the intake gate: it checks for contradictions or missing inputs and prompts for clarification before dispatching workers.<br/>
- <b>QA-2</b> verifies the final output. If one component fails, the engine re-executes only the failed worker, not the whole project.
</details>

<details>
<summary><b>Does the desktop companion monitor other applications?</b></summary>
<br/>
<b>No.</b>
Visual awareness is disabled by default and must be explicitly enabled. When active, it captures only the visible content inside the EMILIA LAB window, redacts password fields, and communicates strictly with your local <code>127.0.0.1</code> model.
</details>

<details>
<summary><b>How do I turn a GitHub repository skill into an active worker?</b></summary>
<br/>
Open <b>Workers → Design New Worker</b>. Paste any GitHub repository URL. The system recursively scans its sub-folders for <code>SKILL.md</code>, parses frontmatter and capabilities, and auto-designs a worker. You can install it as a new worker or merge it into an existing one. No manual naming required.
</details>

<details>
<summary><b>Why is the chat not a single box anymore?</b></summary>
<br/>
Because each conversation has its own workers, flow, approvals, and artifacts. The chat area therefore carries the <b>Office Workflow View</b>, and the resizable <b>THIS CHAT SESSION</b> panel shows TASKS / OFFICE / APPROVALS / RESULT / PROJECT for that session only. The Main Brain replies like a normal AI agent - narrating what it thinks and what it is doing - not just reporting status.
</details>

---

## 🤝 Contributing

Contributions, issues, and feature requests are warmly welcomed!

- Found a bug or have a feature suggestion? Please open an [Issue](https://github.com/lingjw02/ai-workdesk-local/issues).
- Want to share an agent skill? Share your `SKILL.md` configurations with the community.

---

## 📄 License

This project is licensed under the [MIT License](./LICENSE).
<br/>
Copyright (c) 2026 AI WorkDesk Authors.
