"""AI WorkDesk OS — headless core engine (Spec v0.1, Phases 1-6)."""

__version__ = "0.6.0"

from .bus import MessageBus, Envelope
from .engine import Engine
from .main_brain import MainBrainIntelligence, RequirementSpec
from .memory import MemoryManager, can_access
from .permissions import PermissionManager
from .registry import Registry
from .runtime import QA, StubWorker, ProjectManager, ClarificationNeeded, FailureReport
from .states import TaskState, WorkerState, StateMachine, TransitionError
from .task import Task, TaskGroup
from .tools import ToolError, ToolRegistry, ToolResult, ToolSpec
from .worker_creator import WorkerCreator

__all__ = [
    "Engine", "MessageBus", "Envelope", "MemoryManager", "can_access",
    "PermissionManager", "Registry", "QA", "StubWorker", "ProjectManager",
    "ClarificationNeeded", "FailureReport",
    "MainBrainIntelligence", "RequirementSpec", "WorkerCreator",
    "TaskState", "WorkerState", "StateMachine", "TransitionError", "Task", "TaskGroup",
    "ToolError", "ToolRegistry", "ToolResult", "ToolSpec",
]
