# Resolved Open Decisions — AI WorkDesk OS v0.1

Locked before Phase-1 coding, per Specification v0.1 §7. Every decision is a default that
can be revisited; changing one does not change the specs, only the implementation.

| # | Decision | Resolution (v0.1) | Rationale |
| --- | --- | --- | --- |
| 1 | Persistence | SQLite, single file `data/workdesk.db`, WAL | Zero-dependency, survives restart (Spec 01 §2.7), enough for headless Phase 1 |
| 2 | Message bus | In-process, threaded, in `bus.py` | Phase-1 headless core; contract (envelope/channels/dedup/DLQ) is transport-agnostic, so a Redis/NATS swap later does not touch callers |
| 3 | Memory store | SQLite tables with `access_scope` filtering | Same file as tasks/audit = one consistent snapshot; vector search can be layered on later |
| 4 | Model router | Not built; stub intelligence only | Real router is Phase 8; the worker `model_preferences` field is already reserved in the schema |
| 5 | Audit retention | Keep all rows; retention policy configurable | Spec says configurable; no default limit imposed yet |
| 6 | Worker runtime isolation | In-process (Phase 1) | Fastest correct skeleton; container/process isolation is a later hardening step, interfaces already per-worker |
| 7 | Permission resolution | Most-specific match → deny-by-default → runtime user override | Locked in `permissions.py`; pattern grammar stays simple fnmatch for v0.1 |
| 8 | UI scope | None (headless) | Work Graph / Virtual Office are Phase 7 |
| 9 | **Server integration** | Headless core **is** the runtime layer; FastAPI/UI delegates to it via `bridge.py` | The parallel FastAPI/WS implementation (`main.py`, `agents/`, `core/`, `memory/`, `tools/`) was merged INTO the headless core — single state machine, single persistence, single audit trail. Old modules stay on disk as legacy but are not called by the server. |

## Server integration notes (post-decision)

- `bridge.py` (`WorkDeskBridge`) is the only boundary: `handle_request()` maps `/api/chat`
  and project-task endpoints onto `Engine.submit`/`clarify`; audit hooks are wrapped into a
  thread-safe queue and pumped to the WS bus without blocking the asyncio loop.
- **Pump must never block the event loop.** The first implementation used
  `queue.Queue.get(timeout=1.0)` inside the pump task and deadlocked uvicorn startup
  (server process alive, port never bound). Fixed with `get_nowait()` drain +
  `asyncio.sleep(0.05–0.25)`.
- `register_worker` is **idempotent** (UPDATE in place, preserving stats) so re-seeding the
  same worker ids across restarts against the persistent DB is safe.
- `/api/memory`, `/api/approvals`, `/api/audit` now read the engine's SQLite tables.
- Verified end-to-end: `test_pipeline.py` (project → task → DONE → QA-2 PASS → artifacts)
  and `smoke_test.py` (simple chat, QA-1 clarification gate, clarified completion, memory,
  audit, approvals, WebSocket event stream) both green; core suite still 9/9.

## Phase 2 — Main Brain intelligence layer (v0.2)

Implemented per Spec §16 Phase 2, still deterministic (LLM lands in Phase 8):

- **Requirement specification**: `RequirementSpec` (goal / intent / output_type / data need /
  privacy / risk / constraints / model-hint / criteria / components) replaces the loose
  Phase-1 spec dict; persisted as `task.spec` JSON so QA-1, PM, workers and audit share one
  frozen requirement.
- **QA-1 = completeness + ambiguity + contradiction + feasibility**. Phase-1 only checked
  missing fields; Phase-2 adds vague-reference/amount ambiguity, output-conflict / negation /
  destructive-conflict contradiction, and capability-gap feasibility (every component must
  map to an available worker). Clarification now surfaces all blocker categories.
- **New state edge**: `CLARIFYING → FAILED` (`QA1_FAIL_FINAL`) was already coded in
  `accept_request`/`clarify` but missing from the transition table — a latent crash on the
  "user insists on an unsatisfiable requirement" path. Added to `states.ALLOWED`.
- **Simple/complex classification lives in the core** (`MainBrain.classify_text`); the
  bridge no longer uses its own keyword list. Greetings/questions are answered directly by
  MB; capability-gapped requests are always classified complex so MB must intervene.
- **Worker selection is stats-ranked** (qa_pass_rate + EWMA failure_rate + experience) and
  the Task Group now contains ONLY the selected team (`team_plan`), not every worker.
- **Permission planning**: MB probes read/create/modify/delete/install/send policies and
  records expected approvals (ASK/EXPLICIT) and outright DENY into `approvals_expected`,
  audited as `permission_plan`. Sensitive requests (passwords/salary/health…) get a
  `model_hint=local` routing signal for Phase 8.
- **Global-memory learning is evidence-gated**: a clarification answer stores
  `default_output_format` (MEDIUM confidence); a COMPLETED task that *used* the preference
  corroborates it; ≥ 2 corroborations promote to HIGH. No uncontrolled self-rewrite.

## Phase 3 — Worker ecosystem (v0.3)

Implemented per Spec §16 Phase 3 + §5 worker creation paths:

- **Worker Creator is a MB meta-worker** (`worker_creator.py`): designs complete profiles
  (identity/personality/behavior/communication/skills/tools/memory rules), registers,
  activates and instantiates workers. Creation = `install` → resolves the permission
  policy (default EXPLICIT) → auto-passes under `auto_approve`, stays PENDING otherwise;
  audited as `worker_created`/`worker_upgraded`.
- **Capability-gap auto-fill loop**: QA-1 feasibility gap → MB (or PM, as fallback)
  `maybe_create_workers` → re-plan → re-run QA-1. Gap → create → execute → QA-2 now runs
  end to end. Non-auto-approve engines never create silently: the gap surfaces as
  clarification and insisting fails honestly (QA1_FAIL_FINAL).
- **Dynamic stub skills**: created workers get a runtime stub handler producing a
  placeholder artifact labelled as a Phase-3 stub, with a `Summary:` section so QA-2
  content checks pass. Real implementations are Phase 8+.
- **Worker persistence**: the in-memory pool is restored from the registry at startup
  (`_restore_workers`, incl. dynamic skill handlers) — workers and covered gaps survive
  application restarts.
- **Bug fixes found while building the ecosystem**:
  1. `_finalize` persisted the artifact manifest by reading it back from the DB (always
     empty). It now receives the in-memory manifest explicitly.
  2. Global-memory output injection happened *after* components were derived, so a
     learned `default_output_format` produced a task that passed QA-1 with 0 components
     and completed vacuously. Components/criteria are now rebuilt after injection.
  3. QA-2 passed vacuously when a worker errored and produced no artifact (e.g. the
     writer without a `save_path` raised, was escalated, and the empty manifest passed).
     QA-2 now requires every planned component to have produced an artifact
     (`artifact_missing` failure), and the writer defaults to
     `<project_dir>/<project>/report.md`.
  4. `classify` returned "simple" for execute intents with incomplete requirements, so
     the bridge answered them with a canned reply instead of the QA-1 gate. Execute
     intents are now always "complex" (the simple fast-path is for greet/ask only).

## Phase 4 — PM lifetime system (v0.4)

Implemented per Spec 04 §5.3 (PM schema) + Spec 03 §4.5 (evidence-gated lessons)
+ §16 Phase 4:

- **Persistent PM identity across restarts.** A PM is created once per project and
  restored from the `pms` registry at engine startup (`_restore_pms`), exactly like
  workers. Restarting the application reuses the same pm_id and its accumulated record;
  there is no "new PM every run". Different projects never share a PM.
- **PM institutional memory** (`ProjectManager.record_after_task`, called at every
  terminal task state COMPLETED/FAILED/CANCELLED):
  - `task_history` / `group_history` — the PM's project ledger (new `task_history_json`,
    `group_history_json` columns, additive DB migration for existing databases).
  - `worker_performance_map` — snapshot of each involved worker's QA pass/fail, EWMA
    failure rate and execution time after every task (feeds Spec §5.6 selection inputs).
  - Project knowledge — each task result + artifact manifest is written to the PROJECT
    memory layer under the PM's own `own_project_id` (memory isolation unchanged:
    cross-project access stays denied by the existing access matrix).
  - Conventions — recurring successful `output_type`s are remembered.
  - Decisions — rework decisions are logged with cycle count and final outcome.
- **Evidence-gated lessons (Spec 03 §4.5).** A task that needed QA rework, or failed
  outright, produces a lesson candidate keyed by capability. The lessons table keeps
  ONE record per (pm, key); a corroborating case upgrades it in place — evidence count
  +1, promoted to HIGH + `stored` at `LESSON_PROMOTE_MIN_EVIDENCE` (2), evidence refs
  accumulated. This is deliberate: the PM learns from repeated evidence, not from a
  single self-serving conclusion.
- **Engine API**: `pm_profile(project_id)` (full persistent record incl. lessons) and
  `pm_history(project_id)` (chronological task ledger) — ready for the Phase 7 WorkDesk
  UI and for Phase 6 rework-assignment heuristics.
- **Explicit non-goals (this phase):** stored lessons do not yet steer execution —
  they are institutional memory; Phase 6 (QA/rework engine) will consume them.

## Phase 5 — Tool control (v0.5)

Implemented per §16 Phase 5 + Spec 03 §4.6. Principle: **having a tool ≠ unlimited
permission to use it.**

- **Tool registry** (`tools.py`): filesystem (list/read/write/mkdir/delete),
  sandboxed terminal (`terminal.run`), browser stubs (Phase 7). Tools are
  capabilities; permission is a separate decision made per invocation.
- **Single point of scope adjudication.** Paths are normalized and classified as
  project/system; the handler never re-decides scope — the permission matrix does.
  (Initially handlers double-checked scope and broke the MB's EXPLICIT system-delete
  policy; removed in favour of policy-only adjudication.)
- **Approval lifecycle.** ASK/EXPLICIT resolve → most recent approval for the same
  (actor, action, resource, tool): PENDING blocks (no duplicate requests), APPROVED
  releases the gate, DENIED allows a new request. `decide(APPROVED)` therefore makes
  the *next* invocation of that action execute — the approval is consumed by the
  request identity, not by the approval row.
- **Terminal safety**: dangerous-command blacklist (checked before any policy
  resolution) + timeout + project-dir cwd. Honest note: a blacklist is not a
  sandbox; a real VM boundary is Phase 8+.
- **Permission-granularity refinement**: ordinary project-file deletion is now ASK
  (was EXPLICIT via the broad `delete * → EXPLICIT` fallback), while important-file
  and system deletion stay EXPLICIT (more specific policy wins). This is a deliberate
  refinement: everyday cleanups no longer need explicit confirmation at every step.
  `test_phase2.py::test_permission_planning_high_risk` updated accordingly.
- **Non-goal**: worker skills still don't call tools autonomously — the tool layer is
  fully testable via `Engine.execute_tool`, wiring skills to tool chains is Phase 8+.

## Phase 6 — QA / rework engine (v0.6)

Implemented per §16 Phase 6. QA moves from improvised per-run judgment to a
spec-defined verification engine with a persisted, queryable history.

- **Failure field-name normalization: `criterion`.** The old ad-hoc
  `criteria_violated` is replaced by a single `criterion` key in every failure
  report; the P5-era tests were updated in lockstep.
- **QA-1 is persisted, not just acted on.** The requirement verdict produced inside
  `MainBrain._plan` is written to `qa_verdicts` as `stage=QA1` — a task's validation
  history starts at requirement time, not after execution.
- **QA-2 score formula.** `score = 1 − 0.25·high − 0.10·medium − 0.05·low` failures
  per cycle. Scores are advisory (the pass/fail verdict gates the loop); they make
  quality comparable across tasks without a threshold that would punish honest
  reports of multiple defects.
- **Validation history table `qa_verdicts`.** One row per (task, stage, cycle,
  component, criterion) verdict, covering QA-1 + every QA-2 cycle. `qa_history()`
  reads it in order; `task_validation_report()` aggregates it. This is the Phase 15
  audit-log companion for QA (decision metadata, not chain-of-thought).
- **Selective rework via capability consumption map.** P1's rework actually
  re-ran *every* component (conservative, since downstream dependencies were
  unknown). P6 adds `CONSUMES` (`writer` consumes `data`, `documenter` consumes
  `data`+`research`): rework redoes only the failed component + its direct
  consumers. Unrelated components (e.g. `research` when `data` fails) are left
  untouched — verified by `test_selective_rework_redoes_only_failed_components`.
- **New state edge `IN_QA → FAILED (RETRY_LIMIT)`.** The retry cap was enforced from
  `IN_QA`, but the state machine only had `REWORK → FAILED`; a permanently failing
  component hit an illegal-transition error instead of a clean FAILED. The edge is
  now part of the canonical table (P6 test `test_retry_limit...` was the first to
  walk that path).
- **`totals_correct` is scoped to the report-writing component.** The totals check
  used to scan *every* file artifact, so a research-notes file (which legitimately
  has no `Total:` line) failed the check and blocked multi-component tasks. It now
  applies only to the `writer.markdown` artifact; other checks (`has_summary`,
  `format_ok`) remain artifact-wide because every stub artifact carries a `Summary:`
  section by contract.
- **Lessons steer execution (Phase 4 → 6 hand-off).** A HIGH-confidence PM lesson
  on a failed component's capability causes that component to be reworked first,
  with the lesson text injected as `guidance` into the redo payload and surfaced in
  report artifacts as a `QA Note:` line; the application is audited as
  `rework_lesson_applied`. Lesson confidence is still evidence-gated (≥2
  corroborating cases), so the rework path learns from validated history, not from
  single impressions.

## Phase 7 — WorkDesk UI (v0.7)

Implemented per §16 Phase 7. The UI layer stays a thin client: every pixel-level
view is backed by engine read models; the server adds no second source of truth.

- **UI read models live in the engine** (`list_tasks` / `task_detail` / `list_pms`
  / `virtual_office` / `settings_snapshot`) as pure queries. The WorkDesk UI
  therefore cannot drift from the runtime — it renders whatever the engine
  actually persisted (tasks, QA verdicts, PM lessons, approvals, audit).
- **`/api/workers` now returns the real engine worker pool.** The old endpoint
  returned the legacy static catalog (avatar/description/statistics objects that
  never existed at runtime). P7 switches it to `Engine.worker_catalog()` —
  persistent profiles with real trigger/QA-pass/fail statistics.
- **Task results now carry `qa_score`.** Previously only `qa_cycles`/`rework_count`
  were persisted; the per-cycle score from QA-2 is now stored in the result so the
  task list and detail views can show it without recomputation. Older rows render
  as "—".
- **Static-asset cache busting.** The browser cached the pre-P7 `app.js` and the
  new sidebar never bound; every script/link reference in `index.html` now carries
  `?v=0.7.0` so a version bump forces a reload.
- **Resume is exposed to the UI** (`POST /api/tasks/{id}/resume`) so CLARIFYING /
  READY / PAUSED / CANCELLED tasks can be re-dispatched from the Tasks view.
- **Non-goal kept**: the UI is a browser workbench (real engine, real WS stream);
  a packaged Windows desktop shell is deferred to the Phase 10 expansion list.

## Phase 7.5 — UI reshape (user decision)

User: "移除 workgraph；virtual office 和 approval 应该是存在于每一个 chats 里，而不是单独存在于外边；删除会话记录".

- **Work Graph removed** as a global view (it duplicated the per-task detail
  pane; the legacy workspace tab still has its own graph component).
- **Virtual Office and Approvals moved inside every chat.** Each conversation
  now carries a session pane scoped by `conversation_id`: that chat's tasks
  (state distribution), the workers those tasks actually used, and its PENDING
  approvals with Approve/Deny. Rationale: each chat uses different workers and
  has a different flow, so the office/gates are conversation state, not global
  state. Engine read models (`list_tasks` / `virtual_office` / `approvals_pending`)
  accept `conversation_id`; tasks persist the id that created them.
- **Conversation records deleted** (49 files cleared) and the sidebar now has a
  per-conversation delete button (✕).
- **P8.1 follow-up (user decision):** the session pane moved from the chat
  bottom to a **right-hand collapsible panel** with four tabs — TASKS / WORKERS /
  APPROVALS / RESULT VISUALIZE — so each chat has its own inspectable
  workspace. RESULT renders deterministic bar visualizations (task counts,
  avg QA, state distribution, per-task QA scores) from the conversation's own
  tasks only.

## Phase 8 — Hybrid Model Router (v0.8)

Implemented per §12 / Phase 8.

- **Routing is a pure decision + persisted record.** `ModelRouter.route` is
  deterministic: privacy first (sensitive → LOCAL when `LOCAL_ENDPOINT` is set,
  else cloud-instant with the limitation audited), then capability pins
  (vision → multimodal expert), then complexity (simple → instant, complex →
  expert), then the worker default. Every decision has a fallback chain.
- **Workers never see the router.** They ask for a capable model; the engine
  routes each task component once (`Engine.route_group`) before the PM starts
  workers and persists `task_routes` + audit `model_routed`.
- **`task_routes` table** (new) is the queryable routing history; Settings shows
  stats and RECENT ROUTES; the task detail pane shows MODEL ROUTES per component.
- **The router decides but does not call** — model provider adapters (local
  OpenAI-compatible endpoint, OpenRouter) are the next step; the decision
  layer is complete and fully tested.

## Phase 10 — personal utilities & working area (v0.10)

- **One page per function.** Ten new views (Timer/Alarm/Stopwatch, Calculator,
  Notepad & MB Memory, Code Studio, Documents, Sheets, Slides, PDF, Media,
  Remote Device) are reachable from two new sidebar groups. `tools.js` owns
  all ten renderers; navigation is wired in `app.js` (wirePhase10).
- **Workspace file API** — `data/workspace/` exposed through
  `/api/workspace/{files,read,save,upload,file}` with a traversal-safe path
  resolver (rejects `..` escapes). Uploads land in type subdirs (code/docs/
  sheets/slides/pdf/media). Binary reads are detected via strict UTF-8 decode.
- **Sandboxed code run** — `POST /api/code/run` executes Python in a temp dir
  with a hard timeout (default 15s), output caps, size limit (60 KB) and an
  audit event `code_run`; the sandbox is deleted afterwards. Real execution
  verified (42, 55, 1..8 fibs).
- **Notes** — `notes` table with sections `user` / `mb`; My Notepad edits
  user notes while the MB Memory tab is a live read-only view of global memory.
- **Honest scope** — Remote Device is a roadmap page (security boundary: needs
  signed pairing, key management, session auditing); PDF creation is via
  browser Print→Save-as-PDF; code editing is single-file (no LSP); sheets are
  CSV-grid (no binary xlsx). These are documented as planned, not faked.
- **Testing** — `tests/test_phase10.py` (7 tests): ws save/read/list/delete,
  traversal escape denial, binary upload detection, notes

## Phase 11 — WorkDesk 2.0 (v0.11)

- **Vault is filesystem, not a table.** `data/vault/{my,mb}` as markdown files:
  Obsidian-style tooling (wiki links, full-text search, per-section isolation)
  falls out naturally, and users can sync/backup the vault with ordinary tools.
  Path resolution normalizes + enforces the section prefix → traversal attempts
  return `invalid_path` / `not_found` instead of escaping.
- **Worker names come from the skill, never the user.** `worker_design` parses a
  GitHub repo's `SKILL.md` frontmatter (`name` / `description`) and builds the
  profile; the wizard has no name field to type. `_TOOL_HINTS` infers tools +
  studio (research/code/sheets/slides/media/design/pdf/docs), with research and
  code ranked above document hints so a "research…writes findings" skill does not
  degrade into a docs worker.
- **Merge is idempotent upgrade, not duplicate.** `registry.register_worker`
  updates in place (same `worker_id` keeps statistics), and `worker_apply(mode=
  "merge")` dedups skills by capability and tools by name. Similarity is keyword
  overlap of name+skills; the wizard offers Create New / Merge into Selected.
- **Worker Studio is role-shaped.** Studio type is inferred per worker; the
  `code` studio shows a code file browser + run, `research` embeds a browser
  monitor iframe (X-Frame-Options limits which sites load — example.com works,
  many production sites refuse; a proxy/extension is the documented follow-up),
  `docs`/`sheets`/`general` show role/tools/jump cards.
- **Clear History has an asset boundary.** `clear_history` wipes conversations,
  tasks, approvals, audit and learning tables but deliberately keeps workers,
  PMs, vault and workspace — those are assets, not history.
- **Frontend cache lesson.** A stale `workers.js` (calling an unexported
  `showView`) survived a reload because the URL was version-pinned; the fix was
  `App.showView` + a version bump. Lesson: JS calling into IIFE-private helpers
  must go through the exported namespace, and any frontend change needs a
  cache-busting bump.
- **Direct value assignment ≠ user typing.** `bu.js` setting `textarea.value`
  does not fire `input`, so previews that rerender on `input` look stale; the
  vault now also rerenders on save, and tests must dispatch a real `Event('input')`
  to simulate typing.
## Phase 12 — WorkDesk 2.1 (v0.12)

- **MB memory is auto-synced, not hand-written.** `mb_sync()` rebuilds four
  living notes in `vault/mb/_auto/` from live system state (global memory,
  evidence-gated lessons, in-flight tasks + pending approvals, PM knowledge).
  The vault stays a plain markdown filesystem; the Main Brain just owns one
  folder of it. `Knowledge & Memory` was merged into this vault section — one
  entry, one source of truth.
- **Office Suite folds four views into one.** Documents/Sheets/Slides/PDF keep
  their original renderers and DOM ids; `view-suite` hosts them as lazy panes
  so no editor logic was rewritten. Sidebar shrinks by three entries.
- **Dashboard as default home.** The app boots into `view-dashboard` (was the
  chat hub); chat stays reachable via nav and quick-launch. KPI/vault counts
  required normalizing two API shapes (`vault/tree` returns `{files:[...]}`,
  not an array).
- **Server longevity.** keep-alive raised to 600s and a double-click
  `start_workdesk.bat` launcher (logs to `data/server.log`). No idle timeout
  on the WebSocket path.
- **Lesson from P12 UI debug:** moving sections into a wrapper by string
  surgery left stray `id="view-docs">` text nodes in the DOM (rendered as
  visible text); renderSuite also initially re-cleared the tab it had just
  activated (read active *before* clearing). Both caught in browser review.
## Phase 13 — Hive layer + Office Floor (v0.13, munder-difflin inspired)

- **Port the coordination, not the harness.** munder-difflin's value is its
  hive patterns (mailbox messaging, speech acts, blackboard, event log, office
  visualization) — its CLI-wrapper core is the opposite of this app's one-AI
  model, so node-pty/git/Pixi were consciously left out. The floor is DOM/CSS;
  the Main Brain is the god agent; a worker message is a real file in its
  inbox and outbox.
- **Message = file, twice.** One JSON per message, written to sender outbox +
  recipient inbox via temp-file + atomic rename (munder-difflin's single-writer
  rule, minus the git layer). Dedup by id when listing — a message legitimately
  exists in two boxes.
- **Anti-livelock is structural.** Only request/query/propose obligate a reply;
  `hops` increments per reply; cap 8 → refused + logged. Two workers can never
  ping-pong forever.
- **Blackboard single-scribe.** board.md is written only through
  `hive_board_put(scribe=...)`; the UI defaults the scribe to "pm". Shared
  plans therefore can't conflict, matching the god-scribe rule.
- **Office floor lives inside each chat** (user rule since P8: virtual office
  belongs in the chat session, not outside). It replaced the workers list, not
  the tabs — the session pane still has TASKS / OFFICE / APPROVALS / RESULT /
  PROJECT. Desk click = open that worker's studio (reusing P11).
- **Status is the visual.** munder-difflin's palette and overlays
  (thinking dots, blocked "!", success sparkle) were ported as CSS; the floor
  polls every 6s while the tab is active instead of pushing, keeping the
  single-AI model honest.
- **Testing** — `tests/test_phase13.py` (6 tests): inbox/outbox roundtrip, bad
  act rejected, hop-cap livelock refusal, conversation/agent filters,
  single-scribe board, state snapshot. 130/130 total.

## Phase 13b/c — Design worker scans sub-folders · per-chat Command Center

- **Design New Worker now scans the whole repo.** A root URL with no top-level
  SKILL.md triggers a recursive `git/trees?recursive=1` scan; every SKILL.md
  becomes a candidate (noise dirs skipped). One candidate → auto-design;
  several → pick list in the UI; picked file path is read directly (`.md`
  suffix short-circuits the `/SKILL.md` append — the first cut double-appended
  it and failed).
- **User correction: the office page belongs in every chat.** The screenshot
  the user shared was munder-difflin's Command Center (office floor + command
  tabs + agent strip). The OFFICE tab was rebuilt to that shape *inside each
  chat's session pane* — floor on top, COMMAND CENTER tabs
  (MONITOR/TASKS/APPROVALS/TERMINAL) with a QUEUE composer in the middle, the
  PM blackboard beside it, and an agent strip along the bottom with per-agent
  status and a `talk` button that targets the composer. Every chat renders its
  own copy because it is bound to `renderSessionPane(conversationId)`.

## Phase 14 — Task priority (drag to reorder) + live office heartbeat

- **Tasks carry a `priority` column** (db migration adds it if missing).
  `list_tasks` orders by `priority ASC, created_ts DESC`; a new
  `reorder_tasks(conversation_id, task_ids)` persists the user-chosen order
  and rejects task ids that do not belong to the conversation (HTTP 400).
  Route: `POST /api/tasks/reorder`.
- **Drag to prioritize in both task lists** — the session TASKS tab and the
  Command Center TASKS page render every row `draggable` with a grab handle
  (⠿). HTML5 drag & drop reorders the rows, then calls `Api.reorderTasks` and
  refreshes; the order survives reloads because it lives in the database, and
  it is per-chat (the list is scoped by `conversation_id`).
- **Live office heartbeat** — the OFFICE poll now runs every 4s and overwrites
  each desk/strip badge from `hive_state`'s worker roster, so statuses move
  without a full reload. Main Brain's own status is derived: pending approvals
  → `needs you`, recent hive events → `working`, otherwise `idle`.
- **Testing** — `tests/test_phase14.py` (4): default newest-first, reorder
  persistence (twice, last wins), foreign-id rejection, hive_state live
  roster. 134/134 total.

## Phase 15 — Command Center extended: nine tabs, two rows

User said "尽量的模拟" — keep imitating munder-difflin. The Command Center now
carries two tab rows: MONITOR/TASKS/APPROVALS/TERMINAL (row 1) and
GRAPH/ACTIVITY/MEMORY/COMMANDS/ASK ME (row 2), plus a header strip with
`auto mode` / `memory: minimal` / an estimated MB `ctx` readout.

- **TERMINAL** became a real event terminal — timestamped lines with a `$`
  prompt marker drawn from the hive event log.
- **GRAPH** renders live task-state and agent-state distribution bars from
  the session's own tasks/workers (pure DOM, no chart lib).
- **ACTIVITY** streams the audit timeline tail (`/api/audit`), filtered to the
  chat's tasks.
- **MEMORY** shows the Main Brain's vault auto-notes (mb/_auto count + a
  global-memory preview) — pitfall: `vaultTree()` defaults to the `my`
  section, the memory page must pass `"mb"`.
- **COMMANDS** — shortcuts wired to real engine calls: *Ask all workers for
  status* (sends a `query` "What are you up to?" to every worker in the chat),
  *Sync Main Brain memory* (`POST /api/vault/mb-sync`), *Pending approvals*
  (jumps to the APPROVALS page), *New task in chat* (focuses the composer).
- **ASK ME** pipes a typed question into the main chat composer.
- Tab choice survives the 4s heartbeat re-render (`window._ofActiveCcTab`).
- Frontend-only; no backend change, no test change (134/134 stands).

## Phase 16 — UI cleanup: registry is profiles, workspace lives in chats

User uploaded a chat-UI concept sketch (office workflow view left, Main
Brain / Project Manager tab selection + Chat UI + other chat session
functions right) and gave three changes:

1. **Worker Registry has no "Open Workspace"** — a workspace is a chat
   product and only exists inside chats that do heavy work. Removed the
   `wreg-open` button from registry cards (now a single `Edit Profile`
   action → `openDesign(wid)`) and rewrote the registry intro:
   "Workers are persistent AI employees. Edit a profile to adjust skills,
   tools and permissions — their live workspace lives inside the chats
   that actually use them." Worker studio still opens from inside a chat
   (OFFICE floor desks / agent strip cards).
2. **This Chat Session panel is freely resizable** — added a `#spResize`
   drag handle between the chat and the session sidebar; dragging changes
   `flex-basis` (clamped 300–780px), persisted in `localStorage
   wd_sp_w` and restored on boot (skipped while collapsed).
3. **Design New Worker leaves the sidebar** — the entry already lives in
   the Worker Registry header (`+ Design New Worker`); removed the
   redundant `navDesignBtn` sidebar item. `navDesignBtn` references in
   app.js / workers.js are null-guarded and harmless.
- Verified in browser: sidebar has no Design item, registry cards show
  only Edit Profile, drag sets flexBasis 547px and saves to localStorage.
- Frontend-only; cache bump v=0.16.0; 134/134 tests unchanged.

## Phase 17 — Chat main rebuilt as office workflow view (concept sketch)

User confirmed building the uploaded chat-UI concept: office workflow view
on the left, Main Brain / Project Manager tab selection + Chat UI on the
right, other chat session functions remain the right sidebar.

- `#chatMain` is now a row: `#chatWorkflow` (236px) + `#chatCenter`.
- **`#chatWorkflow`** — OFFICE WORKFLOW VIEW header, MAIN BRAIN as a
  hexagon (clip-path) with live status, below it a 2×N grid of worker
  desks (hex avatar + name + status pill; status classes
  working/waiting/completed). Desks come from `spState.workers`
  (virtual office) overlaid with the hive roster on a 4s heartbeat
  (skipped when the chat view is not active); clicking a desk opens the
  worker studio.
- **`#chatCenter`** — `MAIN BRAIN / PROJECT MANAGER` tabs. Brain tab is
  the original chat (header, clarification gate, log, composer). PM tab
  shows `renderChatPm()`: PM identity card (hex avatar, manages
  project(s) linked to this chat, task/done/working/failed stats), tasks
  with state pills + QA %, deliverables paths, QA-history summary;
  clicking a task opens the task detail.
- Fixed a long-standing noise bug found during verification:
  `refreshSidebar` wrote into a `projectList` element that never existed
  (37 console errors per refresh) — now null-guarded.
- Verified live: MB hex shows working, Alex Researcher desk AVAILABLE,
  PM tab renders Project Manager card + 1 task + 3 sections, brain/PM
  tabs switch cleanly, console errors down to pre-existing legacy ones.
- Frontend-only; cache bump v=0.17.0; 134/134 tests unchanged.

## Phase 17b — Debug: all non-chat views went blank

User reported every page except chat stopped working. Root cause: the
Phase 17 chatMain rebuild left an **extra `</div>`** in the HTML (the old
chatMain close tag remained in the tail while the new block already closed
it). Browsers auto-recover by popping unclosed elements out of `<main>`,
so `#spResize`, `#sessionSidebar` and every other `.view` section were
lifted to `<body>` level and laid out in normal flow *below* the
full-height `#shell` (y≈960–1920px, off-viewport). A Cici-translate
extension class on `<body>` was a red herring — removing it changed
nothing.

Fix: removed the single surplus `</div>`; the view-chat block now balances
52 `<div>` / 52 `</div>`.

Verified in browser: all 19 views live inside `#main`, every nav target
renders at y=0 with content (dashboard 6228 chars … settings 5011), chat
keeps workflow + session sidebar (TASKS/OFFICE/APPROVALS/RESULT/PROJECT).
Frontend-only; 134/134 tests unchanged.

## Phase 18 — ChatAnywhere free AI relay integration

User asked to connect `https://github.com/chatanywhere/gpt_api_free` as a
cloud model provider. This is an OpenAI-compatible free/low-cost relay:
register at https://chatanywhere.tech (bind GitHub) for a free key —
weekly 50k-point quota + 100 requests/day; host `api.chatanywhere.tech`
(CN) / `api.chatanywhere.org` (outside CN — the project default here,
since the user is in Malaysia).

What was added (backed by the existing Phase 8.2 provider layer — no new
client class needed, `OpenAICompatProvider` already speaks the OpenAI
protocol):
- `core/config.py` + `src/workdesk/config.py`: `CHATANYWHERE_API_KEY`,
  `CHATANYWHERE_ENDPOINT` (env-overridable), `CHATANYWHERE_MODEL`.
- `src/workdesk/model_router.py`: cloud provider is now ChatAnywhere when
  its key is present, OpenRouter remains the fallback; `provider_status()`
  reports `chatanywhere_configured/endpoint/model`.
- `bridge.py` + `main.py`: `POST /api/settings/chatanywhere` persists the
  key to `.env` (line-scoped replace) and hot-applies it to the running
  process — no restart needed.
- Settings UI (MODEL ROUTER card): key input + Save + status rows +
  registration hint. `.env` ships with the free-key placeholder and the
  `api.chatanywhere.org` endpoint for outside-CN use.

Verified live: Settings page renders the new card; filling a test key
flips the provider to active through the API immediately and writes
`.env`; clearing it disables again. 134/134 tests unchanged.

- **Testing** — `tests/test_phase12.py` (4 tests): mb-sync writes four auto
  notes, global memory appears in `global-memory.md`, sync idempotent,
  auto notes searchable. All roots redirected to temp dirs; 124/124 total.

- **Testing** — `tests/test_phase11.py` (7 tests): vault CRUD/search/traversal/
  section isolation, clear-history, skill design (mocked fetch), create/merge/
  update, studio read model. All roots redirected to temp dirs; 120/120 total. CRUD + section
  isolation, code run ok/error/size-limit. The workspace root is redirected to
  a temp dir so tests never touch production files.

## Phase 9 — learning system (v0.9)

- **One pipeline, three scopes.** `src/workdesk/learning.py` turns a terminal
  task outcome into lesson candidates for the PM (`pm`), the participating
  workers (`worker`, each learning only the capabilities it executed per the
  team plan) and the Main Brain (`global`, keyed by capability and aggregated
  across projects). `lessons` gains `scope`/`owner_id`/`applied_count`/
  `last_applied_ts` (idempotent DB migration; existing PM lessons are
  backfilled to scope=pm).
- **Evidence gating kept honest.** Candidates start LOW with one ref;
  corroborating cases raise evidence_count and confidence (MEDIUM >=2, HIGH at
  LESSON_PROMOTE_MIN_EVIDENCE). Only HIGH + `stored` lessons surface as QA
  hints. The Phase-4 lesson key convention (capability) is preserved so old PM
  lessons upgrade in place.
- **Applied loop closes the cycle.** Before each QA-2 verdict, HIGH lessons
  for the task capability are counted (`applied_count`, status `applied`) and
  audit-logged as `lesson_applied`. QA-2 failure sets are now accumulated per
  task, so only components that actually failed QA-2 produce lessons (the
  writer no longer learns the data worker's failures).
- **Boundaries respected.** `for_owner(scope, id)` returns only that owner's
  lessons; hints consult global + pm scopes only; workers never see lessons of
  other workers or projects.

## Phase 8.2 — provider adapters: the router calls (v0.8.2)

Follow-up to Phase 8: "decides but does not call" is resolved.

- **`src/workdesk/model_providers.py`** adds `OpenRouterProvider` (cloud,
  `OPENROUTER_API_KEY`) and `OpenAICompatProvider` (any OpenAI-compatible
  local endpoint — Ollama/LM Studio/vLLM at `LOCAL_ENDPOINT` + `LOCAL_MODEL`).
  Both use stdlib urllib (the core stays dependency-free).
- **`ModelRouter.call(decision, messages)`** invokes the routed model, walks
  the fallback chain on failure, records every attempt (provider/model/ok/error)
  and audit-logs `model_called` / `model_call_failed`. Local primaries call
  `LOCAL_MODEL` by name (the endpoint is a base URL, not a model).
- **`POST /api/model-router/call`** exposes route→invoke→fallback as a one-off
  call; Settings gains a **TEST MODEL CALL** panel (capability/complexity/
  privacy selectors) that shows the decision, the invoked model, duration and
  the response. Verified live against OpenRouter: simple→`openai/gpt-4o-mini`,
  complex/research→`anthropic/claude-sonnet-4.5`, both returning real text.
  `max_tokens` defaults to 256 so free-tier credit limits don't 402.
- **Boundary kept:** worker execution remains deterministic (mock workers);
  wiring worker outputs through `router.call` is a Phase 9+ decision, not done
  here, so the whole Phase 1-8 regression stays green.

## Notable extensions to the spec made during implementation

- Added transitions `PAUSED → READY`, `CANCELLED → READY` (resume from checkpoint) and
  `RUNNING → READY` (crash restart) to the task state machine — the spec defined resume
  conceptually but not these exact edges.
- QA-2 failure attribution: a content failure found in a downstream artifact is attributed
  to the **responsible component** (e.g., wrong totals → `data.summarize`), and rework
  re-runs the failed component **plus its downstream dependents** — never the full project.
- PM lesson records are keyed per (pm, capability) with **in-place upgrades** rather than
  append-only rows: a lesson is a single fact whose evidence/confidence grows, so the
  registry never accumulates duplicate lesson entries and lookups stay single-row.
- Tool actions map onto the existing permission actions (`fs.write`→create, `fs.delete`
  →delete, `terminal.run`→execute) so the Spec 03 §4.6 policy matrix governs tools
  without a second policy language.
- P6 additions: `IN_QA → FAILED (RETRY_LIMIT)` state edge; `CONSUMES` capability map
  for selective rework; `criterion` as the single failure-field name; `totals_correct`
  scoped to report-writing artifacts; `qa_verdicts` table as the queryable
  validation history (see Phase 6 chapter above).
- P7 additions: engine-side UI read models; `qa_score` persisted in task results;
  real worker pool behind `/api/workers`; static-asset cache busting (see Phase 7
  chapter above).
- P7.5 additions: `tasks.conversation_id` and `approvals.task_id` columns; session
  pane inside every chat; conversation delete (see Phase 7.5 chapter above).
- P8 additions: `task_routes` table + `ModelRouter`; `route_group` per task; audit
  `model_routed`; `/api/model-router` (see Phase 8 chapter above).


## Phase 18b/18c — search-engine-tool 实况接入 + ChatAnywhere 链路修复（完成）

- search-engine-tool（bravekingzhang）：不引入 puppeteer/selenium，`tools/web_tool.py` 自实现 keyless Bing HTML 抓取（`_search_bing_sync` + `_parse_bing` + `_decode_bing_ck`），Brave key 存在时优先；`runtime.py` 的 `research.search` skill 为实况，结果落盘 `<project_dir>/<project_id>/research_notes.md`（UTF-8）。已端到端实测：POST /api/chat 调研任务 → QA-2 PASS → research_notes.md 含真实 Bing 结果。
- 测试污染根因（重要教训）：`tools/web_tool.py` 顶层 `from core import config` 触发 `core/config.py` 的 `load_dotenv`，把 .env 的真实 key 注入测试进程 env → 使 test_phase8 的 provider_status 断言失败。修复：web_tool 只读 `os.environ`（server 侧 bridge 早已加载 .env），彻底解耦无副作用。
- ChatAnywhere 403 修复：Cloudflare 需要 User-Agent，`model_providers.OpenAICompatProvider._post` 补 `User-Agent: Mozilla/5.0 ...` 头；实测 `.org`/`.tech` 双端点 gpt-4o-mini/deepseek-chat 均 200。
- 模型名映射：ChatAnywhere 只服务自身模型列表，`ModelRouter._effective_model()` 在 provider.name=="chatanywhere" 时把路由决策名（如 anthropic/*）改写为 `CHATANYWHERE_MODEL`（默认 gpt-4o-mini），fallback 同样映射。新增单测 `test_chatanywhere_maps_routed_models`。
- 全量测试：13 个文件 143 例全绿；server 已重启，真实链路验证 `WORKDESK-LIVE-OK`。


## Phase 18d — Full-function debug + Liquid UI (2026-09-13)

### Bugs fixed
1. `POST /api/workers` 422 -> 200: handler now takes pydantic `WorkerProfile` body;
   bridge.worker_create maps profile -> engine.install_worker_from_profile (SQLite single source).
2. `POST /api/approvals/resolve` 500 -> 200: added `ApprovalResolveRequest` pydantic body.
3. `worker_catalog()` rows now carry `id` alias of `worker_id` (frontend reads `w.id`).
4. Dashboard MODEL ROUTER: `provider_status()` returns dict but UI mapped it as array -> now
   builds `[{name, ok}]` from `local_configured / openrouter_configured / chatanywhere_configured`.
5. Settings page read `mr.providers` but `bridge.settings()` did not expose it -> added
   `"providers": provider_status()`.
6. Simple chat replies were Phase-1 rule-engine placeholders -> `_chat_model_reply()` now routes
   through the Phase-8 model router (fallback to placeholder if no provider reachable).
7. Liquid theme compositing: `mix-blend-mode:screen` + `backdrop-filter` made the #main area
   disappear from rendered frames -> removed both (kept semi-transparent panels + animated blobs).

### Liquid UI (浅蓝 + 宇宙紫 + 白)
- `:root` variables remapped to light palette; 220 hardcoded hex colors remapped across
  style.css / views.js / workers.js / tools.js.
- Animated liquid gradient blobs (2 fixed layers, 18-26s alternate drift), flowing hover
  gradient on nav items, gradient-flow primary buttons, glass cards with glow shadows,
  dual-glow brand dot, gradient chat bubbles.
- Cache bump `v=0.18.0` -> `v=0.19.0` (index.html).

### Verified
- API: workers create/list, approvals resolve, chat simple (real model reply) all green.
- Browser walkthrough: 13 nav views + chat session 5 tabs (Tasks/Office/Approvals/Result/Project)
  all render under the liquid theme.
- Full regression: 13 test files green (143 baseline cases).
