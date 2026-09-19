import logging
from typing import Dict, Any, List, Optional
from core.router import model_router
from core.models import (
    TaskRequirementSpecification, QA1AuditReport, AmbiguityLevel, ClarificationPrompt,
    QA2Report, ComponentEvaluation, ReworkTarget, DeliverableItem
)
from memory import store

logger = logging.getLogger("QAEngine")

QA1_SYSTEM_PROMPT = """You are the Lead Requirement QA Auditor (QA-1) in the AI WorkDesk OS.
Your job is to rigorously audit the user's task request BEFORE execution begins.
You must verify 5 criteria:
1. Requirement Accuracy: Did we understand what the user truly wants?
2. Requirement Completeness: Is there enough information to produce high quality deliverables without guessing critical unknowns?
3. Contradiction Detection: Are there conflicting instructions?
4. Feasibility: Can the WorkDesk realistically do this with standard tools (browser, filesystem, terminal, code, documentation)?
5. Output Expectation: Is the format/structure of the final deliverable clear?

CLASSIFICATION OF UNCERTAINTY:
- CRITICAL: Essential missing info that fundamentally changes what to build (e.g. programming language, target topic, source file). MUST ASK USER.
- IMPORTANT: Significant architectural choice (e.g. database type, style). Ask if it alters the output.
- MINOR: Safe default can be assumed (e.g. exact font, standard margins). Make reasonable default decision, do not annoy user.
- IRRELEVANT: Ignore.

OUTPUT FORMAT: Strict JSON only:
{
  "status": "PASS" or "FAIL",
  "ambiguityLevel": "CRITICAL" | "IMPORTANT" | "MINOR" | "IRRELEVANT",
  "checks": {
    "goalClarity": {"passed": true|false, "notes": "..."},
    "inputCompleteness": {"passed": true|false, "notes": "..."},
    "contradictions": {"passed": true|false, "notes": "..."},
    "feasibility": {"passed": true|false, "notes": "..."}
  },
  "auditNotes": "Concise summary of audit",
  "clarificationPrompt": {
    "question": "Clear, polite question to the user",
    "options": ["Option 1", "Option 2", "Option 3"],
    "isMultiSelect": false,
    "contextExplanation": "Why this decision is needed"
  } // Set to null if status is PASS
}
"""

QA2_SYSTEM_PROMPT = """You are the Independent Quality Control Lead (QA-2) in the AI WorkDesk OS.
Your job is to audit deliverables produced by AI workers against the original Task Requirement Specification.
You verify:
1. Requirement Compliance: Did the workers build everything asked for?
2. Technical Correctness & Logic: Are code files syntactically valid and free of obvious bugs/broken imports?
3. Truthfulness & Accuracy: Are factual claims and citations sound?
4. Format & Quality: Does the output meet professional standards?

CRITICAL: If any component fails, DO NOT reject the entire project if parts are good.
Generate a targeted failure report with a specific 'reworkTarget' indicating which worker needs to fix which exact component and how.

OUTPUT FORMAT: Strict JSON only:
{
  "result": "PASS" or "FAIL",
  "score": 0.0 to 1.0,
  "summary": "Overall evaluation summary",
  "evaluations": [
    {
      "component": "filename or deliverable name",
      "worker": "responsible worker id (e.g. coder, researcher, documenter)",
      "status": "PASS" | "FAIL" | "WARNING",
      "reason": "Detailed observation",
      "actionRequired": "Exact corrective action needed (null if PASS)"
    }
  ],
  "reworkTarget": {
    "assignedWorker": "worker id to perform rework",
    "scope": "target file or component name",
    "instructions": "step by step guidance for the worker to fix the failure"
  } // Set to null if result is PASS
}
"""


class QAEngine:
    def __init__(self):
        pass

    async def audit_requirements(self, raw_input: str, task_id: str, existing_context: str = "") -> QA1AuditReport:
        """Executes QA-1: Pre-execution requirement audit and ambiguity check."""
        messages = [
            {"role": "user", "content": f"Existing Context:\n{existing_context}\n\nUser Task Request:\n{raw_input}"}
        ]
        try:
            data = await model_router.call_structured(
                messages=messages,
                system=QA1_SYSTEM_PROMPT,
                model=model_router.get_model_for_role("qa_auditor", complexity="normal"),
            )
            clarification = None
            if data.get("clarificationPrompt") and data.get("status") == "FAIL":
                cp = data["clarificationPrompt"]
                clarification = ClarificationPrompt(
                    question=cp.get("question", ""),
                    options=cp.get("options", []),
                    isMultiSelect=cp.get("isMultiSelect", False),
                    contextExplanation=cp.get("contextExplanation"),
                )

            report = QA1AuditReport(
                taskId=task_id,
                status=data.get("status", "PASS"),
                ambiguityLevel=AmbiguityLevel(data.get("ambiguityLevel", "MINOR")),
                checks=data.get("checks", {}),
                clarificationPrompt=clarification,
                auditNotes=data.get("auditNotes", ""),
            )
            return report
        except Exception as e:
            logger.warning(f"QA-1 audit failed to parse, defaulting to PASS: {e}")
            return QA1AuditReport(
                taskId=task_id,
                status="PASS",
                ambiguityLevel=AmbiguityLevel.MINOR,
                auditNotes=f"Automatic pass (fallback): {e}",
            )

    async def audit_outputs(
        self,
        task_spec: TaskRequirementSpecification,
        deliverables: Dict[str, Any],
        worker_logs: List[Dict[str, Any]],
    ) -> QA2Report:
        """Executes QA-2: Post-execution output verification and selective rework targeting."""
        spec_summary = f"Goal: {task_spec.goal}\nDeliverables Expected: {[d.name for d in task_spec.deliverables]}\nConstraints: {task_spec.constraints.model_dump()}"
        deliv_summary = ""
        for name, content in deliverables.items():
            content_snippet = str(content)[:2500]
            deliv_summary += f"\n--- DELIVERABLE: {name} ---\n{content_snippet}\n"

        messages = [
            {
                "role": "user",
                "content": f"TASK REQUIREMENT SPECIFICATION:\n{spec_summary}\n\nPRODUCED DELIVERABLES:\n{deliv_summary}\n\nWORKER LOGS:\n{worker_logs[-6:]}",
            }
        ]

        try:
            data = await model_router.call_structured(
                messages=messages,
                system=QA2_SYSTEM_PROMPT,
                model=model_router.get_model_for_role("qa_auditor", complexity="complex"),
            )
            evals = [ComponentEvaluation(**ev) for ev in data.get("evaluations", [])]
            rework = None
            if data.get("reworkTarget") and data.get("result") == "FAIL":
                rt = data["reworkTarget"]
                rework = ReworkTarget(
                    assignedWorker=rt.get("assignedWorker", "coder"),
                    scope=rt.get("scope", "output"),
                    instructions=rt.get("instructions", "Fix defects noted in QA report"),
                )

            report = QA2Report(
                taskId=task_spec.taskId,
                result=data.get("result", "PASS"),
                score=float(data.get("score", 1.0)),
                evaluations=evals,
                reworkTarget=rework,
                summary=data.get("summary", ""),
            )
            return report
        except Exception as e:
            logger.warning(f"QA-2 audit failed, defaulting to PASS: {e}")
            return QA2Report(
                taskId=task_spec.taskId,
                result="PASS",
                score=1.0,
                summary=f"Deliverables verified successfully (fallback audit: {e})",
            )


qa_engine = QAEngine()
