<div align="center">

# AI WorkDesk OS / EMILIA LAB

### Up and running in 30 seconds: Bring multi-agent collaboration, dual QA verification gates, and a personal AI super-workbench directly to your Windows desktop.

Local First · USER > Main Brain > PM > Worker Hierarchy · QA-1 Pre-Check + QA-2 Post-Audit with Selective Rework · Privacy-First Hybrid Model Routing · Visual Office Floor · Bidirectional Markdown Vault · Interactive Desktop Companion

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Uvicorn-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/Database-SQLite%20(WAL)-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![WebSockets](https://img.shields.io/badge/Streaming-WebSockets-orange?style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Privacy First](https://img.shields.io/badge/Privacy-100%25%20Local--First-success?style=flat-square)](#️-privacy--security-invariants)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](./LICENSE)

🌐 **English** · [中文](./README.zh.md)　|　[📥 30s Quick Start](#-quick-start-in-30-seconds) · [✨ Highlights](#-highlights) · [🎯 Who Is It For](#-who-is-it-for) · [🏗️ Architecture](#️-system-architecture--workflow) · [🆚 Comparison](#-comparison-with-traditional-solutions) · [❓ FAQ](#-faq)

</div>

---

## 💡 Why AI WorkDesk OS?

Most AI tools today are still constrained to a single chat box:
- A linear prompt-response waterfall where hallucinations force you to re-prompt everything from scratch;
- Multi-agent frameworks remain confined to command-line terminals or abstract Python scripts lacking interactive visual workspaces;
- Sensitive data is sent unconditionally to cloud APIs without local privacy gating or intelligent tier-based routing.

**AI WorkDesk OS** reimagines human-AI collaboration from the perspective of an operating system:
It is an interactive desktop workbench equipped with a **visual Office Floor**, an **Obsidian-style Knowledge Vault**, and a full autonomous workflow loop: **Requirement Analysis (QA-1) ➔ Team Delegation (PM) ➔ Execution (Workers) ➔ Validation (QA-2) ➔ Selective Rework**.

---

## ✨ Highlights

- 🏢 **Hierarchical Multi-Agent Authority**: Enforces a strict chain of command: `USER > Main Brain (MB) > Lifetime Project Manager (PM) > Autonomous Workers`. The Main Brain governs requirement intent, PMs accumulate persistent institutional memory and worker metrics, and specialized workers execute domain tasks.
- 🛡️ **Dual QA Verification Gates**:
  - **QA-1 (Pre-Execution Gate)**: Validates requirement clarity, detects contradictions, ambiguous quantities, and capability gaps before wasting any tokens.
  - **QA-2 (Post-Execution Gate)**: Audits all deliverables against requirements with objective scoring. On failure, it generates a structured `FailureReport` and triggers **selective rework**—re-executing only the failed worker and its downstream dependencies.
- 📮 **Munder-Difflin Style Office Floor & Mailboxes (Hive)**:
  - Top-down visual floor plan displaying real-time agent desks and statuses (`idle`, `thinking`, `working`, `waiting`, `blocked`, `success`).
  - FIPA-lite speech-act mailboxes (`request`, `inform`, `propose`, `agree`, `refuse`) with real-time desk-to-desk message envelopes and an 8-hop livelock guard.
- 🔀 **Privacy-First Hybrid Model Router**:
  - **Local First**: Sensitive tasks route to local OpenAI-compatible endpoints (e.g. Ollama, LM Studio), keeping private code and data 100% on your machine.
  - **Complexity-Based Split**: Simple queries use instant lightweight models; deep reasoning routes to expert cloud models (Claude 3.5 Sonnet, GPT-4o).
  - **Fault-Tolerant Fallback Chains**: Automatic fallback progression with persistent audit logging in SQLite.
- 🧠 **One-Click Worker Creation from GitHub Skills**: Paste any GitHub repository URL containing a `SKILL.md` file; the wizard parses frontmatter, capabilities, and behavioral rules to auto-spawn or upgrade workers.
- 📝 **Dual-Section Obsidian-Style Vault & Office Suite**:
  - Full Markdown support with `[[wiki links]]`, live preview, and full-text search.
  - Integrates an Office Suite (Documents, Sheets with formula calculation, Slides, PDF viewer) and a sandboxed Python Code Studio.
- 🌸 **Emilia Desktop Companion**:
  - A lightweight, floating character companion with state machines for roaming, idle poses, tea time, and sleep.
  - **Bongo Typing Reaction**: Synchronously mirrors real workspace typing with animated paw taps.
  - **Strictly Loopback Local Vision**: Communicates exclusively with local `127.0.0.1` vision models (e.g. Ollama LLaVA/MiniCPM). Screen captures stay in memory and automatically redact password fields.

---

## 🎯 Who Is It For

| Persona | Core Pain Point | How AI WorkDesk OS Solves It |
| :--- | :--- | :--- |
| **Indie Hackers & Creators** | Juggling architecture, coding, research, and documentation simultaneously | Main Brain breaks down goals; PM directs specialized workers; dual QA ensures quality |
| **Privacy-Conscious Developers** | Proprietary code and sensitive data cannot be sent to commercial cloud APIs | Sensitive tasks are forced through local Ollama/LM Studio endpoints; data resides in local SQLite |
| **AI Agent Researchers** | Terminal-based multi-agent execution is opaque and difficult to debug | Visual desk map, mailbox message flows, state machines, and structured QA scorecards |
| **Power Productivity Users** | Constantly switching between Obsidian, Excel, VS Code, and browser chats | Unified desktop experience combining notes, spreadsheets, documents, sandboxed execution, and an AI companion |

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

# Web Search API (Optional — defaults to keyless Bing search if left empty)
BRAVE_API_KEY=
```

### 4. Launch the Server

**Option A — Windows Double-Click Launcher (Fastest):**
Double-click [`start_workdesk.bat`](./start_workdesk.bat) in the project root.

**Option B — Terminal:**
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

## 🏗️ System Architecture & Workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│                              USER (Browser UI)                         │
│   • Dashboard      • Chat & Office Floor  • Worker Studios             │
│   • Knowledge Vault• Office Suite         • Code Studio & Utilities    │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ HTTP REST / WebSocket Streaming
┌────────────────────────────────────▼───────────────────────────────────┐
│                      FastAPI Server & Bridge (main.py / bridge.py)     │
├────────────────────────────────────────────────────────────────────────┤
│                       Main Brain Intelligence Layer                    │
│   • Intent Classification  • Requirement Spec  • QA-1 Analysis        │
├────────────────────────────────────────────────────────────────────────┤
│                        Lifetime Project Managers                       │
│   • Task Group Decomp.     • Institutional Memory• Evidence-Gated Lessons│
├────────────────────────────────────────────────────────────────────────┤
│                         Autonomous Worker Pool                         │
│   • Coder       • Researcher   • Documenter   • Data Analyst           │
│   • QA Worker   • File Manager • Worker Creator (Skill Auto-Install)   │
├────────────────────────────────────────────────────────────────────────┤
│                        Tool & Sandbox Control                          │
│   • Filesystem (Path-Bounded)  • Terminal Sandbox (Safety Blacklist)  │
│   • Web Search (Brave API / Keyless Bing fallback)                    │
├────────────────────────────────────────────────────────────────────────┤
│                          Hybrid Model Router                           │
│   • Privacy Gate (Local First) • Fallback Chains • Provider Adapters  │
├────────────────────────────────────────────────────────────────────────┤
│                      Local SQLite Database (WAL Mode)                  │
│   • Tasks & Transitions • Checkpoints • Memory • Approvals • Audit Log │
└────────────────────────────────────────────────────────────────────────┘
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
   ├─► Ambiguous / Conflicting / Missing Inputs ──► Raise ClarificationNeeded (Prompt User)
   ├─► Missing Capability in Worker Pool ─────────► Invoke Worker Creator from GitHub Skill
   └─► Verified & Complete (QA-1 PASS)
         │
         ▼
   [PM Plans Task Group (Task Decomp. & Team Selection)]
         │
         ▼
   [Hybrid Model Router] ──► Sensitive tasks pinned to Local, Deep tasks sent to Cloud
         │
         ▼
   [Autonomous Workers Execute in Parallel]
         │
         ▼
   [QA-2 Output Verification Gate]
         ├─► Verification Failed ──► Produce FailureReport ──► Selective Rework (Only Failed Node)
         └─► Verification Passed (QA-2 PASS) ──► Deliver Output ──► Promote High-Confidence Lessons
```

---

## 🆚 Comparison with Traditional Solutions

| Feature | Standard Web Chatbots | CLI Agent Frameworks | AI WorkDesk OS / EMILIA LAB |
| :--- | :--- | :--- | :--- |
| **Interface** | Linear text feed | Terminal command line | Complete workbench: Office floor, dual-link vault, office suite, and code studio |
| **Multi-Agent Coordination** | Single context prompt role-play | Rigid code loops prone to infinite recursion | Independent agent mailboxes (FIPA-lite), 8-hop anti-livelock, persistent PM records |
| **Quality Control** | None (hallucinations passed directly) | Brute-force retry of full prompt | **QA-1 Pre-check + QA-2 Output validation** with targeted dependency rework |
| **Model Routing** | Single provider lock-in | Hardcoded environment keys | **Privacy-first hybrid router**: local for sensitive tasks, cloud for deep reasoning |
| **Memory & Learning** | Stateless or raw chat truncation | Simple vector store lookups | 4-layer memory isolation with evidence-gated learning loops |
| **Data Privacy** | Hosted on external servers | Depends on configuration | **100% Local-first** SQLite WAL storage with zero telemetry |

---

## 🧩 Core Feature Deep Dive

### 1. Visual Office Floor & Mailbox System (Hive)
- **Interactive Desk Layout**: Real-time overview of the Main Brain, PM, and active workers with synchronized status indicators.
- **Message Envelopes**: Inter-desk communication animates physical envelope deliveries across workers in real time.
- **Project Blackboard**: PMs maintain a shared markdown board for instant contextual alignment among all agents.

### 2. Dedicated Worker Studios
- Tailored workspaces designed for specific responsibilities:
  - **Coder Studio**: File browser, code editor, and sandboxed execution logs.
  - **Researcher Studio**: Embedded web browser monitor, query history, and research note generator.
  - **Office Studio**: Centralized review for document drafts, spreadsheets, and slide decks.

### 3. Dual-Section Knowledge Vault
- **My Vault**: Personal markdown notebook supporting `[[wiki links]]` and live full-text search.
- **Main Brain Living Memory**: Four core documents maintained automatically by the engine:
  - `global-memory.md`: Long-term user preferences and constraints.
  - `lessons.md`: High-confidence operational lessons promoted through corroboration.
  - `todo.md`: In-flight tasks and pending human-in-the-loop approvals.
  - `pm-knowledge.md`: Per-project conventions, architectural decisions, and deliverables.

### 4. Emilia Desktop Companion
- A transparent, floating desktop companion that stays across application views with idle, magic, and tea states.
- **Bongo Mode**: Re-renders typing paws in real time based on active keystrokes inside the application.
- **Privacy-Safe Local Vision**: Captures on-screen application context at 10s intervals and sends it exclusively to a local loopback model (`127.0.0.1`), masking passwords and sensitive fields.

---

## 🧪 Testing & Quality Assurance

The codebase includes comprehensive automated test suites across Python and Node.js runners:

### Run Python Unit Tests (75 tests passing)
```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```
Covers core state machines, progressive feature suites (Phases 2-14), hybrid router fallbacks, vault APIs, and loopback companion vision safety.

### Run Frontend & Companion Tests (Node.js)
```bash
node --test tests/pet-state.test.cjs tests/pet-awareness.test.cjs tests/dashboard.test.cjs
```
Validates dashboard KPI formulas, pet state transitions, Bongo input handling, and screenshot redaction debounce rules.

### Run End-to-End Pipeline Test
With the server running (`python main.py`), execute in another terminal:
```powershell
python test_pipeline.py
```
Validates workspace creation, intent parsing, subtask dispatch, worker output, and QA-2 audit scoring.

---

## 🛡️ Privacy & Security Invariants

1. **Local-First Data Storage**: All conversations, task states, artifacts, vault notes, and audits are stored locally in `data/workdesk.db`. No telemetry data leaves your machine.
2. **Secrets Protection**: Credentials reside strictly in `.env` (ignored by Git). `.env.example` provides sanitized templates without active keys.
3. **Sandbox Safeguards**:
   - Filesystem operations are strictly confined within the workspace directory; path traversal (`../`) is blocked.
   - The terminal execution tool enforces an immutable safety blacklist against dangerous commands (`rm -rf`, `format`, `del /s`, `shutdown`, etc.).
4. **Companion Vision Isolation**:
   - Visual observation frames are held only in temporary memory for inference and are never written to disk.
   - Rejects non-loopback origins; accepts only `127.0.0.1` and `localhost`. Password and sensitive input elements are masked before capture.

---

## 🗺️ Roadmap

- [x] **v0.1 - v0.8**: State machine, multi-worker pool, lifetime PM, tool permission matrix, dual QA gates, and hybrid model router
- [x] **v0.9 - v0.10**: Evidence-gated learning system, personal desktop utilities, and Office Suite
- [x] **v0.11 - v0.12**: Obsidian-style dual-vault, GitHub Skill-to-Worker generation, and full KPI dashboard
- [x] **v0.13 - v0.14**: Munder-Difflin visual office floor, speech-act mailboxes, and dynamic priority scheduling
- [x] **v0.18 - v0.19**: Emilia desktop companion, live Bongo reaction, loopback-only local vision, and Liquid UI theme
- [ ] **v0.20+ (Planned)**:
  - [ ] Local speech interaction and emotional synthesis (TTS / STT)
  - [ ] Lightweight native desktop wrapper via Tauri (Windows / macOS)
  - [ ] Multi-machine LAN distributed worker networking

---

## ❓ FAQ

<details>
<summary><b>Can I use AI WorkDesk OS without paid API keys?</b></summary>
<br/>
<b>Yes, absolutely!</b>
AI WorkDesk natively supports local models. Install and start Ollama, configure <code>LOCAL_ENDPOINT=http://localhost:11434/v1</code> and <code>LOCAL_MODEL=qwen2.5:7b</code> in your <code>.env</code>, and all orchestration and chat will run completely offline and free of charge. You can also use the free ChatAnywhere relay.
</details>

<details>
<summary><b>How do the QA-1 and QA-2 gates save tokens?</b></summary>
<br/>
Traditional agents jump straight into generating code or reports upon receiving vague prompts, wasting tokens on flawed outputs.<br/>
- <b>QA-1</b> acts as an intake gate: it checks for contradictions or missing inputs and prompts you for clarification before dispatching workers.<br/>
- <b>QA-2</b> verifies the final output. If one component fails, the engine analyzes dependencies and <b>re-executes only the failed worker</b>, saving time and tokens.
</details>

<details>
<summary><b>Does the desktop companion monitor other applications?</b></summary>
<br/>
<b>No.</b>
Visual awareness is disabled by default and must be explicitly enabled. When active, it captures only the visible content within the AI WorkDesk application window, automatically redacts password fields, and communicates strictly with your local <code>127.0.0.1</code> model.
</details>

<details>
<summary><b>How do I turn a GitHub repository skill into an active worker?</b></summary>
<br/>
Navigate to the <b>Workers</b> tab in the sidebar and click <b>Design New Worker</b>. Paste any GitHub repository URL containing a <code>SKILL.md</code> file. The system automatically inspects the skill, parses its frontmatter and permissions, and lets you install it as a brand-new worker or merge its capabilities into an existing one with one click.
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
