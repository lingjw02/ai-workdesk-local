"""WorkDesk engine facade: wires Spec 01-04 into one headless runtime.

Phase-1 scope: no UI. The engine persists everything to SQLite, so task state,
memory, audit, approvals and registries survive restart (Spec 01 §2.7 resume).
"""
import json
from pathlib import Path

from . import config, db, ids
from .bus import MessageBus
from .envelope import Envelope
from .memory import MemoryManager
from .permissions import PermissionManager
from .registry import Registry
from .runtime import MainBrain, ProjectManager, QA, StubWorker
from .states import TaskState, TERMINAL
from .task import Task, TaskGroup
from .tools import ToolRegistry
from .worker_creator import WorkerCreator
from .model_router import ModelRouter, RouteRequest
from .learning import LearningSystem


class Engine:
    def __init__(self, db_path=None, auto_approve=None, project_dir=None,
                 auto_create_workers=None):
        self.config = config
        self.db_path = db_path
        self.db = db.init(db_path)
        self.bus = MessageBus()
        self.memory = MemoryManager(self.db, self.bus)
        auto = config.AUTO_APPROVE_DEFAULT if auto_approve is None else auto_approve
        self.auto_approve = auto
        self.permissions = PermissionManager(
            self.db, self.bus, auto_approve=auto)
        self.registry = Registry(self.db, self.bus)
        self.qa = QA()
        self.mb = MainBrain(self)
        self.worker_creator = WorkerCreator()
        # Phase 5: tool registry (capabilities are separate from permissions)
        self.tools = ToolRegistry(self)
        # Phase 8: task-based hybrid model routing (local/cloud/api + fallbacks)
        self.model_router = ModelRouter(config, audit=self.permissions.audit)
        # Phase 9: learning system (PM / worker / global evidence-gated lessons)
        self.learning = LearningSystem(self.registry, audit=self.permissions.audit)
        # Phase 3: runtime skill handlers for dynamically created workers
        self.skill_handlers: dict[str, callable] = {}
        # Phase 3: capability gaps auto-fill workers (defaults to following auto_approve)
        self.auto_create_workers = auto if auto_create_workers is None else auto_create_workers
        self.pms: dict[str, ProjectManager] = {}
        self.workers: dict[str, StubWorker] = {}
        self._cancel_flags: dict[str, bool] = {}
        self.project_dir = Path(project_dir) if project_dir else config.OUT_DIR
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.bus.audit_hook = self._on_bus_message
        self._restore_workers()
        self._restore_pms()

    # ---- protocol audit hook: decision metadata, never chain-of-thought ----
    def _on_bus_message(self, env: Envelope) -> None:
        try:
            if env.type == "COMMAND":
                self.permissions.audit(env.from_role, env.from_id, f"command:{env.payload.get('op', '')}",
                                       reason=str(env.payload.get("component", "")), task_id=env.task_id)
            elif env.type == "ESCALATION":
                self.permissions.audit(env.from_role, env.from_id, "escalate",
                                       reason=str(env.payload.get("reason", "")), task_id=env.task_id)
            elif env.type == "APPROVAL_REQUEST":
                self.permissions.audit(env.from_role, env.from_id, "approval_request",
                                       reason=f"{env.payload.get('action')} {env.payload.get('resource')}",
                                       task_id=env.task_id)
        except Exception:  # noqa: BLE001 - audit must never break the flow
            pass

    # ---- worker ecosystem ----
    def seed_worker(self, worker_id: str, name: str, skills: dict,
                    fail_once: list[str] | None = None,
                    sleep_skill: dict | None = None,
                    personality: dict | None = None,
                    behavior_rules: list[str] | None = None,
                    role_class: str = "WORKER") -> str:
        skill_recs = []
        for sid, meta in skills.items():
            sid_full = self.registry.register_skill(name=sid, entry_point=f"stub:{sid}",
                                                    tools_required=meta.get("tools", ["FILESYSTEM"]))
            skill_recs.append({"skill_id": sid_full, "primary": True,
                               "capability": meta.get("capability", sid)})
        # Phase 3: complete the worker profile (identity, behavior, memory rules)
        persona = personality or {"traits": ["focused", "thorough"],
                                  "tone": "professional",
                                  "communication_style": "concise status updates"}
        rules = behavior_rules or ["report blockers to the PM",
                                   "follow the permission policy"]
        wid = self.registry.register_worker(worker_id=worker_id, name=name, role_class=role_class,
                                            personality=persona, behavior_rules=rules,
                                            skills=skill_recs,
                                            tools=[{"tool": "FILESYSTEM",
                                                    "permissions": {"read": True, "write": True}}],
                                            permissions={},
                                            memory_rules={"group_memory": True,
                                                          "own_experience": True,
                                                          "cross_project": "NEVER"})
        self.registry.activate(wid)
        self.workers[wid] = StubWorker(self, wid, name, skills,
                                       fail_once=fail_once, sleep_skill=sleep_skill)
        return wid

    # ---- Phase 3: capability-gap auto-fill ----
    def _restore_workers(self) -> None:
        """Rebuild the in-memory worker pool from the registry (persistent workers
        survive an application/computer restart; Spec 04 §5.6). Dynamic skill
        handlers are re-registered from their stub entry points."""
        from .worker_creator import _dynamic_handler
        skill_map = {r["skill_id"]: r for r in
                     db.query("SELECT skill_id, name, entry_point FROM skills")}
        for row in db.query("SELECT * FROM workers WHERE status IN ('AVAILABLE','ACTIVE')"):
            wid = row["worker_id"]
            if wid in self.workers:
                continue
            meta: dict[str, dict] = {}
            for s in json.loads(row["skills_json"] or "[]"):
                sid = s.get("skill_id")
                info = skill_map.get(sid)
                short = (info["name"] if info is not None else None) or sid
                cap = s.get("capability") or short.split(".")[0]
                meta[short] = {"capability": cap}
                if info is not None and str(info["entry_point"] or "").startswith("stub:"):
                    self.skill_handlers.setdefault(short, _dynamic_handler(self, cap))
            self.workers[wid] = StubWorker(self, wid, row["name"], meta)

    # ---- Phase 5: tool execution for workers (through the permission gate) ----
    def execute_tool(self, worker_id: str, tool_name: str, action: str = "run",
                     params: dict | None = None, task_id: str | None = None):
        """A worker invokes a tool. Capability (has the tool) and permission
        (may use it here) are checked separately; ASK/EXPLICIT levels raise an
        approval that stays PENDING unless auto_approve (demo)."""
        return self.tools.execute("WORKER", worker_id, tool_name, action,
                                  params or {}, worker_id=worker_id, task_id=task_id)

    def tool_catalog(self) -> list[dict]:
        return self.tools.list()

    # ---- Phase 4: PM registry restore (persistent identity across restarts) ----
    def _restore_pms(self) -> None:
        for row in db.query("SELECT pm_id, name, project_id FROM pms WHERE status != 'RETIRED'"):
            pid = row["project_id"]
            if pid in self.pms:
                continue
            self.pms[pid] = ProjectManager(row["pm_id"], row["name"], pid, self)

    # ---- Phase 3: capability-gap auto-fill ----
    def maybe_create_workers(self, spec: dict, task_id: str | None = None) -> list[str]:
        """Create a worker for every component capability no existing worker covers.
        Creation is permission-gated (Worker Creator); returns the ids actually created."""
        created: list[str] = []
        if not self.auto_create_workers:
            return created
        for comp in spec.get("components", []):
            cap = comp.get("capability")
            if not cap:
                continue
            covered = any(
                any(meta.get("capability") == cap for meta in w.skills.values())
                for w in self.workers.values())
            if covered:
                continue
            wid, status = self.worker_creator.create(
                self, cap, description=str(spec.get("goal") or "")[:200], task_id=task_id)
            if status == "created":
                created.append(wid)
        return created

    # ---- Phase 3: worker catalog & manual install ----
    def worker_catalog(self) -> list[dict]:
        """Full worker profiles incl. stats, status, skills, tools, permissions."""
        rows = []
        for wid in sorted(self.workers):
            row = self.registry.get_worker(wid)
            if row:
                row.setdefault("id", row.get("worker_id"))
                rows.append(row)
        return rows

    def install_worker_from_profile(self, profile: dict) -> str:
        """User-manual-creation path: install a worker from a full profile dict."""
        skill_recs, meta = [], {}
        for s in profile.get("skills", []):
            sid = s.get("skill_id") or s["name"]
            sid_full = self.registry.register_skill(name=sid, entry_point=f"stub:{sid}",
                                                    tools_required=s.get("tools_required",
                                                                         ["FILESYSTEM"]))
            cap = s.get("capability", sid.split(".")[0])
            skill_recs.append({"skill_id": sid_full, "primary": s.get("primary", True),
                               "capability": cap})
            meta[sid] = {"capability": cap}
        wid = self.registry.register_worker(
            worker_id=profile.get("worker_id"), name=profile["name"],
            role_class=profile.get("role_class", "WORKER"),
            personality=profile.get("personality") or {},
            behavior_rules=profile.get("behavior_rules") or [],
            skills=skill_recs, tools=profile.get("tools") or [],
            permissions=profile.get("permissions") or {},
            memory_rules=profile.get("memory_rules") or {})
        self.registry.activate(wid)
        self.workers[wid] = StubWorker(self, wid, profile["name"], meta)
        return wid

    # ---- PM ----
    def get_pm(self, project_id: str) -> ProjectManager:
        if project_id in self.pms:
            return self.pms[project_id]
        pm_id = self.registry.create_pm(name=f"pm-{project_id}", project_id=project_id)
        pm = ProjectManager(pm_id, f"pm-{project_id}", project_id, self)
        self.pms[project_id] = pm
        return pm

    def pm_profile(self, project_id: str) -> dict:
        """Phase 4: full persistent PM record (knowledge, decisions, worker
        performance, lessons, conventions, task/group history)."""
        pm = self.get_pm(project_id)
        rec = self.registry.get_pm(pm.pm_id) or {}
        rec["lessons"] = self.registry.get_pm_lessons(pm.pm_id)
        return rec

    def pm_history(self, project_id: str, limit: int = 100) -> list[dict]:
        rows = db.query("SELECT task_id, request_text, state, created_ts, result_json "
                        "FROM tasks WHERE project_id=? ORDER BY created_ts DESC LIMIT ?",
                        (project_id, limit))
        return [{"taskId": r["task_id"], "request": r["request_text"], "state": r["state"],
                 "created_ts": r["created_ts"],
                 "result": json.loads(r["result_json"] or "null")} for r in rows]

    # ---- Phase 6: validation history & reports ----
    def qa_history(self, task_id: str) -> list[dict]:
        """Persisted QA verdicts for a task (QA-1 + every QA-2 cycle), oldest first."""
        rows = db.query("SELECT * FROM qa_verdicts WHERE task_id=? ORDER BY rowid",
                        (task_id,))
        return [dict(r) for r in rows]

    def task_validation_report(self, task_id: str) -> dict:
        """Structured validation report: cycles, failures, passed checks, verdict."""
        task = db.query_one("SELECT task_id, state, result_json FROM tasks WHERE task_id=?",
                            (task_id,))
        if task is None:
            raise KeyError(f"task {task_id} not found")
        verdicts = self.qa_history(task_id)
        cycles = sorted({v["cycle"] for v in verdicts if v["stage"] == "QA2"})
        return {
            "task_id": task_id,
            "state": task["state"],
            "qa1_checks": [v for v in verdicts if v["stage"] == "QA1"],
            "qa2_cycles": cycles,
            "failures": [v for v in verdicts if not v["passed"]],
            "passed_checks": [v for v in verdicts if v["passed"]],
            "result": json.loads(task["result_json"] or "null"),
        }

    # ---- task lifecycle ----
    def analyze_request(self, text: str, ctx: dict | None = None) -> dict:
        """Phase-2 MB preview without creating a task (UI / tests): the structured
        requirement + QA-1 verdict + classification + team plan + permission plan."""
        spec = self.mb.intelligence.analyze(text, dict(ctx or {}), None, self)
        v1 = self.mb.intelligence.qa1(spec, self)
        spec["complexity"] = self.mb.intelligence.classify(text, spec, self)
        team, gaps = self.mb.intelligence.select_workers(spec, self)
        spec["team_plan"] = team
        spec["capability_gaps"] = gaps
        spec["approvals_expected"] = self.mb.intelligence.plan_permissions(self, None, spec)
        return {"spec": spec, "qa1": v1, "complexity": spec["complexity"]}

    def submit(self, text: str, ctx: dict | None = None, answers: dict | None = None) -> Task:
        task = self.mb.accept_request(text, ctx=ctx, answers=answers)
        if task.state == TaskState.READY:
            return self.mb.run_ready_task(task)
        return task

    def clarify(self, task_id: str, answers: dict) -> Task:
        task = self.load_task(task_id)
        if task.state != TaskState.CLARIFYING:
            raise ValueError(f"task {task_id} is {task.state.value}, not CLARIFYING")
        ctx = (task.spec or {}).get("_ctx") or {}
        spec, v1 = self.mb._plan(task, task.request_text, ctx, answers)
        if not v1["pass"]:
            self.mb._t(task, TaskState.FAILED, "QA1_FAIL_FINAL", "QA")
            task.spec = spec
            self._save_task(task)
            return task
        self.mb._t(task, TaskState.ANALYZING, "CLARIFY_RESOLVED", "MB")
        self.mb._finalize_spec(task, task.request_text, spec, answers)
        self.mb._t(task, TaskState.READY, "QA1_PASS", "QA")
        self._save_task(task)
        return self.mb.run_ready_task(task)

    def cancel_requested(self, task_id: str) -> bool:
        return self._cancel_flags.get(task_id, False)

    def stop(self, task_id: str) -> None:
        """USER 'Stop' -> CANCELLED from any non-terminal state (Spec 01 §2.6)."""
        self._cancel_flags[task_id] = True
        task = self.load_task(task_id)
        if task.state not in TERMINAL:
            self.mb._t(task, TaskState.CANCELLED, "STOP", "USER")
            self._save_task(task)
            self._finalize(task)

    def resume(self, task_id: str) -> Task:
        task = self.load_task(task_id)
        if task.state not in (TaskState.READY, TaskState.PAUSED, TaskState.CANCELLED):
            return task
        self._cancel_flags.pop(task_id, None)
        cp = db.query_one("SELECT snapshot_json FROM checkpoints WHERE task_id=? ORDER BY created_ts DESC",
                          (task_id,))
        if cp is not None and task.state in (TaskState.PAUSED, TaskState.CANCELLED):
            snap = json.loads(cp["snapshot_json"])
            task.spec = snap.get("spec", task.spec)
            task.rework_count = snap.get("rework_count", 0)
        if task.state in (TaskState.PAUSED, TaskState.CANCELLED):
            self.mb._t(task, TaskState.READY, "RESUME", "MB")
        self._save_task(task)
        return self.mb.run_ready_task(task)

    def recover_pending(self) -> list[Task]:
        """Restart-safe resume: re-dispatch tasks that were not terminal at shutdown."""
        out = []
        rows = db.query("SELECT task_id, state FROM tasks WHERE state IN ('READY','PAUSED','RUNNING')")
        for r in rows:
            task = self.load_task(r["task_id"])
            if task.state == TaskState.RUNNING:
                self.mb._t(task, TaskState.READY, "RESTART", "MB")
                self._save_task(task)
            out.append(self.resume(r["task_id"]))
        return out

    def checkpoint(self, task: Task) -> str:
        cp_id = ids.new_id()
        snapshot = {"task_id": task.task_id, "state": task.state.value, "spec": task.spec,
                    "group_id": task.group_id, "rework_count": task.rework_count}
        db.execute("INSERT INTO checkpoints(cp_id,task_id,snapshot_json,created_ts) VALUES(?,?,?,?)",
                   (cp_id, task.task_id, json.dumps(snapshot), ids.now_iso()))
        rows = db.query("SELECT cp_id FROM checkpoints WHERE task_id=? ORDER BY created_ts DESC",
                        (task.task_id,))
        for r in rows[config.CHECKPOINT_KEEP:]:
            db.execute("DELETE FROM checkpoints WHERE cp_id=?", (r["cp_id"],))
        return cp_id

    # ---- persistence helpers ----
    def load_task(self, task_id: str) -> Task:
        row = db.query_one("SELECT * FROM tasks WHERE task_id=?", (task_id,))
        if row is None:
            raise KeyError(f"task {task_id} not found")
        task = Task(task_id=row["task_id"], request_text=row["request_text"],
                    project_id=row["project_id"], conversation_id=row["conversation_id"],
                    spec=json.loads(row["spec_json"] or "{}"),
                    state=TaskState(row["state"]), group_id=row["group_id"],
                    rework_count=row["rework_count"],
                    result=json.loads(row["result_json"]) if row["result_json"] else None,
                    created_ts=row["created_ts"], updated_ts=row["updated_ts"])
        n = db.query_one("SELECT COUNT(*) AS n FROM task_transitions WHERE task_id=?", (task_id,))["n"]
        task.sm.events = [{"seq": i} for i in range(1, n + 1)]
        return task

    def _save_task(self, task: Task) -> None:
        self.mb._save_task(task)

    def _make_group(self, task: Task, pm: ProjectManager) -> TaskGroup:
        # Phase 2: the Task Group contains ONLY the MB-selected team, not every worker.
        team = sorted(set((task.spec or {}).get("team_plan", {}).values()))
        if not team:
            team = list(self.workers.keys())
        group = TaskGroup(group_id=ids.new_id(), task_id=task.task_id, pm_id=pm.pm_id,
                          member_worker_ids=team,
                          shared_requirements_ref=f"task:{task.task_id}:spec")
        db.execute(
            "INSERT INTO task_groups(group_id,task_id,pm_id,member_ids_json,requirements_ref,artifacts_json,memory_scope_id,created_ts,closed_ts) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (group.group_id, task.task_id, pm.pm_id, json.dumps(group.member_worker_ids),
             group.shared_requirements_ref, json.dumps(group.artifacts_manifest),
             group.memory_scope_id, group.created_ts, None))
        return group

    def _finalize(self, task: Task, manifest: list[dict] | None = None) -> None:
        if task.group_id:
            # persist the in-memory artifact manifest (the group object may be gone
            # by the time resume()/stop() finalizes, so callers pass it explicitly)
            arts = manifest if manifest is not None else self._group_artifacts(task.group_id)
            db.execute("UPDATE task_groups SET artifacts_json=?, closed_ts=? WHERE group_id=?",
                       (json.dumps(arts), ids.now_iso(), task.group_id))
        self.bus.send(Envelope(type="EVENT", from_role="MB", from_id="mb", to_role="USER",
                               task_id=task.task_id,
                               payload={"kind": "task_final", "state": task.state.value}))

    def _group_artifacts(self, group_id: str) -> list[dict]:
        row = db.query_one("SELECT artifacts_json FROM task_groups WHERE group_id=?", (group_id,))
        return json.loads(row["artifacts_json"]) if row else []

    # ---- Phase 8: task-based model routing for a Task Group ----
    def route_group(self, task: Task, group: TaskGroup | None = None) -> list[dict]:
        """Route every planned component to a model, persist the decisions and
        audit them. Runs once per task execution before the PM starts workers."""
        spec = task.spec or {}
        team = spec.get("team_plan") or {}
        comps = spec.get("components") or []
        if not comps:
            return []
        routes = []
        for comp in comps:
            comp_id = comp.get("id", "")
            cap = comp.get("capability", "default")
            worker_id = team.get(comp_id) or ""
            if not worker_id:
                continue
            req = RouteRequest(
                task_id=task.task_id, worker_id=worker_id, capability=cap,
                complexity=spec.get("complexity", "normal"),
                privacy=spec.get("privacy", "public"),
                task_type=spec.get("output_type", "default"),
                model_hint=spec.get("model_hint", "auto"))
            decision = self.model_router.route(req)
            self.model_router.record(req, decision)
            routes.append({"component": comp_id, "worker": worker_id, **decision.to_dict()})
        return routes

    def timeline(self, task_id: str | None = None) -> list[dict]:
        return self.permissions.timeline(task_id)

    # ------------------------------------------------------------------ #
    # Phase 7: WorkDesk UI read models (pure queries, no execution)       #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _summary(result: dict | None) -> dict:
        result = result or {}
        artifacts = result.get("artifacts") or []
        return {
            "qa_cycles": result.get("qa_cycles") or 0,
            "qa_score": result.get("qa_score"),
            "rework_count": result.get("rework_count") or 0,
            "artifacts": [{"component": a.get("component"), "kind": a.get("kind"),
                           "path": a.get("path")} for a in artifacts],
        }

    def list_tasks(self, project_id: str | None = None, limit: int = 100,
                   conversation_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM tasks"
        params: list = []
        conds = []
        if project_id:
            conds.append("project_id=?")
            params.append(project_id)
        if conversation_id is not None:
            conds.append("conversation_id=?")
            params.append(conversation_id)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY priority ASC, created_ts DESC LIMIT ?"
        params.append(limit)
        out = []
        for r in db.query(sql, tuple(params)):
            item = {"task_id": r["task_id"], "request": r["request_text"],
                    "state": r["state"], "project_id": r["project_id"],
                    "conversation_id": r["conversation_id"],
                    "group_id": r["group_id"], "rework_count": r["rework_count"],
                    "priority": r["priority"] or 0,
                    "created_ts": r["created_ts"], "updated_ts": r["updated_ts"]}
            try:
                spec = json.loads(r["spec_json"] or "null") or {}
            except Exception:
                spec = {}
            item["team_routes"] = spec.get("team_routes") or []
            item["capability_gaps_detail"] = spec.get("capability_gaps_detail") or []
            item["spec"] = spec
            item.update(self._summary(json.loads(r["result_json"] or "null")))
            out.append(item)
        return out

    def reorder_tasks(self, conversation_id: str, task_ids: list[str]) -> dict:
        """Persist a user-chosen priority order for a chat's task list.
        Every id must belong to the conversation; unknown ids are rejected."""
        known = {r["task_id"] for r in db.query(
            "SELECT task_id FROM tasks WHERE conversation_id=?", (conversation_id,))}
        unknown = [t for t in task_ids if t not in known]
        if unknown:
            raise ValueError(f"task(s) not in conversation {conversation_id}: {unknown}")
        for idx, tid in enumerate(task_ids):
            db.execute("UPDATE tasks SET priority=?, updated_ts=? WHERE task_id=?",
                       (idx, ids.now_iso(), tid))
        return {"reordered": len(task_ids)}

    def task_detail(self, task_id: str) -> dict:
        """Full task read model for the WorkDesk UI: task + spec + group +
        state machine + QA history + validation report + audit timeline."""
        task = self.load_task(task_id)
        group = None
        if task.group_id:
            row = db.query_one("SELECT * FROM task_groups WHERE group_id=?", (task.group_id,))
            if row is not None:
                group = dict(row)
                group["artifacts"] = json.loads(group.pop("artifacts_json") or "[]")
                group["members"] = json.loads(group.pop("member_ids_json") or "[]")
        transitions = [dict(r) for r in db.query(
            "SELECT * FROM task_transitions WHERE task_id=? ORDER BY seq", (task_id,))]
        return {
            "task": {"task_id": task.task_id, "request": task.request_text,
                     "state": task.state.value, "project_id": task.project_id,
                     "conversation_id": task.conversation_id,
                     "group_id": task.group_id, "rework_count": task.rework_count,
                     "created_ts": task.created_ts, "updated_ts": task.updated_ts,
                     "spec": task.spec,
                     "result": self._summary(task.result)},
            "group": group,
            "transitions": transitions,
            "timeline": self.permissions.timeline(task_id),
            "qa_history": self.qa_history(task_id),
            "validation": self.task_validation_report(task_id),
            "model_routes": self.model_router.for_task(task_id),
        }

    def list_pms(self) -> list[dict]:
        out = []
        for r in db.query("SELECT * FROM pms ORDER BY updated_ts DESC"):
            rec = dict(r)
            for k in ("knowledge_json", "decisions_json", "lessons_json", "conventions_json",
                      "worker_performance_json", "task_history_json", "group_history_json"):
                if k in rec:
                    rec[k.removesuffix("_json")] = json.loads(rec.pop(k) or "[]")
            rec["lessons"] = self.registry.get_pm_lessons(rec["pm_id"])
            rec["task_count"] = db.query_one(
                "SELECT COUNT(*) AS n FROM tasks WHERE project_id=?", (rec["project_id"],))["n"]
            out.append(rec)
        return out

    def virtual_office(self, conversation_id: str | None = None) -> dict:
        """Live snapshot for the Virtual Office view: worker status + task-state
        distribution + pending approvals + recent activity. When
        `conversation_id` is given, only that chat session's tasks (and the
        workers those tasks actually used) are shown — each chat has its own
        worker roster and flow (user requirement, P7.5)."""
        workers = []
        if conversation_id is not None:
            trows = db.query("SELECT DISTINCT spec_json FROM tasks WHERE conversation_id=?",
                             (conversation_id,))
            used_ids: set[str] = set()
            for r in trows:
                spec = json.loads(r["spec_json"] or "{}")
                used_ids.update((spec.get("team_plan") or {}).values())
            pool = [self.worker_catalog_row(w) for w in used_ids if w in self.workers]
        else:
            pool = self.worker_catalog()
        for w in pool:
            skills = w.get("skills") or []
            workers.append({
                "id": w["worker_id"], "name": w["name"], "status": w["status"],
                "skills": [s.get("skill_id") or s.get("name") for s in skills],
                "capabilities": [s.get("capability") for s in skills],
                "tools": w.get("tools") or [],
                "permissions": w.get("permissions") or {},
                "stats": {"times_triggered": w["times_triggered"],
                          "tasks_completed": w["tasks_completed"],
                          "qa_passed": w["qa_passed"], "qa_failed": w["qa_failed"],
                          "failure_rate": round(w["failure_rate"] or 0.0, 3),
                          "qa_pass_rate": round(w.get("qa_pass_rate") or 0.0, 3)},
            })
        task_states: dict[str, int] = {}
        if conversation_id is not None:
            for r in db.query("SELECT state, COUNT(*) AS n FROM tasks WHERE conversation_id=? GROUP BY state",
                              (conversation_id,)):
                task_states[r["state"]] = r["n"]
        else:
            for r in db.query("SELECT state, COUNT(*) AS n FROM tasks GROUP BY state"):
                task_states[r["state"]] = r["n"]
        pending = len(self.approvals_pending(conversation_id))
        recent = self.permissions.timeline()[-12:]
        if conversation_id is not None:
            recent = [r for r in recent if r["task_id"] in self._conversation_task_ids(conversation_id)]
        return {"workers": workers, "task_states": task_states, "pending_approvals": pending,
                "recent_activity": [{"ts": r["ts"], "actor": r["actor_id"] or r["actor_role"],
                                     "role": r["actor_role"], "action": r["action"],
                                     "task_id": r["task_id"], "reason": r["reason"]}
                                    for r in recent]}

    def _conversation_task_ids(self, conversation_id: str) -> set[str]:
        return {r["task_id"] for r in
                db.query("SELECT task_id FROM tasks WHERE conversation_id=?", (conversation_id,))}

    def approvals_pending(self, conversation_id: str | None = None) -> list[dict]:
        """PENDING approvals, optionally scoped to one chat session (by joining
        the approval's task back to the conversation)."""
        if conversation_id is not None:
            rows = db.query(
                "SELECT a.approval_id, a.request_id, a.requester_id, a.action, a.resource, "
                "a.tool, a.level, a.task_id FROM approvals a "
                "JOIN tasks t ON t.task_id = a.task_id "
                "WHERE a.status='PENDING' AND t.conversation_id=? ORDER BY a.approval_id",
                (conversation_id,))
        else:
            rows = db.query(
                "SELECT approval_id, request_id, requester_id, action, resource, tool, level, task_id "
                "FROM approvals WHERE status='PENDING' ORDER BY approval_id")
        return [{"requestId": r["approval_id"], "workerId": r["requester_id"], "tool": r["tool"],
                 "action": r["action"], "params": {"resource": r["resource"]},
                 "level": r["level"], "taskId": r["task_id"]}
                for r in rows]

    def worker_catalog_row(self, worker_id: str) -> dict | None:
        if worker_id not in self.workers:
            return None
        return self.registry.get_worker(worker_id)

    # ---- Phase 9: learning read models ----
    def learning_stats(self) -> dict:
        return self.learning.stats()

    def learning_list(self, scope: str | None = None, limit: int = 100) -> list[dict]:
        return self.learning.list_all(scope=scope, limit=limit)

    def learning_hints(self, capability: str) -> list[dict]:
        return self.learning.hints_for(capability)

    def settings_snapshot(self) -> dict:
        counts = {r["t"]: r["n"] for r in db.query(
            "SELECT 'tasks' AS t, COUNT(*) AS n FROM tasks "
            "UNION ALL SELECT 'pms', COUNT(*) FROM pms "
            "UNION ALL SELECT 'workers', COUNT(*) FROM workers "
            "UNION ALL SELECT 'skills', COUNT(*) FROM skills "
            "UNION ALL SELECT 'lessons', COUNT(*) FROM lessons "
            "UNION ALL SELECT 'qa_verdicts', COUNT(*) FROM qa_verdicts")}
        return {
            "max_rework_cycles": config.MAX_REWORK_CYCLES,
            "checkpoint_keep": config.CHECKPOINT_KEEP,
            "auto_approve": self.auto_approve,
            "db_path": str(self.db_path) if self.db_path else "(in-memory)",
            "project_dir": str(self.project_dir),
            "lesson_promote_min_evidence": config.LESSON_PROMOTE_MIN_EVIDENCE,
            "counts": counts,
        }
