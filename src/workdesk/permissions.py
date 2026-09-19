"""Permission manager + audit log (Spec 03 §4.6).

Four levels (AUTO / NOTIFY / ASK / EXPLICIT), policy tuples with most-specific-match
resolution and deny-by-default, approval records, and the append-only audit log
(decision/event metadata only -- never chain-of-thought).
"""
import fnmatch
import json

from . import db, ids
from .envelope import Envelope

LEVELS = ("AUTO", "NOTIFY", "ASK", "EXPLICIT")


class PermissionManager:
    def __init__(self, database, bus=None, auto_approve: bool = False):
        self.db = database
        self.bus = bus
        self.auto_approve = auto_approve
        self._seed_defaults()

    # ---- policies ----
    def _seed_defaults(self) -> None:
        # (actor_role, action, resource_pattern, tool, condition, level, scope)
        defaults = [
            ("*", "read",    "project:*",              "*", "", "AUTO",     "project"),
            ("*", "create",  "project:*",              "*", "", "NOTIFY",   "project"),
            ("*", "modify",  "project:config:*",       "*", "", "ASK",      "project"),
            ("*", "delete",  "project:important:*",    "*", "", "EXPLICIT", "project"),
            ("*", "delete",  "*",                      "*", "", "EXPLICIT", "system"),
            ("*", "install", "*",                      "*", "", "EXPLICIT", "system"),
            ("WORKER", "*",  "system:*",               "*", "", "BLOCKED",  "system"),
        ]
        for d in defaults:
            self.add_policy(*d)

    def add_policy(self, actor_role: str, action: str, resource_pattern: str,
                   tool: str, condition: str, level: str, scope: str) -> int:
        return db.execute(
            "INSERT INTO policies(actor_role,action,resource_pattern,tool,condition,level,scope) VALUES(?,?,?,?,?,?,?)",
            (actor_role, action, resource_pattern, tool, condition, level, scope))

    def resolve(self, actor_role: str, action: str, resource: str, tool: str) -> tuple[str, dict | None]:
        """Most specific match wins; deny by default (Spec 03 §4.6)."""
        best, best_score = None, -1
        for r in db.query("SELECT * FROM policies"):
            if r["actor_role"] not in ("*", actor_role):
                continue
            if r["action"] not in ("*", action):
                continue
            if r["tool"] not in ("*", tool):
                continue
            if not fnmatch.fnmatch(resource, r["resource_pattern"]):
                continue
            score = (r["actor_role"] != "*") + (r["action"] != "*") + (r["tool"] != "*") \
                + (len(r["resource_pattern"]) if r["resource_pattern"] != "*" else 0)
            if score > best_score:
                best, best_score = r, score
        if best is None:
            return "DENY", None
        if best["level"] == "BLOCKED":
            return "DENY", dict(best)
        return best["level"], dict(best)

    def check(self, actor_role: str, action: str, resource: str, tool: str) -> tuple[bool, str]:
        level, policy = self.resolve(actor_role, action, resource, tool)
        allowed = level in ("AUTO", "NOTIFY")
        return allowed, level

    # ---- approvals ----
    def require_approval(self, requester_role: str, requester_id: str, action: str,
                         resource: str, tool: str, task_id: str | None = None) -> tuple[str | None, str]:
        level, policy = self.resolve(requester_role, action, resource, tool)
        if level not in ("ASK", "EXPLICIT"):
            return None, level
        approval_id = ids.new_id()
        request_id = ids.new_id()
        status = "APPROVED" if self.auto_approve else "PENDING"
        db.execute(
            "INSERT INTO approvals(approval_id,request_id,requester_role,requester_id,action,resource,tool,level,status,decision_ts,decision_context,task_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (approval_id, request_id, requester_role, requester_id, action, resource, tool,
             level, status, ids.now_iso() if status == "APPROVED" else None,
             "auto-approve (demo)" if status == "APPROVED" else None, task_id),
        )
        if self.bus is not None:
            self.bus.send(Envelope(type="APPROVAL_REQUEST", from_role=requester_role, from_id=requester_id,
                                   to_role="USER", task_id=task_id,
                                   payload={"approval_id": approval_id, "action": action, "resource": resource, "level": level}))
        return approval_id, level

    def decide(self, approval_id: str, decision: str, context: str = "") -> None:
        if decision not in ("APPROVED", "DENIED"):
            raise ValueError(f"bad decision {decision}")
        db.execute("UPDATE approvals SET status=?, decision_ts=?, decision_context=? WHERE approval_id=?",
                   (decision, ids.now_iso(), context, approval_id))
        if self.bus is not None:
            row = db.query_one("SELECT * FROM approvals WHERE approval_id=?", (approval_id,))
            if row is not None:
                self.bus.send(Envelope(type="APPROVAL_RESPONSE", from_role="USER", from_id="user",
                                       to_role=row["requester_role"], to_id=row["requester_id"],
                                       payload={"approval_id": approval_id, "decision": decision}))

    # ---- audit log ----
    def audit(self, actor_role: str, actor_id: str, action: str, *, tool: str | None = None,
              files_changed: list | None = None, reason: str | None = None,
              qa_refs: list | None = None, rework_refs: list | None = None,
              task_id: str | None = None) -> int:
        return db.execute(
            "INSERT INTO audit_events(ts,task_id,actor_role,actor_id,action,tool,files_changed_json,reason,qa_refs_json,rework_refs_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (ids.now_iso(), task_id, actor_role, actor_id, action, tool,
             json.dumps(files_changed or []), reason, json.dumps(qa_refs or []),
             json.dumps(rework_refs or [])))

    def timeline(self, task_id: str | None = None) -> list[dict]:
        if task_id:
            rows = db.query("SELECT * FROM audit_events WHERE task_id=? ORDER BY seq", (task_id,))
        else:
            rows = db.query("SELECT * FROM audit_events ORDER BY seq")
        return [dict(r) for r in rows]
