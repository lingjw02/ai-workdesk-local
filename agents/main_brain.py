import asyncio
import datetime
import logging
import uuid
from typing import Dict, Any, List, Optional
from core.models import (
    TaskState, TaskRequirementSpecification, DeliverableItem, TaskConstraints,
    UserPreferences, QA1AuditReport, QA2Report
)
from core.state_machine import state_machine
from core.router import model_router
from core.event_bus import event_bus
from memory.memory_manager import memory_manager
from memory import store
from agents.qa import qa_engine
from agents.registry import registry
from agents.pm import ProjectManagerAgent

logger = logging.getLogger("MainBrain")

PARSE_SPEC_PROMPT = """You are the Main Brain of the AI WorkDesk OS.
Parse the user's natural language goal into a structured Task Requirement Specification.
Assess whether the task is 'simple' (routine, single-step query or safe immediate action) or 'complex' (multi-step project, code creation, document generation, multi-worker coordination).

OUTPUT FORMAT: Strict JSON only:
{
  "goal": "Clear, concise statement of the objective",
  "complexity": "simple" | "complex",
  "deliverables": [
    {
      "name": "filename or deliverable label",
      "type": "code" | "document" | "data" | "action",
      "criteria": "what constitutes success for this item"
    }
  ],
  "preferences": {
    "language": "English",
    "detailLevel": "medium"
  }
}
"""


class MainBrain:
    def __init__(self):
        pass

    async def handle_user_request(
        self,
        user_text: str,
        project_id: Optional[str] = None,
        active_workers: Optional[List[str]] = None,
        clarification_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        await state_machine.transition(task_id, TaskState.ANALYZING, "Main Brain analyzing requirement")

        # Step 1: Parse requirement specification
        global_memory = memory_manager.get_global_memory()
        mem_str = "; ".join(f"{k}: {v}" for k, v in global_memory.items()) if global_memory else "none"

        parse_messages = [
            {
                "role": "user",
                "content": f"User preferences: {mem_str}\nUser Request: {user_text}"
                + (f"\nAdditional User Clarification: {clarification_response}" if clarification_response else ""),
            }
        ]

        try:
            parsed = await model_router.call_structured(
                messages=parse_messages,
                system=PARSE_SPEC_PROMPT,
                model=model_router.get_model_for_role("main_brain", complexity="normal"),
            )
        except Exception as e:
            logger.warning(f"Failed parsing structured spec, using default: {e}")
            parsed = {
                "goal": user_text,
                "complexity": "complex" if len(user_text) > 40 else "simple",
                "deliverables": [{"name": "response.txt", "type": "document", "criteria": "accurate answer"}],
                "preferences": {"language": "English", "detailLevel": "medium"},
            }

        deliverables = [DeliverableItem(**d) for d in parsed.get("deliverables", [])]
        task_spec = TaskRequirementSpecification(
            taskId=task_id,
            projectId=project_id,
            goal=parsed.get("goal", user_text),
            complexity=parsed.get("complexity", "complex"),
            deliverables=deliverables,
            preferences=UserPreferences(**parsed.get("preferences", {})),
            rawUserInput=user_text,
        )

        # Step 2: QA-1 Requirement Audit (The Ambiguity Gate)
        await state_machine.transition(task_id, TaskState.QA_1, "Conducting QA-1 Requirement Audit")
        qa1_report: QA1AuditReport = await qa_engine.audit_requirements(
            raw_input=user_text,
            task_id=task_id,
            existing_context=f"Project: {project_id}, Global preferences: {mem_str}",
        )

        # Broadcast QA-1 result to Work Graph UI
        await event_bus.broadcast("qa1_audit_completed", {
            "taskId": task_id,
            "status": qa1_report.status,
            "ambiguityLevel": qa1_report.ambiguityLevel.value,
            "clarificationPrompt": qa1_report.clarificationPrompt.model_dump() if qa1_report.clarificationPrompt else None,
            "auditNotes": qa1_report.auditNotes,
        })

        if qa1_report.status == "FAIL" and qa1_report.clarificationPrompt and not clarification_response:
            # Ambiguity detected -> Trigger Reprompt Assistant
            await state_machine.transition(task_id, TaskState.CLARIFICATION_REQUIRED, "Ambiguity detected by QA-1")
            return {
                "taskId": task_id,
                "status": "CLARIFICATION_REQUIRED",
                "clarification": qa1_report.clarificationPrompt.model_dump(),
                "taskSpec": task_spec.model_dump(),
            }

        # Step 3: Simple vs Complex Routing
        if task_spec.complexity == "simple" and not project_id:
            # Direct Work by Main Brain
            await state_machine.transition(task_id, TaskState.WORKING, "Executing simple direct task")
            reply = await model_router.call_openrouter(
                messages=[{"role": "user", "content": user_text}],
                system=f"You are the Main Brain of the AI WorkDesk OS. User preferences: {mem_str}. Be direct, professional, and clear.",
                deepthink="normal",
            )
            await state_machine.transition(task_id, TaskState.FINALIZING, "Finalizing direct answer")
            await state_machine.transition(task_id, TaskState.DONE, "Simple task completed")
            return {
                "taskId": task_id,
                "status": "DONE",
                "complexity": "simple",
                "reply": reply,
                "deliverables": {"answer.txt": reply},
            }

        # Step 4: Complex Task -> Task Group Coordination via Lifetime PM
        if not project_id:
            # Create a default project if none specified
            default_proj = {
                "id": f"proj-{uuid.uuid4().hex[:6]}",
                "name": "Default Workspace",
                "workers": active_workers or ["researcher", "coder", "documenter"],
                "createdAt": datetime.datetime.now().isoformat(),
                "updatedAt": datetime.datetime.now().isoformat(),
            }
            store.save_project(default_proj)
            project_id = default_proj["id"]

        proj = store.load_project(project_id)
        workers = active_workers or (proj.get("workers") if proj else ["researcher", "coder", "documenter"])
        pm_profile = registry.get_or_create_pm(project_id, proj.get("name", "Project") if proj else "Project")
        pm_agent = ProjectManagerAgent(pm_profile)

        await state_machine.transition(task_id, TaskState.PLANNING, "PM decomposing task")
        await state_machine.transition(task_id, TaskState.ASSIGNED, f"Workers assigned: {', '.join(workers)}")
        await state_machine.transition(task_id, TaskState.WORKING, "Task Group executing")

        # PM coordinates worker tasks
        exec_result = await pm_agent.plan_and_execute_task(task_spec, active_worker_ids=workers)
        deliverables_dict = exec_result.get("deliverables", {})
        worker_logs = exec_result.get("workerLogs", [])

        # Step 5: QA-2 Output Verification
        await state_machine.transition(task_id, TaskState.QA_2, "Conducting QA-2 Output Verification")
        qa2_report: QA2Report = await qa_engine.audit_outputs(
            task_spec=task_spec,
            deliverables=deliverables_dict,
            worker_logs=worker_logs,
        )

        await event_bus.broadcast("qa2_audit_completed", {
            "taskId": task_id,
            "result": qa2_report.result,
            "score": qa2_report.score,
            "summary": qa2_report.summary,
            "evaluations": [e.model_dump() for e in qa2_report.evaluations],
            "reworkTarget": qa2_report.reworkTarget.model_dump() if qa2_report.reworkTarget else None,
        })

        # Step 6: Selective Rework Loop if QA-2 Failed
        if qa2_report.result == "FAIL" and qa2_report.reworkTarget:
            logger.info(f"QA-2 failed. Triggering selective rework on {qa2_report.reworkTarget.scope}")
            await state_machine.transition(task_id, TaskState.REWORK, f"Reworking {qa2_report.reworkTarget.scope}")
            deliverables_dict = await pm_agent.execute_rework(
                task_spec=task_spec,
                rework_target=qa2_report.reworkTarget,
                existing_deliverables=deliverables_dict,
            )
            # Re-audit
            await state_machine.transition(task_id, TaskState.QA_2, "Re-auditing reworked output")
            qa2_report = await qa_engine.audit_outputs(
                task_spec=task_spec,
                deliverables=deliverables_dict,
                worker_logs=worker_logs,
            )

        # Step 7: Finalize & Learn
        await state_machine.transition(task_id, TaskState.FINALIZING, "Finalizing deliverables")
        
        # Evidence-based learning candidate extraction
        if qa2_report.result == "PASS":
            memory_manager.evaluate_and_store_lesson(
                project_id=project_id,
                context=task_spec.goal[:80],
                lesson_candidate=f"Workflow succeeded for {task_spec.goal[:40]} with {', '.join(workers)}",
                evidence_count=len(worker_logs),
                verified_by_qa=True,
            )

        await state_machine.transition(task_id, TaskState.DONE, "Task successfully completed")

        return {
            "taskId": task_id,
            "status": "DONE",
            "complexity": "complex",
            "pmPlan": exec_result.get("pmPlan"),
            "deliverables": deliverables_dict,
            "qa2Report": qa2_report.model_dump(),
            "workerLogs": worker_logs,
        }


main_brain = MainBrain()
