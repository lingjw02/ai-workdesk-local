import asyncio
import datetime
import logging
from typing import Dict, Any, Optional
from core.models import PermissionLevel, ToolInvocationRequest, ApprovalDecision
from core.event_bus import event_bus
from memory import store

logger = logging.getLogger("PermissionGate")


class PermissionGate:
    """Enforces the 4-level permission system. Supports non-blocking pause for single workers."""

    def __init__(self):
        self.pending_requests: Dict[str, ToolInvocationRequest] = {}
        self._waiters: Dict[str, asyncio.Event] = {}
        self._decisions: Dict[str, ApprovalDecision] = {}

    async def evaluate_and_request(
        self,
        worker_id: str,
        tool: str,
        action: str,
        params: Dict[str, Any],
        required_level: PermissionLevel,
        max_autonomy_level: int,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> bool:
        """Evaluates whether the tool invocation is allowed automatically or requires user approval."""
        request_id = f"req-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        req = ToolInvocationRequest(
            requestId=request_id,
            workerId=worker_id,
            projectId=project_id,
            taskId=task_id,
            tool=tool,
            action=action,
            params=params,
            requiredLevel=required_level,
            status="pending",
        )

        # Log audit entry
        store.append_audit_log({
            "actor": worker_id,
            "role": "worker",
            "eventType": "tool_invocation_requested",
            "details": req.model_dump(),
            "relatedTaskId": task_id,
            "relatedProjectId": project_id,
        })

        # Level 4: Never automatic
        if required_level == PermissionLevel.NEVER_AUTOMATIC:
            logger.warning(f"BLOCKED: Tool execution '{tool}.{action}' is Level 4 (Never Automatic).")
            req.status = "rejected"
            return False

        # If required level <= worker's allowed autonomy level, and level is Automatic or Notify
        if int(required_level) <= max_autonomy_level:
            if required_level == PermissionLevel.AUTOMATIC:
                return True
            if required_level == PermissionLevel.NOTIFY:
                await event_bus.broadcast("tool_executed_notify", {
                    "workerId": worker_id,
                    "tool": tool,
                    "action": action,
                    "params": params,
                    "taskId": task_id,
                })
                return True

        # Level 2 (Ask) or Level 3 (Explicit Approval) requires user confirmation
        logger.info(f"Worker [{worker_id}] requires approval for '{tool}.{action}' (Level {required_level.value})")
        self.pending_requests[request_id] = req
        waiter = asyncio.Event()
        self._waiters[request_id] = waiter

        # Broadcast approval request to frontend modal
        await event_bus.broadcast("approval_required", {
            "requestId": request_id,
            "workerId": worker_id,
            "tool": tool,
            "action": action,
            "params": params,
            "level": required_level.value,
            "taskId": task_id,
            "projectId": project_id,
            "timestamp": req.createdAt,
        })

        # Wait non-blockingly until user resolves this specific approval request
        try:
            # 5-minute timeout for human approval
            await asyncio.wait_for(waiter.wait(), timeout=300.0)
            decision = self._decisions.get(request_id)
            approved = decision.approved if decision else False
            req.status = "approved" if approved else "rejected"
            return approved
        except asyncio.TimeoutError:
            logger.warning(f"Approval request {request_id} timed out. Defaulting to reject.")
            req.status = "timeout"
            return False
        finally:
            self.pending_requests.pop(request_id, None)
            self._waiters.pop(request_id, None)

    async def resolve_approval(self, decision: ApprovalDecision):
        request_id = decision.requestId
        if request_id in self._waiters:
            self._decisions[request_id] = decision
            self._waiters[request_id].set()
            
            store.append_audit_log({
                "actor": "user",
                "role": "user",
                "eventType": "approval_decision",
                "details": decision.model_dump(),
            })
            await event_bus.broadcast("approval_resolved", decision.model_dump())
            return True
        return False

    def list_pending(self):
        return [req.model_dump() for req in self.pending_requests.values()]


permission_gate = PermissionGate()
