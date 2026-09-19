# AI WorkDesk OS / EMILIA LAB

<p align="center">
  <strong>A Local-First Personal AI Operating System & Multi-Agent Desktop Workbench</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Backend-FastAPI%20%7C%20Uvicorn-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Database-SQLite%20(WAL)-003B57.svg" alt="SQLite">
  <img src="https://img.shields.io/badge/Protocol-WebSockets%20%2B%20REST-orange.svg" alt="WebSockets">
  <img src="https://img.shields.io/badge/Privacy-Local--First-success.svg" alt="Privacy Local First">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## Overview

**AI WorkDesk OS** (featuring **EMILIA LAB**) is a local-first, desktop-grade AI workbench that orchestrates multi-agent teams to accomplish complex personal and software tasks. Unlike superficial chatbot wrappers, AI WorkDesk implements a complete multi-tier agent operating system:

1. **Hierarchical Authority Ladder**: `USER > Main Brain (MB) > Project Manager (PM) > Autonomous Workers`.
2. **Dual QA Verification Gates**:
   - **QA-1 (Pre-execution Gate)**: Validates requirement completeness, detects ambiguities and contradictions, and verifies worker capability coverage before any work begins.
   - **QA-2 (Post-execution Gate)**: Audits deliverables against requirements with objective scoring and triggers **selective rework** (redoing only failed components and downstream consumers, rather than the entire pipeline).
3. **Munder-Difflin Inspired Hive Layer & Office Floor**: Real-time visual office floor with desk avatars, speech-act mailbox messaging (`request`, `inform`, `propose`, `agree`, `refuse`), anti-livelock hop limits, and shared blackboards.
4. **Hybrid Model Router**: Privacy-first routing policy that keeps sensitive tasks on local loopback models (e.g. Ollama, LM Studio), while routing complex reasoning to cloud expert models (OpenRouter, Claude 3.5 Sonnet, GPT-4o) or free relays (ChatAnywhere), backed by automated fallback chains and audit logging.
5. **Obsidian-Style Knowledge Vault & Working Area**: Built-in markdown vault supporting `[[wiki links]]`, live preview, full-text search, and auto-syncing memory notes, alongside an integrated Office Suite (Documents, Sheets, Slides, PDF) and sandboxed Code Studio.
6. **Emilia Desktop Companion**: An interactive, floating character companion with mood states, Bongo typing reaction (reacts live to user input inside the app), customizable wardrobe atlas, and loopback-only local visual workspace awareness.

---

## Architecture & Core Subsystems

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

### 1. Main Brain (MB) & Dual QA Gates
- **Requirement Analysis**: Transforms loose natural language into a structured `RequirementSpec` (goal, constraints, output format, risk level, privacy sensitivity, and decomposition).
- **QA-1 Pre-Execution Gate**: Checks for missing information, ambiguous quantities, conflicting instructions, and capability gaps. If a gap is detected, MB can trigger the **Worker Creator** to auto-design and install a new worker from a GitHub `SKILL.md` before execution.
- **QA-2 Post-Execution Gate**: Evaluates all produced artifacts. If flaws are found, a structured `FailureReport` is generated, and a selective rework cycle re-executes only the responsible worker and its consumers.
- **Evidence-Gated Learning**: Lessons learned from rework or failures are promoted from `LOW` to `HIGH` confidence only after multiple corroborating tasks. Once stored, they automatically inject guidance into future runs.

### 2. Hive Office Floor & Worker Studios
- **Visual Office Floor**: Visualizes agents seated at their respective desks with live status indicators (`idle`, `thinking`, `working`, `waiting`, `blocked`, `success`).
- **Speech-Act Mailboxes**: Inter-agent messages are delivered via structured inbox/outbox files with explicit communicative acts and hop limits to prevent livelock loops.
- **Worker Studios**: Dedicated workspace environments tailored to each worker's role:
  - **Coder**: Live workspace file tree, code viewer, and execution output.
  - **Researcher**: Embedded browser monitor, query logs, and note generator.
  - **Documenter / Analyst**: Document draft reviews and data summaries.
- **Dynamic Worker Generator**: Point the wizard at any GitHub repository URL containing a `SKILL.md` file; the system parses frontmatter, tools, and behavior rules, allowing one-click installation or capability merging into existing workers.

### 3. Hybrid Model Router & Privacy
- **Privacy-First Routing**: Requests tagged as sensitive or requiring local isolation automatically route to your local OpenAI-compatible endpoint (`LOCAL_ENDPOINT`, e.g., Ollama or LM Studio).
- **Multi-Provider Support**: Out-of-the-box support for:
  - **Local**: Ollama, LM Studio, LocalAI (`http://localhost:11434/v1`, etc.)
  - **Cloud**: OpenRouter (`OPENROUTER_API_KEY`) with models like Claude 3.5 Sonnet and GPT-4o
  - **Free Relay**: ChatAnywhere (`CHATANYWHERE_API_KEY`)
- **Fallback Chains & Audit**: If a cloud or primary model call fails, the router traverses configured fallbacks and records every route decision and latency metric in SQLite.

### 4. Knowledge Vault & Office Suite
- **Obsidian-Style Dual Vault**:
  - `My Vault`: User notes, Markdown files, wiki-link support (`[[Note Title]]`), and full-text search.
  - `Main Brain Memory`: Living system notes (`global-memory.md`, `lessons.md`, `todo.md`, `pm-knowledge.md`) automatically kept in sync with the orchestrator.
- **Integrated Working Area**:
  - **Documents**: Rich-text WYSIWYG document editor.
  - **Sheets**: Interactive spreadsheet with live formula evaluation (`SUM`, `AVG`, cell coordinates).
  - **Slides**: Presentation slide deck editor with PDF export.
  - **PDF Viewer**: Embedded client-side PDF document reader.
  - **Media Room**: Audio/video/image gallery and viewing suite.
  - **Personal Utilities**: Stopwatch, alarms, countdown timer, and scientific calculator.

### 5. Emilia Desktop Companion
- **Transparent Desktop Pet**: Floats seamlessly across app pages with smooth roaming, idling, sleeping, and tea animations.
- **Bongo Typing Mode**: Re-renders left/right typing paws in real time based on active user keystrokes in the workspace.
- **Interactive Room & Wardrobe**: Equip interchangeable 2D atlas accessories across multiple outfits (original, casual, ice queen, kimono, maid).
- **Local-Only Vision Awareness**: Optional loopback-only visual awareness that captures active workspace frames every 10s and queries a local vision model (e.g. Ollama LLaVA/MiniCPM). Zero frames are written to disk or sent to external clouds.

---

## Quick Start

### Prerequisites
- **Python 3.11+** installed on your system.
- **Git** installed.
- *(Optional)* **Node.js 18+** for running client-side test suites or npm scripts.
- *(Optional)* A local model server (e.g. [Ollama](https://ollama.com/) or [LM Studio](https://lmstudio.ai/)) if you want 100% offline local model inference.

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/ai-workdesk-local.git
cd ai-workdesk-local
```

### 2. Set Up Virtual Environment
On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

On macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the template configuration file:
```bash
cp .env.example .env
```
Open `.env` in any text editor and fill in your desired providers:
- **Local inference**: Set `LOCAL_ENDPOINT=http://localhost:11434/v1` and `LOCAL_MODEL=qwen2.5:7b` (or your preferred local model).
- **OpenRouter (Cloud)**: Set `OPENROUTER_API_KEY=sk-or-v1-...`.
- **ChatAnywhere (Free Relay)**: Set `CHATANYWHERE_API_KEY=sk-...`.
- **Brave Search (Optional)**: Set `BRAVE_API_KEY=...` for real web search (a keyless Bing fallback is built in if left empty).

> [!NOTE]
> Never commit your `.env` file to version control. It is already added to `.gitignore`.

### 4. Launch the Application

**Option A — Windows Double-Click Launcher:**
Double-click `start_workdesk.bat` in the repository root.

**Option B — Terminal (PowerShell / Bash):**
```bash
python main.py
```

**Option C — npm script:**
```bash
npm start
```

Open your browser and navigate to:
```
http://localhost:3787
```

---

## Repository Structure

```
ai-workdesk-local/
├── agents/                     # Worker profiles, registries, and PM agent definitions
│   ├── main_brain.py           # Main Brain prompt handling and coordination
│   ├── pm.py                   # Lifetime Project Manager agent
│   ├── qa.py                   # QA evaluation agent
│   ├── registry.py             # Persistent worker pool & seed profiles
│   └── worker.py               # Worker execution container
├── core/                       # Core system configuration and data contracts
│   ├── config.py               # Paths, environment loader, and defaults
│   ├── event_bus.py            # Async pub/sub event bus
│   ├── models.py               # Pydantic data schemas
│   ├── router.py               # API routing helpers
│   └── state_machine.py        # Task lifecycle state machine definitions
├── docs/                       # Specifications and architecture docs
│   ├── COMPANION.md            # Emilia desktop companion & local vision guide
│   └── superpowers/            # Design specs and historical implementation plans
├── memory/                     # Memory management and persistent storage
│   ├── memory_manager.py       # Scoped memory lookup and permissions
│   └── store.py                # SQLite memory backing store
├── public/                     # Frontend client assets (Vanilla JS / CSS)
│   ├── assets/                 # Character sprites, backgrounds, and pet wardrobe atlas
│   ├── css/                    # Liquid theme, dashboard, studio, and pet stylesheets
│   ├── js/                     # Modular frontend logic (chat, office floor, vault, etc.)
│   ├── vendor/                 # Bundled libraries (pdf.js, html2canvas, pdf-lib)
│   └── index.html              # Single-page application entrypoint
├── src/workdesk/               # Pure headless orchestration engine
│   ├── bus.py                  # In-process message bus with dead-letter queue
│   ├── engine.py               # Facade engine coordinating tasks, state, and audit
│   ├── envelope.py             # Communication protocol message envelope
│   ├── learning.py             # Evidence-gated lesson pipeline
│   ├── model_router.py         # Task-based hybrid model routing engine
│   ├── permissions.py          # 4-layer permission matrix and access gates
│   ├── runtime.py              # Task group orchestration and QA execution loop
│   ├── tools.py                # Filesystem, terminal sandbox, and web tool execution
│   └── worker_creator.py       # Capability gap detection and worker synthesis
├── tests/                      # Automated test suites
│   ├── test_core.py            # Core engine foundation tests
│   ├── test_phase2.py to 14.py # Phase-by-phase feature regression tests
│   ├── test_companion_vision.py# Loopback vision validation tests
│   └── *.test.cjs              # Node.js DOM and pet behavior tests
├── tools/                      # Tool wrappers
│   ├── filesystem_tool.py      # Sandboxed filesystem operations
│   ├── permission_gate.py      # Runtime permission enforcement
│   ├── terminal_tool.py        # Sandboxed command execution with command blacklist
│   └── web_tool.py             # Brave Search & keyless Bing search fallback
├── .env.example                # Safe environment variable template
├── .gitignore                  # Comprehensive git ignore rules
├── AI_WORKDESK_OS_SPEC_v0.1.md # Foundational architectural specification
├── DECISIONS.md                # Architecture Decision Records (ADRs)
├── main.py                     # FastAPI application server and WebSocket handler
├── bridge.py                   # Server bridge between FastAPI and headless engine
├── companion_vision.py         # Local companion vision endpoint router
├── start_workdesk.bat          # One-click Windows runner
├── test_pipeline.py            # Integration test for running server
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## Testing & Verification

The codebase comes with extensive automated test coverage across Python and Node.js test runners:

### Run Python Unit Tests
```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```
Runs 75+ automated unit tests covering the engine, state machine, permission matrix, worker creation, hybrid model routing, vault storage, and companion vision safety.

### Run Frontend & Companion Tests (Node.js)
```bash
node --test tests/pet-state.test.cjs tests/pet-awareness.test.cjs tests/dashboard.test.cjs
```
Runs 18 unit tests verifying dashboard state calculations, pet state transitions, Bongo input handling, cooldowns, and loopback frame sampling guards.

### Run End-to-End Pipeline Test
Start the server in one terminal (`python main.py`), then run in another:
```powershell
python test_pipeline.py
```
Validates the complete lifecycle: workspace creation, requirement decomposition by Main Brain, task assignment to workers, tool execution, and QA-2 validation scoring.

---

## Security & Privacy Invariants

1. **Local-First Data Storage**: All tasks, conversations, notes, approvals, and audit events persist locally in `data/workdesk.db` (SQLite). No operational data is transmitted to external telemetry servers.
2. **Secrets Protection**: API keys are isolated to `.env` (which is never tracked by Git). `.env.example` contains only clean placeholder structures.
3. **Bounded Tool Execution**:
   - Filesystem operations are strictly confined within the project workspace directory; path traversal (`../`) is blocked.
   - Terminal execution runs through a strict command blacklist preventing destructive commands (`rm -rf`, `format`, `del /s`, `shutdown`, etc.).
4. **Isolated Companion Vision**:
   - Visual observation frames never touch disk and cannot trigger tools or state mutations.
   - Only numeric loopback addresses (`127.0.0.1`, `localhost`) are accepted; remote endpoints and proxies are rejected.
   - Password fields, settings forms, and private UI regions are automatically redacted from captured frames.

---

## License

This project is licensed under the [MIT License](LICENSE).
