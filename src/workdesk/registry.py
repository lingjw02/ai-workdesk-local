"""Worker / PM / Skill registry (Spec 04 §5.1-5.7).

Persistent worker profiles with lifecycle (REGISTERED -> AVAILABLE -> ACTIVE ->
SUSPENDED -> RETIRED), capability lookup, EWMA performance statistics, PM records,
and the skill catalogue. Upgrade keeps statistics: records are only ever updated in place.
"""
import json

from . import db, ids

WORKER_LIFECYCLE = ("REGISTERED", "AVAILABLE", "ACTIVE", "SUSPENDED", "RETIRED")
EWMA_ALPHA = 0.2


class Registry:
    def __init__(self, database, bus=None):
        self.db = database
        self.bus = bus

    # ---------------- workers ----------------
    def register_worker(self, *, worker_id: str | None = None, name: str,
                        role_class: str = "WORKER", personality: dict | None = None,
                        behavior_rules: list | None = None, skills: list | None = None,
                        tools: list | None = None, permissions: dict | None = None,
                        memory_rules: dict | None = None) -> str:
        worker_id = worker_id or ids.new_id()
        exists = db.query_one("SELECT worker_id FROM workers WHERE worker_id=?", (worker_id,))
        if exists is not None:
            # Idempotent upgrade: keep statistics, refresh profile fields in place.
            db.execute(
                "UPDATE workers SET name=?, role_class=?, personality_json=?, behavior_rules_json=?, "
                "skills_json=?, tools_json=?, permissions_json=?, memory_rules_json=?, updated_ts=? "
                "WHERE worker_id=?",
                (name, role_class, json.dumps(personality or {}), json.dumps(behavior_rules or []),
                 json.dumps(skills or []), json.dumps(tools or []), json.dumps(permissions or {}),
                 json.dumps(memory_rules or {}), ids.now_iso(), worker_id))
            return worker_id
        db.execute(
            "INSERT INTO workers(worker_id,name,role_class,personality_json,behavior_rules_json,skills_json,"
            "tools_json,permissions_json,memory_rules_json,status,times_triggered,tasks_completed,qa_passed,qa_failed,"
            "failure_rate,avg_execution_time_ms,created_ts,updated_ts) VALUES(?,?,?,?,?,?,?,?,?,?,0,0,0,0,0.0,0.0,?,?)",
            (worker_id, name, role_class, json.dumps(personality or {}), json.dumps(behavior_rules or []),
             json.dumps(skills or []), json.dumps(tools or []), json.dumps(permissions or {}),
             json.dumps(memory_rules or {}), "REGISTERED", ids.now_iso(), ids.now_iso()))
        return worker_id

    def set_status(self, worker_id: str, status: str) -> None:
        if status not in WORKER_LIFECYCLE:
            raise ValueError(f"bad lifecycle state {status}")
        db.execute("UPDATE workers SET status=?, updated_ts=? WHERE worker_id=?",
                   (status, ids.now_iso(), worker_id))

    def activate(self, worker_id: str) -> None:
        self.set_status(worker_id, "AVAILABLE")

    def suspend(self, worker_id: str) -> None:
        self.set_status(worker_id, "SUSPENDED")

    def retire(self, worker_id: str) -> None:
        self.set_status(worker_id, "RETIRED")

    def get_worker(self, worker_id: str) -> dict | None:
        row = db.query_one("SELECT * FROM workers WHERE worker_id=?", (worker_id,))
        return self._worker_dict(row) if row is not None else None

    def find_workers(self, capability_tags: list[str],
                     statuses: tuple[str, ...] = ("AVAILABLE", "ACTIVE")) -> list[dict]:
        out = []
        for row in db.query("SELECT * FROM workers"):
            if row["status"] not in statuses:
                continue
            skills = json.loads(row["skills_json"] or "[]")
            caps = {s.get("capability", "") for s in skills}
            if any(tag in caps for tag in capability_tags):
                out.append(self._worker_dict(row))
        return out

    @staticmethod
    def _worker_dict(row) -> dict:
        d = dict(row)
        for k in ("personality_json", "behavior_rules_json", "skills_json", "tools_json",
                  "permissions_json", "memory_rules_json"):
            if k in d:
                d[k.removesuffix("_json")] = json.loads(d.pop(k) or "{}")
        total = d.get("qa_passed", 0) + d.get("qa_failed", 0)
        d["qa_pass_rate"] = d["qa_passed"] / total if total else 0.0
        return d

    def bump_triggered(self, worker_id: str) -> None:
        db.execute("UPDATE workers SET times_triggered=times_triggered+1 WHERE worker_id=?", (worker_id,))

    def record_result(self, worker_id: str, task_id: str, passed: bool, exec_ms: float) -> None:
        row = db.query_one("SELECT * FROM workers WHERE worker_id=?", (worker_id,))
        if row is None:
            return
        a = EWMA_ALPHA
        tasks = row["tasks_completed"] + 1
        qa_passed = row["qa_passed"] + (1 if passed else 0)
        qa_failed = row["qa_failed"] + (0 if passed else 1)
        rate = qa_passed / (qa_passed + qa_failed) if (qa_passed + qa_failed) else 0.0
        failure_rate = (1 - a) * row["failure_rate"] + a * (0.0 if passed else 1.0)
        avg_ms = (1 - a) * row["avg_execution_time_ms"] + a * exec_ms
        db.execute(
            "UPDATE workers SET tasks_completed=?,qa_passed=?,qa_failed=?,failure_rate=?,avg_execution_time_ms=?,updated_ts=? "
            "WHERE worker_id=?",
            (tasks, qa_passed, qa_failed, failure_rate, avg_ms, ids.now_iso(), worker_id))

    # ---------------- PMs ----------------
    def create_pm(self, name: str, project_id: str) -> str:
        pm_id = ids.new_id()
        db.execute(
            "INSERT INTO pms(pm_id,name,project_id,status,knowledge_json,decisions_json,lessons_json,"
            "conventions_json,worker_performance_json,task_history_json,group_history_json,"
            "schema_version,created_ts,updated_ts) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?)",
            (pm_id, name, project_id, "AVAILABLE", "[]", "[]", "[]", "[]", "{}", "[]", "[]",
             ids.now_iso(), ids.now_iso()))
        return pm_id

    def update_pm(self, pm_id: str, *, knowledge: list | None = None,
                  decisions: list | None = None, lessons: list | None = None,
                  conventions: list | None = None, worker_performance: dict | None = None,
                  task_history: list | None = None, group_history: list | None = None) -> None:
        """Phase 4: in-place, idempotent PM record updates (history/performance append)."""
        row = db.query_one("SELECT * FROM pms WHERE pm_id=?", (pm_id,))
        if row is None:
            raise KeyError(f"pm {pm_id} not found")
        _j = json.loads
        cur = {
            "knowledge": _j(row["knowledge_json"] or "[]"),
            "decisions": _j(row["decisions_json"] or "[]"),
            "lessons": _j(row["lessons_json"] or "[]"),
            "conventions": _j(row["conventions_json"] or "[]"),
            "worker_performance": _j(row["worker_performance_json"] or "{}"),
            "task_history": _j(row["task_history_json"] or "[]"),
            "group_history": _j(row["group_history_json"] or "[]"),
        }

        def _append(seq: list, items: list) -> list:
            for it in items:
                if it not in seq:
                    seq.append(it)
            return seq

        if knowledge is not None:
            cur["knowledge"] = _append(cur["knowledge"], knowledge)
        if decisions is not None:
            cur["decisions"] = _append(cur["decisions"], decisions)
        if lessons is not None:
            cur["lessons"] = _append(cur["lessons"], lessons)
        if conventions is not None:
            cur["conventions"] = _append(cur["conventions"], conventions)
        if worker_performance is not None:
            cur["worker_performance"].update(worker_performance)
        if task_history is not None:
            cur["task_history"] = _append(cur["task_history"], task_history)
        if group_history is not None:
            cur["group_history"] = _append(cur["group_history"], group_history)
        db.execute(
            "UPDATE pms SET knowledge_json=?, decisions_json=?, lessons_json=?, conventions_json=?, "
            "worker_performance_json=?, task_history_json=?, group_history_json=?, updated_ts=? "
            "WHERE pm_id=?",
            (json.dumps(cur["knowledge"]), json.dumps(cur["decisions"]), json.dumps(cur["lessons"]),
             json.dumps(cur["conventions"]), json.dumps(cur["worker_performance"]),
             json.dumps(cur["task_history"]), json.dumps(cur["group_history"]), ids.now_iso(), pm_id))

    def get_pm(self, pm_id: str) -> dict | None:
        row = db.query_one("SELECT * FROM pms WHERE pm_id=?", (pm_id,))
        if row is None:
            return None
        d = dict(row)
        for k in ("knowledge_json", "decisions_json", "lessons_json", "conventions_json",
                  "worker_performance_json", "task_history_json", "group_history_json"):
            if k in d:
                d[k.removesuffix("_json")] = json.loads(d.pop(k) or ("{}" if "performance" in k else "[]"))
        return d

    # ---------------- PM lessons (Spec 03 §4.5 evidence-gated learning) ----------------
    def add_pm_lesson(self, pm_id: str, lesson_key: str, content: str, evidence_count: int,
                      confidence: str, refs: list | None = None) -> str:
        """Store one lesson per (pm, key); a later finding with the same key upgrades
        the SAME record (evidence count / confidence / status) instead of inserting."""
        status = "stored" if confidence == "HIGH" else "candidate"
        refs_json = json.dumps(refs or [])
        existing = db.query_one("SELECT lesson_id FROM lessons WHERE pm_id=? AND lesson_key=?",
                                (pm_id, lesson_key))
        if existing is not None:
            db.execute(
                "UPDATE lessons SET content=?, evidence_count=?, confidence=?, refs_json=?, "
                "status=?, updated_ts=? WHERE lesson_id=?",
                (content, evidence_count, confidence, refs_json, status, ids.now_iso(),
                 existing["lesson_id"]))
            return existing["lesson_id"]
        lesson_id = ids.new_id()
        db.execute(
            "INSERT INTO lessons(lesson_id,pm_id,lesson_key,content,evidence_count,confidence,"
            "refs_json,status,created_ts,updated_ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (lesson_id, pm_id, lesson_key, content, evidence_count, confidence,
             refs_json, status, ids.now_iso(), ids.now_iso()))
        self.update_pm(pm_id, lessons=[lesson_id])
        return lesson_id

    def get_pm_lesson_key(self, pm_id: str, lesson_key: str) -> dict | None:
        row = db.query_one("SELECT * FROM lessons WHERE pm_id=? AND lesson_key=? "
                           "ORDER BY updated_ts DESC LIMIT 1", (pm_id, lesson_key))
        if row is None:
            return None
        d = dict(row)
        d["refs"] = json.loads(d.pop("refs_json") or "[]")
        return d

    def get_pm_lessons(self, pm_id: str) -> list[dict]:
        out = []
        for row in db.query("SELECT * FROM lessons WHERE pm_id=? ORDER BY updated_ts DESC",
                            (pm_id,)):
            d = dict(row)
            d["refs"] = json.loads(d.pop("refs_json") or "[]")
            out.append(d)
        return out

    # ---------------- skills ----------------
    def register_skill(self, *, name: str, version: str = "0.1.0", skill_type: str = "BUILTIN",
                       entry_point: str = "", params: dict | None = None,
                       tools_required: list | None = None,
                       permissions_required: list | None = None) -> str:
        skill_id = ids.new_id()
        db.execute(
            "INSERT INTO skills(skill_id,name,version,type,entry_point,params_json,tools_required_json,"
            "permissions_required_json,enabled,installed_ts) VALUES(?,?,?,?,?,?,?,?,1,?)",
            (skill_id, name, version, skill_type, entry_point, json.dumps(params or {}),
             json.dumps(tools_required or []), json.dumps(permissions_required or []), ids.now_iso()))
        return skill_id
