<div align="center">

# AI WorkDesk OS / EMILIA LAB

### A local-first, multi-agent personal AI operating system & desktop workbench for Windows.

Local First · USER > Main Brain > PM > Worker Hierarchy · Dual QA Gates (QA-1/2) with Selective Rework · Privacy-First Hybrid Model Router · Visual Office Floor · Bidirectional Markdown Vault · Interactive Companion

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Uvicorn-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/Database-SQLite%20(WAL)-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![WebSockets](https://img.shields.io/badge/Streaming-WebSockets-orange?style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Privacy First](https://img.shields.io/badge/Privacy-100%25%20Local--First-success?style=flat-square)](#️-privacy--security-invariants)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](./LICENSE)

🌐 [中文](./README.md) · **English**　|　[📥 Quick Start](#-quick-start-in-30-seconds) · [✨ Highlights](#-highlights) · [🎯 Who Is It For](#-who-is-it-for) · [🏗️ Architecture](#️-system-architecture--workflow) · [🆚 Comparison](#-comparison-with-traditional-solutions) · [❓ FAQ](#-faq)

</div>

---

## 💡 Why AI WorkDesk OS?

Most AI tools today are still constrained to a single chat box:
- A linear prompt prompt-response waterfall where hallucinations force you to re-prompt everything from scratch;
- Multi-agent frameworks remain confined to command-line terminals or abstract Python scripts lacking interactive visual workspaces;
- Sensitive data is sent unconditionally to cloud APIs without local privacy gating or intelligent tier-based routing.

**AI WorkDesk OS** reimagines human-AI collaboration from the perspective of an operating system:
It is an interactive desktop workbench equipped with a **visual Office Floor**, an **Obsidian-style Knowledge Vault**, and a full autonomous workflow loop: **Requirement Analysis (QA-1) ➔ Team Delegation (PM) ➔ Execution (Workers) ➔ Validation (QA-2) ➔ Selective Rework**.

---

## ✨ Highlights

- 🏢 **Hierarchical Multi-Agent Authority**: Enforces a strict chain of command: `USER > Main Brain > Lifetime PM > Autonomous Workers`. The Main Brain governs requirement intent, PMs accumulate persistent institutional memory and worker metrics, and specialized workers execute domain tasks.
- 🛡️ **Dual QA Verification Gates**:
  - **QA-1 (Pre-Execution Gate)**: Validates requirement clarity, detects contradictions, ambiguous quantities, and capability gaps before wasting any tokens.
  - **QA-2 (Post-Execution Gate)**: Audits all deliverables against requirements. On failure, it generates a structured `FailureReport` and triggers **selective rework**—re-executing only the failed worker and its downstream dependencies.
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

**Windows Double-Click Launcher:**
Double-click [`start_workdesk.bat`](./start_workdesk.bat) in the project root.

**Terminal:**
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

## 🧪 Testing & Verification

The project includes an automated test suite across Python and Node.js test runners:

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

---

## 📄 License

This project is licensed under the [MIT License](./LICENSE).
<br/>
Copyright (c) 2026 AI WorkDesk Authors.
