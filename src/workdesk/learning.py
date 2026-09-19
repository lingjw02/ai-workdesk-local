"""Phase 9 — learning system (Spec 01 §8, Phase 9).

Experience -> Lesson candidate -> Evidence / Confidence -> Stored lesson
-> Applied to future tasks, with strict memory boundaries.

Three scopes mirror the memory architecture:
  * pm     — one persistent lesson per (PM, key); the PM's institutional memory
  * worker — one lesson per (worker, key); the worker's own experience
  * global — one lesson per (MB, key) aggregated across projects; learned by
             the Main Brain from global history

The pipeline is evidence-gated (never self-rewriting): a candidate starts at
LOW with one ref, corroborating cases raise evidence_count and confidence
(MEDIUM at >=1 extra, HIGH at LESSON_PROMOTE_MIN_EVIDENCE), and only HIGH
lessons become `stored` and eligible to be applied as QA hints. Every
application is counted (applied_count) and audit-logged as `lesson_applied`,
so the system learns that the lesson was useful — or not.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from . import config, db, ids


def _keyed_cap(capability: str) -> str:
    """Lesson key = capability, matching the Phase-4 PM lesson convention so
    existing PM lessons upgrade in place rather than forking."""
    return capability


class LearningSystem:
    def __init__(self, registry, audit: Callable | None = None):
        self.registry = registry
        self.audit = audit

    # ---------------- the pipeline: task -> lesson candidates ----------------
    def learn_from_task(self, *, task, outcome: str, qa_cycles: int,
                        rework_count: int, worker_ids: list[str],
                        pm_id: str, team_plan: dict | None = None,
                        failed_components: list[str] | None = None) -> list[dict]:
        """Run all three scopes after a terminal task state.

        Only tasks that needed QA rework or outright failed produce lessons —
        success is remembered as PM conventions, not as a lesson. When
        `failed_components` is given (the QA-2 failure set), only those
        capabilities learn; otherwise every reworked component learns. Each
        worker learns only the capability it actually executed (team_plan maps
        component id -> worker id; without a plan every participating worker
        learns every reworked capability).
        """
        spec = task.spec or {}
        comps = spec.get("components") or []
        if not comps:
            return []
        plan = team_plan or {}
        learned: list[dict] = []
        for comp in comps:
            cap = comp.get("capability") or "default"
            if failed_components is not None and comp.get("id") not in failed_components:
                continue
            content = self._lesson_text(outcome, qa_cycles, rework_count, cap)
            if not content:
                continue
            ref = {"task_id": getattr(task, "task_id", "unit"), "outcome": outcome}
            # 1) PM lesson (project-level institutional memory)
            learned.append(self._upsert("pm", pm_id, _keyed_cap(cap), content,
                                        [task.task_id], outcome))
            # 2) worker lessons (each worker learns only its own components)
            comp_workers = []
            if plan:
                cid = comp.get("id")
                wid = plan.get(cid)
                if wid:
                    comp_workers = [wid]
            for wid in comp_workers or worker_ids:
                if not wid:
                    continue
                learned.append(self._upsert("worker", wid, _keyed_cap(cap), content,
                                            [task.task_id], outcome))
            # 3) global lesson (MB aggregates across projects by capability)
            learned.append(self._upsert("global", "MB", _keyed_cap(cap), content,
                                        [task.task_id], outcome))
        return [l for l in learned if l]

    @staticmethod
    def _lesson_text(outcome: str, qa_cycles: int, rework_count: int,
                     cap: str) -> str:
        if outcome == "FAILED":
            return (f"capability '{cap}' repeatedly failed QA-2 and hit the "
                    f"retry limit ({rework_count} cycles); check its artifact "
                    f"against the criteria before assigning it again")
        if qa_cycles > 0:
            return (f"capability '{cap}' needed {qa_cycles} QA cycle(s); its "
                    f"first artifact often misses required criteria (e.g. Summary)")
        return ""

    # ---------------- upsert (evidence-gated) ----------------
    def _upsert(self, scope: str, owner_id: str, key: str, content: str,
                refs: list[str], outcome: str) -> dict | None:
        existing = self._get(scope, owner_id, key)
        if existing is not None:
            count = existing["evidence_count"] + 1
            conf = "HIGH" if count >= config.LESSON_PROMOTE_MIN_EVIDENCE else (
                "MEDIUM" if count >= 2 else "LOW")
            merged_refs = existing["refs"] + [r for r in refs if r not in existing["refs"]]
            db.execute(
                "UPDATE lessons SET content=?, evidence_count=?, confidence=?, "
                "refs_json=?, status=?, updated_ts=? WHERE lesson_id=?",
                (content, count, conf, json.dumps(merged_refs),
                 "stored" if conf == "HIGH" else "candidate",
                 ids.now_iso(), existing["lesson_id"]))
            lesson_id = existing["lesson_id"]
        else:
            lesson_id = ids.new_id()
            db.execute(
                "INSERT INTO lessons(lesson_id,pm_id,lesson_key,content,evidence_count,"
                "confidence,refs_json,status,created_ts,updated_ts,scope,owner_id,"
                "applied_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (lesson_id, owner_id, key, content, 1, "LOW",
                 json.dumps(refs), "candidate", ids.now_iso(), ids.now_iso(),
                 scope, owner_id))
        if self.audit is not None:
            try:
                self.audit("MB" if scope == "global" else scope.upper(),
                           owner_id, "learned",
                           reason=f"scope={scope} key={key} outcome={outcome}",
                           task_id=refs[0] if refs else None)
            except Exception:  # noqa: BLE001 - audit never breaks learning
                pass
        return self._get(scope, owner_id, key)

    def _get(self, scope: str, owner_id: str, key: str) -> dict | None:
        row = db.query_one(
            "SELECT * FROM lessons WHERE scope=? AND owner_id=? AND lesson_key=? "
            "ORDER BY updated_ts DESC LIMIT 1", (scope, owner_id, key))
        if row is None:
            return None
        d = dict(row)
        d["refs"] = json.loads(d.pop("refs_json") or "[]")
        return d

    # ---------------- application: hints + applied bookkeeping ----------------
    def hints_for(self, capability: str, owner_scopes: tuple[str, ...] = ("global", "pm")) -> list[dict]:
        """HIGH-confidence stored lessons for a capability (global first, then
        PM-scope, since a PM may not exist yet in unit flows)."""
        key = _keyed_cap(capability)
        marks = ",".join("?" * len(owner_scopes))
        rows = db.query(
            f"SELECT * FROM lessons WHERE lesson_key=? AND confidence='HIGH' "
            f"AND scope IN ({marks}) AND status='stored' "
            f"ORDER BY evidence_count DESC, updated_ts DESC",
            (key, *owner_scopes))
        out = []
        for r in rows:
            d = dict(r)
            d["refs"] = json.loads(d.pop("refs_json") or "[]")
            out.append(d)
        return out

    def record_applied(self, lesson_id: str) -> None:
        db.execute(
            "UPDATE lessons SET applied_count=applied_count+1, last_applied_ts=?, "
            "status='applied' WHERE lesson_id=?",
            (ids.now_iso(), lesson_id))

    # ---------------- read models ----------------
    def stats(self) -> dict:
        by_scope: dict[str, int] = {}
        by_conf: dict[str, int] = {}
        for r in db.query("SELECT scope, confidence FROM lessons"):
            by_scope[r["scope"]] = by_scope.get(r["scope"], 0) + 1
            by_conf[r["confidence"]] = by_conf.get(r["confidence"], 0) + 1
        applied = db.query_one(
            "SELECT COALESCE(SUM(applied_count),0) AS n FROM lessons")
        return {"total": sum(by_scope.values()), "by_scope": by_scope,
                "by_confidence": by_conf,
                "applied": int(applied["n"]) if applied else 0}

    def list_all(self, scope: str | None = None, limit: int = 100) -> list[dict]:
        sql = ("SELECT lesson_id, pm_id, lesson_key, content, evidence_count, "
               "confidence, refs_json, status, scope, owner_id, applied_count, "
               "last_applied_ts, created_ts, updated_ts FROM lessons")
        params: list = []
        if scope:
            sql += " WHERE scope=?"
            params.append(scope)
        sql += " ORDER BY updated_ts DESC LIMIT ?"
        params.append(limit)
        out = []
        for r in db.query(sql, tuple(params)):
            d = dict(r)
            d["refs"] = json.loads(d.pop("refs_json") or "[]")
            out.append(d)
        return out

    def for_owner(self, scope: str, owner_id: str, limit: int = 50) -> list[dict]:
        rows = db.query(
            "SELECT * FROM lessons WHERE scope=? AND owner_id=? "
            "ORDER BY updated_ts DESC LIMIT ?", (scope, owner_id, limit))
        out = []
        for r in rows:
            d = dict(r)
            d["refs"] = json.loads(d.pop("refs_json") or "[]")
            out.append(d)
        return out
