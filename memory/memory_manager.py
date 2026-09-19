import datetime
import logging
from typing import Dict, Any, Optional, List
from memory import store
from core.models import PMLesson

logger = logging.getLogger("MemoryManager")


class MemoryIsolationError(PermissionError):
    pass


class MemoryManager:
    """Manages the 4-layer memory hierarchy with strict scoping and evidence-based learning."""

    def __init__(self):
        pass

    # --- Layer 1: Global Memory (MB Owned) ---
    def get_global_memory(self) -> Dict[str, Any]:
        return store.load_global_memory()

    def update_global_memory(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Updated global memory with keys: {list(patch.keys())}")
        return store.save_global_memory(patch)

    # --- Layer 2: Project Memory (Lifetime PM Owned) ---
    def get_project_memory(self, project_id: str, caller_role: str = "pm", caller_project_id: Optional[str] = None) -> Dict[str, Any]:
        """Strict isolation check: PM and Workers cannot access other project memories without MB grant."""
        if caller_role in ("pm", "worker") and caller_project_id and caller_project_id != project_id:
            raise MemoryIsolationError(f"Access Denied: {caller_role} of project '{caller_project_id}' cannot read memory of project '{project_id}'")

        proj = store.load_project(project_id)
        if not proj:
            return {}
        return proj.get("projectMemory", {
            "charter": proj.get("name", ""),
            "conventions": proj.get("culture", {}).get("conventions", []),
            "avoidances": proj.get("culture", {}).get("avoidances", []),
            "history": proj.get("history", []),
            "lessons": proj.get("lessons", []),
        })

    def update_project_memory(self, project_id: str, patch: Dict[str, Any], caller_project_id: Optional[str] = None):
        if caller_project_id and caller_project_id != project_id:
            raise MemoryIsolationError(f"Access Denied: Cannot modify foreign project memory '{project_id}'")

        proj = store.load_project(project_id)
        if not proj:
            return
        if "projectMemory" not in proj:
            proj["projectMemory"] = {}
        proj["projectMemory"].update(patch)
        proj["updatedAt"] = datetime.datetime.now().isoformat()
        store.save_project(proj)

    # --- Layer 3: Group Memory (Task Group Scoped) ---
    def get_group_memory(self, project_id: str, group_id: str) -> Dict[str, Any]:
        proj = store.load_project(project_id)
        if not proj:
            return {}
        groups = proj.get("taskGroups", {})
        return groups.get(group_id, {}).get("groupMemory", {})

    def update_group_memory(self, project_id: str, group_id: str, patch: Dict[str, Any]):
        proj = store.load_project(project_id)
        if not proj:
            return
        groups = proj.setdefault("taskGroups", {})
        group = groups.setdefault(group_id, {"groupId": group_id, "groupMemory": {}})
        group.setdefault("groupMemory", {}).update(patch)
        store.save_project(proj)

    # --- Layer 4: Worker Memory & Experience ---
    def record_worker_experience(self, worker_id: str, task_id: str, success: bool, duration_sec: float, notes: str = ""):
        worker_file = store.config.WORKER_DIR / f"{worker_id}.json"
        worker_data = store.read_json(worker_file)
        if not worker_data:
            return

        stats = worker_data.setdefault("statistics", {
            "timesTriggered": 0,
            "tasksCompleted": 0,
            "qaPassRate": 1.0,
            "failureRate": 0.0,
            "averageExecutionTimeSec": 0.0
        })

        total = stats.get("timesTriggered", 0) + 1
        completed = stats.get("tasksCompleted", 0) + (1 if success else 0)
        pass_rate = completed / total if total > 0 else 1.0

        stats["timesTriggered"] = total
        stats["tasksCompleted"] = completed
        stats["qaPassRate"] = round(pass_rate, 3)
        stats["failureRate"] = round(1.0 - pass_rate, 3)

        exp_list = worker_data.setdefault("experienceLog", [])
        exp_list.append({
            "taskId": task_id,
            "success": success,
            "durationSec": duration_sec,
            "notes": notes,
            "timestamp": datetime.datetime.now().isoformat(),
        })
        # Keep recent 50 logs
        worker_data["experienceLog"] = exp_list[-50:]
        store.write_json(worker_file, worker_data)

    # --- Evidence-Based Learning (PM & System) ---
    def evaluate_and_store_lesson(
        self,
        project_id: str,
        context: str,
        lesson_candidate: str,
        evidence_count: int,
        verified_by_qa: bool,
    ) -> Optional[PMLesson]:
        """Promotes a lesson candidate to permanent project institutional memory only if evidence criteria met."""
        if not verified_by_qa:
            logger.info(f"Lesson candidate '{lesson_candidate}' rejected: not verified by QA.")
            return None

        confidence = "high" if evidence_count >= 3 else ("medium" if evidence_count >= 2 else "low")
        lesson = PMLesson(
            lessonId=f"les-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
            context=context,
            rule=lesson_candidate,
            confidence=confidence,
            evidenceCount=evidence_count,
            verifiedByQA=verified_by_qa,
        )

        proj = store.load_project(project_id)
        if proj:
            lessons = proj.setdefault("lessons", [])
            lessons.append(lesson.model_dump())
            store.save_project(proj)
            logger.info(f"Learned new project lesson for '{project_id}': {lesson.rule} (Confidence: {confidence})")
        return lesson

    # --- Preference Inheritance ---
    def get_effective_preferences(self, project_id: Optional[str] = None, group_id: Optional[str] = None) -> Dict[str, Any]:
        """Resolves preferences via inheritance: Global -> Project -> Group."""
        prefs = dict(self.get_global_memory())
        if project_id:
            proj = store.load_project(project_id)
            if proj:
                proj_prefs = proj.get("preferences", {})
                prefs.update(proj_prefs)
                if group_id:
                    grp_prefs = proj.get("taskGroups", {}).get(group_id, {}).get("preferences", {})
                    prefs.update(grp_prefs)
        return prefs


memory_manager = MemoryManager()
