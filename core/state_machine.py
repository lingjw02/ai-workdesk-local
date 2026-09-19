import asyncio
import logging
import datetime
from typing import Dict, Optional, Set
from core.models import TaskState
from core.event_bus import event_bus

logger = logging.getLogger("StateMachine")

VALID_TRANSITIONS: Dict[TaskState, Set[TaskState]] = {
    TaskState.CREATED: {TaskState.ANALYZING, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.ANALYZING: {TaskState.QA_1, TaskState.CLARIFICATION_REQUIRED, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.CLARIFICATION_REQUIRED: {TaskState.ANALYZING, TaskState.CANCELLED},
    TaskState.QA_1: {TaskState.CLARIFICATION_REQUIRED, TaskState.PLANNING, TaskState.FINALIZING, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.PLANNING: {TaskState.WAITING_FOR_APPROVAL, TaskState.ASSIGNED, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.WAITING_FOR_APPROVAL: {TaskState.ASSIGNED, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.ASSIGNED: {TaskState.WORKING, TaskState.CANCELLED, TaskState.PAUSED},
    TaskState.WORKING: {TaskState.QA_2, TaskState.WAITING_FOR_APPROVAL, TaskState.PAUSED, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.QA_2: {TaskState.REWORK, TaskState.FINALIZING, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.REWORK: {TaskState.WORKING, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.FINALIZING: {TaskState.DONE, TaskState.CANCELLED, TaskState.ERROR},
    TaskState.PAUSED: {TaskState.WORKING, TaskState.CANCELLED},
    TaskState.DONE: set(),
    TaskState.CANCELLED: set(),
    TaskState.ERROR: set(),
}


class TaskStateMachine:
    def __init__(self):
        self._states: Dict[str, TaskState] = {}
        self._cancel_flags: Dict[str, bool] = {}
        self._history: Dict[str, list] = {}

    def get_state(self, task_id: str) -> TaskState:
        return self._states.get(task_id, TaskState.CREATED)

    def is_cancelled(self, task_id: str) -> bool:
        return self._cancel_flags.get(task_id, False)

    def cancel(self, task_id: str):
        self._cancel_flags[task_id] = True
        self.transition(task_id, TaskState.CANCELLED, reason="User cancelled task")

    async def transition(self, task_id: str, new_state: TaskState, reason: str = "") -> TaskState:
        current_state = self._states.get(task_id, TaskState.CREATED)
        
        # Check transition validity
        allowed = VALID_TRANSITIONS.get(current_state, set())
        if new_state not in allowed and new_state not in (TaskState.CANCELLED, TaskState.ERROR):
            logger.warning(
                f"Transition from {current_state} to {new_state} for task {task_id} is unusual, enforcing state override."
            )

        self._states[task_id] = new_state
        entry = {
            "from": current_state.value,
            "to": new_state.value,
            "reason": reason,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        if task_id not in self._history:
            self._history[task_id] = []
        self._history[task_id].append(entry)

        logger.info(f"Task [{task_id}] state: {current_state.value} -> {new_state.value} ({reason})")

        # Broadcast update for Work Graph and Virtual Office
        await event_bus.broadcast("task_state_changed", {
            "taskId": task_id,
            "state": new_state.value,
            "previousState": current_state.value,
            "reason": reason,
            "timestamp": entry["timestamp"],
        })
        return new_state


state_machine = TaskStateMachine()
