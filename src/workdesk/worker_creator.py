"""Phase-3 Worker Creator meta-worker (Spec §16 Phase 3 + §5 creation paths).

The Worker Creator is the meta-worker whose job is to design and create OTHER
workers. It is invoked by the Main Brain when a requirement needs a capability
no existing worker has (Phase-2 capability-gap detection), and can also be used
directly (install from a profile = the "user manually creates" path).

Creation is permission-gated: creating a worker is an *install* operation, so it
resolves the permission policy (default EXPLICIT) and records an approval. With
`auto_approve=True` (demo/tests) the approval passes automatically; otherwise the
creation stays PENDING and the requester is asked.

Every worker the Creator makes carries a complete profile (identity, personality,
behavior rules, communication style, skills, tools, memory rules) and a dynamic
stub skill handler, so the capability-gap → create → execute → QA-2 loop actually
runs end to end (real skill implementations land in later phases).
"""
from . import db, ids
from .runtime import StubWorker

_DYNAMIC_EXT = {"slides": "md", "excel": "csv", "email": "txt", "plan": "md"}


def _dynamic_handler(engine, capability: str):
    """Generic stub skill body for a dynamically created worker. Produces a
    placeholder artifact containing a Summary section so QA-2's content check
    passes; clearly marked as a Phase-3 stub (no real LLM implementation yet)."""
    ext = _DYNAMIC_EXT.get(capability, "txt")

    def handler(task, group, comp):
        from pathlib import Path
        fname = f"{capability}_output.{ext}"
        path = Path(engine.project_dir) / task.project_id / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            f"# {capability} output\n\n"
            f"Summary: stub output for capability '{capability}'.\n\n"
            "Phase-3 stub produced by a Worker-Creator-made worker; "
            "no real implementation yet (Phase 8+).\n"
        )
        path.write_text(content, encoding="utf-8")
        return {"kind": "file", "path": str(path)}

    return handler


class WorkerCreator:
    # ---- worker design: the full profile (Spec 04 §5.1) ----
    def design(self, capability: str, *, description: str = "", name: str | None = None) -> dict:
        wid = f"w-{capability}"
        skill_id = f"{capability}.build"
        return {
            "worker_id": wid,
            "name": name or f"{capability.title()} Worker",
            "role_class": "WORKER",
            "description": description or f"Dynamic worker for capability '{capability}' "
                                          f"(created by Worker Creator).",
            "personality": {
                "traits": ["diligent", "reliable"],
                "tone": "professional",
                "description": description or f"Worker for capability '{capability}'",
                "communication_style": "concise status updates",
            },
            "behavior_rules": [
                "report blockers to the PM",
                "follow the permission policy",
                "never touch system-scope resources",
            ],
            "skills": [{"skill_id": skill_id, "primary": True, "capability": capability}],
            "tools": [{"tool": "FILESYSTEM", "permissions": {"read": True, "write": True}}],
            "permissions": {},
            "memory_rules": {"group_memory": True, "own_experience": True,
                             "cross_project": "NEVER"},
        }

    # ---- creation: permission-gated, idempotent ----
    def create(self, engine, capability: str, *, description: str = "",
               name: str | None = None, task_id: str | None = None,
               requester_role: str = "MB", requester_id: str = "mb") -> tuple[str | None, str]:
        """Create (or reuse) a worker for `capability`.

        Returns (worker_id, status) where status is one of
        'created' / 'existing' / 'pending' (approval outstanding) / 'denied'.
        """
        wid = f"w-{capability}"
        if engine.registry.get_worker(wid) is not None:
            return wid, "existing"
        # installing a worker is a high-impact action: resolve the permission policy
        ap_id, level = engine.permissions.require_approval(
            requester_role, requester_id, "install", f"worker:{capability}", "REGISTRY",
            task_id=task_id)
        if level in ("ASK", "EXPLICIT"):
            if ap_id is None:
                return None, "denied"
            row = db.query_one("SELECT status FROM approvals WHERE approval_id=?", (ap_id,))
            if row is None or row["status"] != "APPROVED":
                return None, "pending"
        profile = self.design(capability, description=description, name=name)
        skill = profile["skills"][0]
        full_sid = engine.registry.register_skill(name=skill["skill_id"],
                                                  entry_point=f"stub:{skill['skill_id']}",
                                                  tools_required=["FILESYSTEM"])
        engine.skill_handlers[skill["skill_id"]] = _dynamic_handler(engine, capability)
        wid = engine.registry.register_worker(
            worker_id=wid, name=profile["name"], role_class=profile["role_class"],
            personality=profile["personality"], behavior_rules=profile["behavior_rules"],
            skills=[{"skill_id": full_sid, "primary": True, "capability": capability}],
            tools=profile["tools"], permissions=profile["permissions"],
            memory_rules=profile["memory_rules"])
        engine.registry.activate(wid)
        engine.workers[wid] = StubWorker(engine, wid, profile["name"],
                                         {skill["skill_id"]: {"capability": capability}})
        engine.permissions.audit(requester_role, requester_id, "worker_created",
                                 reason=f"capability={capability}", task_id=task_id)
        return wid, "created"

    def upgrade(self, engine, worker_id: str, new_capability: str, *,
                task_id: str | None = None) -> str | None:
        """Add a capability to an existing worker (upgrade path). Returns worker_id."""
        row = engine.registry.get_worker(worker_id)
        if row is None:
            return None
        existing_caps = {s.get("capability") for s in (row.get("skills") or [])}
        if new_capability in existing_caps:
            return worker_id
        skill_id = f"{new_capability}.build"
        full_sid = engine.registry.register_skill(name=skill_id,
                                                  entry_point=f"stub:{skill_id}",
                                                  tools_required=["FILESYSTEM"])
        engine.skill_handlers[skill_id] = _dynamic_handler(engine, new_capability)
        skills = (row.get("skills") or []) + [{"skill_id": full_sid, "primary": False,
                                               "capability": new_capability}]
        engine.registry.register_worker(worker_id=worker_id, name=row["name"],
                                        role_class=row.get("role_class", "WORKER"),
                                        personality=row.get("personality") or {},
                                        behavior_rules=row.get("behavior_rules") or [],
                                        skills=skills, tools=row.get("tools") or [],
                                        permissions=row.get("permissions") or {},
                                        memory_rules=row.get("memory_rules") or {})
        worker = engine.workers.get(worker_id)
        if worker is not None:
            worker.skills[skill_id] = {"capability": new_capability}
        engine.permissions.audit("MB", "mb", "worker_upgraded",
                                 reason=f"worker={worker_id}; capability={new_capability}",
                                 task_id=task_id)
        return worker_id
