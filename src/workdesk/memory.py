"""Memory manager (Spec 03 §4.1-4.5).

Four layers (GLOBAL / PROJECT / GROUP / WORKER), access matrix enforcement,
scope grants (cross-project NEVER automatic), and the evidence-gated lesson pipeline.
"""
from typing import Any

from . import db, ids
from .envelope import Envelope

LAYERS = ("GLOBAL", "PROJECT", "GROUP", "WORKER")
CONFIDENCE = ("HIGH", "MEDIUM", "LOW")


def _granted(ctx: dict, layer: str, scope_id: str) -> bool:
    return bool((ctx.get("grants") or {}).get(f"{layer}:{scope_id}"))


def can_access(actor_role: str, action: str, layer: str, scope_id: str,
               ctx: dict | None = None) -> tuple[bool, str]:
    """Access matrix, Spec 03 §4.3. `ctx` carries the actor's own scopes + grants."""
    ctx = ctx or {}
    if action not in ("read", "write"):
        return False, "unknown action"
    if layer not in LAYERS:
        return False, "unknown layer"
    if actor_role == "USER":
        return (action == "read") or layer == "GLOBAL", "user sees UI layer"
    if actor_role == "MB":
        if layer == "GLOBAL":
            return True, "MB owns global memory"
        if action == "read":
            if layer == "WORKER":
                return True, "MB reads worker stats"
            return _granted(ctx, layer, scope_id), "MB needs explicit grant"
        return _granted(ctx, layer, scope_id), "MB write requires explicit grant"
    if actor_role == "PM":
        if layer == "PROJECT" and scope_id == ctx.get("own_project_id"):
            return True, "PM owns this project memory"
        if layer == "GROUP" and scope_id == ctx.get("own_group_id"):
            return True, "PM current group"
        if layer == "WORKER" and action == "read":
            return True, "PM reads authorized worker performance"
        return False, "PM scope denied"
    if actor_role == "WORKER":
        if layer == "GROUP" and scope_id == ctx.get("own_group_id"):
            return True, "worker current group"
        if layer == "WORKER" and scope_id == ctx.get("own_worker_id"):
            return True, "worker own profile"
        return False, "worker scope denied"
    if actor_role == "QA":
        if action == "read" and layer in ("PROJECT", "GROUP"):
            if scope_id in (ctx.get("own_project_id"), ctx.get("own_group_id")):
                return True, "QA reads task context"
        return False, "QA scope denied"
    return False, "unknown actor"


class MemoryManager:
    def __init__(self, database, bus=None):
        self.db = database
        self.bus = bus

    def write(self, actor_role: str, actor_id: str, layer: str, scope_id: str,
              mem_type: str, content: str, *, confidence: str = "MEDIUM",
              evidence_refs: list | None = None, tags: list | None = None,
              ctx: dict | None = None, task_id: str | None = None,
              immutable: bool = False) -> str:
        ok, why = can_access(actor_role, "write", layer, scope_id, ctx)
        if not ok:
            raise PermissionError(f"memory write denied: {why}")
        mem_id = ids.new_id()
        db.execute(
            "INSERT INTO memory_records(mem_id,layer,scope_id,type,content,source_role,source_id,ts,confidence,evidence_refs_json,ttl,access_scope,immutable,tags_json) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (mem_id, layer, scope_id, mem_type, content, actor_role, actor_id, ids.now_iso(),
             confidence, __import__("json").dumps(evidence_refs or []), None, f"{layer}:{scope_id}",
             1 if immutable else 0, __import__("json").dumps(tags or [])),
        )
        if self.bus is not None:
            self.bus.send(Envelope(type="EVENT", from_role=actor_role, from_id=actor_id,
                                   to_role="*", task_id=task_id,
                                   payload={"kind": "memory_written", "mem_id": mem_id, "layer": layer}))
        return mem_id

    def read(self, actor_role: str, layer: str, scope_id: str, ctx: dict | None = None,
             mem_type: str | None = None, limit: int = 50) -> tuple[list[dict], str]:
        ok, why = can_access(actor_role, "read", layer, scope_id, ctx)
        if not ok:
            return [], why
        sql = "SELECT * FROM memory_records WHERE layer=? AND scope_id=?"
        params: list = [layer, scope_id]
        if mem_type:
            sql += " AND type=?"
            params.append(mem_type)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in db.query(sql, tuple(params))], "ok"

    def grant_scope(self, actor_role: str, actor_id: str, layer: str, scope_id: str,
                    granted_by: str = "MB") -> None:
        """Cross-project / cross-layer access: ONLY MB may grant (Spec 03 §4.3)."""
        db.execute("INSERT INTO memory_grants(actor_role,actor_id,scope_key,granted_by,ts) VALUES(?,?,?,?,?)",
                   (actor_role, actor_id, f"{layer}:{scope_id}", granted_by, ids.now_iso()))

    def grants_for(self, actor_role: str, actor_id: str) -> dict[str, bool]:
        rows = db.query("SELECT scope_key FROM memory_grants WHERE actor_role=? AND actor_id=?",
                        (actor_role, actor_id))
        return {r["scope_key"]: True for r in rows}

    # ---- learning pipeline (Spec 03 §4.5) ----
    def add_lesson_candidate(self, worker_id: str, content: str, evidence_refs: list | None = None) -> str:
        return self.write("WORKER", worker_id, "WORKER", worker_id, "lesson_candidate",
                          content, confidence="MEDIUM", evidence_refs=evidence_refs,
                          ctx={"own_worker_id": worker_id})

    def promote_lesson(self, mem_id: str, evidence_count: int, user_confirmed: bool = False) -> bool:
        """Promotion requires >= 2 corroborating cases or explicit user confirmation."""
        from . import config
        if evidence_count >= config.LESSON_PROMOTE_MIN_EVIDENCE or user_confirmed:
            db.execute("UPDATE memory_records SET type='lesson', confidence='HIGH' WHERE mem_id=?", (mem_id,))
            return True
        return False
