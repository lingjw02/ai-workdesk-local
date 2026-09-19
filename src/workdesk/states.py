"""Task state machine (Spec 01 §2.2-2.4) and worker sub-states."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from . import ids


class TaskState(str, Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    CLARIFYING = "CLARIFYING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_INPUT = "WAITING_INPUT"
    PAUSED = "PAUSED"
    IN_QA = "IN_QA"
    REWORK = "REWORK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}

# (from, to) -> trigger name; every pair is the canonical transition table (Spec 01 §2.3)
ALLOWED: dict[tuple[TaskState, TaskState], str] = {
    (TaskState.CREATED, TaskState.ANALYZING): "MB_ACCEPT",
    (TaskState.ANALYZING, TaskState.CLARIFYING): "QA1_FAIL",
    (TaskState.CLARIFYING, TaskState.ANALYZING): "CLARIFY_RESOLVED",
    (TaskState.CLARIFYING, TaskState.FAILED): "QA1_FAIL_FINAL",
    (TaskState.ANALYZING, TaskState.READY): "QA1_PASS",
    (TaskState.READY, TaskState.RUNNING): "PM_START",
    (TaskState.RUNNING, TaskState.WAITING_INPUT): "DECISION_NEEDED",
    (TaskState.WAITING_INPUT, TaskState.RUNNING): "INPUT_RECEIVED",
    (TaskState.RUNNING, TaskState.PAUSED): "PAUSE",
    (TaskState.PAUSED, TaskState.RUNNING): "RESUME",
    (TaskState.PAUSED, TaskState.READY): "RESUME_FROM_CHECKPOINT",
    (TaskState.CANCELLED, TaskState.READY): "RESUME_FROM_CHECKPOINT",
    (TaskState.RUNNING, TaskState.READY): "RESTART",
    (TaskState.RUNNING, TaskState.IN_QA): "OUTPUT_READY",
    (TaskState.IN_QA, TaskState.REWORK): "QA2_FAIL",
    (TaskState.REWORK, TaskState.RUNNING): "REWORK_ASSIGNED",
    (TaskState.IN_QA, TaskState.COMPLETED): "QA2_PASS",
    (TaskState.IN_QA, TaskState.FAILED): "RETRY_LIMIT",      # QA-2 verdict fails at the cap
    (TaskState.RUNNING, TaskState.FAILED): "RETRIES_EXHAUSTED",
    (TaskState.REWORK, TaskState.FAILED): "RETRY_LIMIT",
}
for _s in list(TaskState):
    if _s not in TERMINAL:
        ALLOWED[(_s, TaskState.CANCELLED)] = "STOP"
ALLOWED[(TaskState.CREATED, TaskState.CANCELLED)] = "STOP"


class TransitionError(RuntimeError):
    pass


@dataclass
class StateMachine:
    """Event-sourced task state machine: every transition appends an immutable event."""

    task_id: str
    state: TaskState = TaskState.CREATED
    events: list[dict[str, Any]] = field(default_factory=list)

    def can(self, to: TaskState) -> bool:
        return (self.state, to) in ALLOWED

    def transition(self, to: TaskState, trigger: str | None = None, actor: str = "MB",
                   payload: dict | None = None) -> dict[str, Any]:
        if to not in TaskState:
            raise TransitionError(f"unknown state {to!r}")
        if not self.can(to):
            raise TransitionError(f"illegal transition {self.state.value} -> {to.value}")
        ev = {
            "seq": len(self.events) + 1,
            "from": self.state.value,
            "to": to.value,
            "trigger": trigger or ALLOWED.get((self.state, to), ""),
            "actor": actor,
            "ts": ids.now_iso(),
            "payload": payload or {},
        }
        self.events.append(ev)
        self.state = to
        return ev


class WorkerState(str, Enum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    THINKING = "THINKING"
    COLLABORATING = "COLLABORATING"
    WAITING_PM = "WAITING_PM"
    WAITING_MB = "WAITING_MB"
    WAITING_USER = "WAITING_USER"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    ERROR = "ERROR"
    DONE = "DONE"
