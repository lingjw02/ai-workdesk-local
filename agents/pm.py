import asyncio
import datetime
import logging
from typing import Dict, Any, List, Optional
from core.models import PMProfile, TaskRequirementSpecification, QA2Report, ReworkTarget
from core.router import model_router
from core.event_bus import event_bus
from memory.memory_manager import memory_manager
from agents.registry import registry
from agents.worker import WorkerRunner

logger = logging.getLogger("LifetimePM")

PM_DECOMPOSE_PROMPT = """You are the Project Manager for this project.
You lead a team of persistent specialists.
Your job is to read the Task Requirement Specification and decompose it into targeted sub-tasks for active workers.

AVAILABLE WORKERS ON THIS PROJECT:
{workers_str}

PROJECT CULTURE & CONVENTIONS:
{culture_str}

HISTORICAL LESSONS LEARNED ON THIS PROJECT:
{lessons_str}

TASK SPECIFICATION:
Goal: {goal}
Deliverables Expected: {deliverables}
Preferences: {preferences}

CRITICAL: Return strictly a JSON object with this format:
{{
  "pmPlan": "1-3 sentences outlining your management strategy for this task",
  "assignments": [
    {{
      "workerId": "worker id from available list",
      "instruction": "specific, precise instruction for this specialist",
      "order": 1
    }}
  ]
}}
Only assign workers who are genuinely needed. Multiple workers with the same order will run in parallel.
"""


class ProjectManagerAgent:
    def __init__(self, pm_profile: PMProfile):
        self.profile = pm_profile

    def _format_culture_str(self) -> str:
        conventions = self.profile.projectCulture.conventions
        avoidances = self.profile.projectCulture.avoidances
        s = "Conventions:\n" + "\n".join(f"- {c}" for c in conventions)
        if avoidances:
            s += "\nAvoidances:\n" + "\n".join(f"- {a}" for a in avoidances)
        return s

    def _format_lessons_str(self) -> str:
        if not self.profile.lessons:
            return "None recorded yet."
        return "\n".join(f"- [{l.confidence.upper()}] {l.rule} (Evidence count: {l.evidenceCount})" for l in self.profile.lessons[-5:])

    async def plan_and_execute_task(
        self,
        task_spec: TaskRequirementSpecification,
        active_worker_ids: List[str],
    ) -> Dict[str, Any]:
        project_id = self.profile.projectId
        task_id = task_spec.taskId

        await event_bus.broadcast("pm_status_changed", {
            "pmId": self.profile.pmId,
            "projectId": project_id,
            "status": "planning",
            "message": f"Decomposing task '{task_spec.goal[:60]}...'",
        })

        # Filter available workers
        workers_meta = []
        for wid in active_worker_ids:
            w = registry.get_worker(wid)
            if w:
                workers_meta.append(f"- {w.id}: {w.name} ({w.description})")
        workers_str = "\n".join(workers_meta)

        messages = [
            {"role": "user", "content": "Please decompose this task into worker assignments."}
        ]
        system = PM_DECOMPOSE_PROMPT.format(
            workers_str=workers_str,
            culture_str=self._format_culture_str(),
            lessons_str=self._format_lessons_str(),
            goal=task_spec.goal,
            deliverables=[d.name for d in task_spec.deliverables],
            preferences=task_spec.preferences.model_dump(),
        )

        plan_data = await model_router.call_structured(
            messages=messages,
            system=system,
            model=model_router.get_model_for_role("pm", complexity="complex"),
        )

        pm_plan = plan_data.get("pmPlan", "Coordinating team execution.")
        assignments = plan_data.get("assignments", [])

        await event_bus.broadcast("pm_status_changed", {
            "pmId": self.profile.pmId,
            "projectId": project_id,
            "status": "executing",
            "message": pm_plan,
            "plan": plan_data,
        })

        # Execute assignments
        deliverables: Dict[str, Any] = {}
        worker_logs: List[Dict[str, Any]] = []

        # Run assignments in parallel
        tasks = []
        for asgn in assignments:
            wid = asgn.get("workerId")
            instruction = asgn.get("instruction", "")
            worker_prof = registry.get_worker(wid)
            if worker_prof:
                runner = WorkerRunner(worker_prof)
                tasks.append(runner.execute(
                    instruction=instruction,
                    task_id=task_id,
                    project_id=project_id,
                    project_culture=self.profile.projectCulture.model_dump(),
                ))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Worker task failed with exception: {res}")
                worker_logs.append({"error": str(res)})
            elif isinstance(res, dict):
                deliverables.update(res.get("deliverables", {}))
                worker_logs.append({
                    "workerId": res.get("workerId"),
                    "summary": res.get("summary"),
                    "success": res.get("success"),
                })

        return {
            "pmPlan": pm_plan,
            "deliverables": deliverables,
            "workerLogs": worker_logs,
        }

    async def execute_rework(
        self,
        task_spec: TaskRequirementSpecification,
        rework_target: ReworkTarget,
        existing_deliverables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Performs targeted selective rework without restarting the entire Task Group."""
        logger.info(f"PM executing selective rework with worker [{rework_target.assignedWorker}] on scope: {rework_target.scope}")
        await event_bus.broadcast("pm_status_changed", {
            "pmId": self.profile.pmId,
            "projectId": self.profile.projectId,
            "status": "reworking",
            "message": f"Directing {rework_target.assignedWorker} to rework: {rework_target.scope}",
        })

        worker_prof = registry.get_worker(rework_target.assignedWorker)
        if not worker_prof:
            worker_prof = registry.get_worker("coder")

        runner = WorkerRunner(worker_prof)
        context = f"Previous deliverable content for {rework_target.scope}:\n{existing_deliverables.get(rework_target.scope, '')}"
        
        rework_res = await runner.execute(
            instruction=rework_target.instructions,
            task_id=task_spec.taskId,
            project_id=self.profile.projectId,
            context=context,
            project_culture=self.profile.projectCulture.model_dump(),
        )

        existing_deliverables.update(rework_res.get("deliverables", {}))
        return existing_deliverables
