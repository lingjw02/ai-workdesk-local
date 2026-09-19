"""Task and TaskGroup records (Spec 01 / Spec 04 §5.4)."""
from dataclasses import dataclass, field
from typing import Any

from . import ids
from .states import StateMachine, TaskState


@dataclass
class Task:
    task_id: str
    request_text: str
    project_id: str = "default"
    conversation_id: str | None = None
    spec: dict[str, Any] = field(default_factory=dict)
    state: TaskState = TaskState.CREATED
    group_id: str | None = None
    rework_count: int = 0
    result: dict[str, Any] | None = None
    created_ts: str = field(default_factory=ids.now_iso)
    updated_ts: str = field(default_factory=ids.now_iso)
    sm: StateMachine = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.state, TaskState):
            self.state = TaskState(self.state)
        self.sm = StateMachine(task_id=self.task_id, state=self.state)


@dataclass
class TaskGroup:
    group_id: str
    task_id: str
    pm_id: str
    member_worker_ids: list[str] = field(default_factory=list)
    shared_requirements_ref: str | None = None
    artifacts_manifest: list[dict[str, Any]] = field(default_factory=list)
    memory_scope_id: str = field(default_factory=ids.new_id)
    created_ts: str = field(default_factory=ids.now_iso)
    closed_ts: str | None = None
