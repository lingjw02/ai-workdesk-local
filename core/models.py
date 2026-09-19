from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
import datetime


class TaskState(str, Enum):
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    PLANNING = "PLANNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    ASSIGNED = "ASSIGNED"
    WORKING = "WORKING"
    QA_1 = "QA_1"
    QA_2 = "QA_2"
    REWORK = "REWORK"
    FINALIZING = "FINALIZING"
    DONE = "DONE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class AmbiguityLevel(str, Enum):
    CRITICAL = "CRITICAL"      # Must ask user
    IMPORTANT = "IMPORTANT"    # Ask if affects architecture/result
    MINOR = "MINOR"            # AI makes reasonable default decision
    IRRELEVANT = "IRRELEVANT"  # Ignore


class PermissionLevel(int, Enum):
    AUTOMATIC = 0          # Safe routine actions
    NOTIFY = 1             # Low risk, execute then notify
    ASK = 2                # Important decision, requires user single-click approval
    EXPLICIT_APPROVAL = 3  # High impact / destructive / external communication
    NEVER_AUTOMATIC = 4    # Critical system boundaries, forbidden without manual admin


class DeliverableItem(BaseModel):
    name: str
    type: str = Field(description="code, document, data, action")
    format: Optional[str] = None
    criteria: str = ""


class TaskConstraints(BaseModel):
    allowedPaths: List[str] = Field(default_factory=list)
    forbiddenActions: List[str] = Field(default_factory=list)
    timeoutMs: int = 120000


class UserPreferences(BaseModel):
    language: str = "English"
    detailLevel: str = "medium"  # concise, medium, thorough
    formatting: Optional[str] = "Markdown"
    additional: Dict[str, Any] = Field(default_factory=dict)


class TaskRequirementSpecification(BaseModel):
    taskId: str
    projectId: Optional[str] = None
    goal: str
    complexity: str = "complex"  # simple vs complex
    deliverables: List[DeliverableItem] = Field(default_factory=list)
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)
    preferences: UserPreferences = Field(default_factory=UserPreferences)
    rawUserInput: str = ""
    createdAt: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class ClarificationPrompt(BaseModel):
    question: str
    options: List[str] = Field(default_factory=list)
    isMultiSelect: bool = False
    contextExplanation: Optional[str] = None


class QA1AuditReport(BaseModel):
    taskId: str
    status: str = "PASS"  # PASS or FAIL
    ambiguityLevel: AmbiguityLevel = AmbiguityLevel.MINOR
    checks: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    clarificationPrompt: Optional[ClarificationPrompt] = None
    auditNotes: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class ComponentEvaluation(BaseModel):
    component: str
    worker: str
    status: str = "PASS"  # PASS, FAIL, WARNING
    reason: str = ""
    actionRequired: Optional[str] = None


class ReworkTarget(BaseModel):
    assignedWorker: str
    scope: str
    instructions: str


class QA2Report(BaseModel):
    taskId: str
    result: str = "PASS"  # PASS or FAIL
    score: float = 1.0
    evaluations: List[ComponentEvaluation] = Field(default_factory=list)
    reworkTarget: Optional[ReworkTarget] = None
    summary: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class WorkerPersonality(BaseModel):
    temperament: str = "professional, analytical"
    communicationStyle: str = "concise, direct"
    behaviorRules: List[str] = Field(default_factory=list)
    oocRules: List[str] = Field(default_factory=list)


class WorkerSkills(BaseModel):
    primary: List[str] = Field(default_factory=list)
    secondary: List[str] = Field(default_factory=list)
    expertiseLevel: str = "senior"


class WorkerPermissions(BaseModel):
    maxAutonomyLevel: int = 1
    allowedDirectories: List[str] = Field(default_factory=lambda: ["./projects/*"])
    blockedCommands: List[str] = Field(default_factory=list)


class WorkerStatistics(BaseModel):
    timesTriggered: int = 0
    tasksCompleted: int = 0
    qaPassRate: float = 1.0
    failureRate: float = 0.0
    averageExecutionTimeSec: float = 0.0


class WorkerProfile(BaseModel):
    id: str
    name: str
    avatar: str = "🤖"
    description: str = ""
    personality: WorkerPersonality = Field(default_factory=WorkerPersonality)
    skills: WorkerSkills = Field(default_factory=WorkerSkills)
    tools: List[str] = Field(default_factory=list)
    permissions: WorkerPermissions = Field(default_factory=WorkerPermissions)
    statistics: WorkerStatistics = Field(default_factory=WorkerStatistics)
    status: str = "available"  # available, working, thinking, waiting, waiting_approval, completed, error


class PMIdentity(BaseModel):
    role: str = "Project Manager"
    personality: str = "structured, proactive, safety-conscious"
    managementStyle: str = "agile task decomposition with strict QA gates"


class ProjectCulture(BaseModel):
    conventions: List[str] = Field(default_factory=list)
    avoidances: List[str] = Field(default_factory=list)


class WorkerPerformanceItem(BaseModel):
    reliability: float = 0.95
    bestUse: str = "general execution"
    notes: Optional[str] = None


class PMLesson(BaseModel):
    lessonId: str
    context: str
    rule: str
    confidence: str = "medium"  # low, medium, high
    evidenceCount: int = 1
    verifiedByQA: bool = True
    createdAt: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class PMProfile(BaseModel):
    pmId: str
    projectId: str
    name: str = "Project Manager"
    coreIdentity: PMIdentity = Field(default_factory=PMIdentity)
    projectCulture: ProjectCulture = Field(default_factory=ProjectCulture)
    workerPerformanceMatrix: Dict[str, WorkerPerformanceItem] = Field(default_factory=dict)
    lessons: List[PMLesson] = Field(default_factory=list)
    status: str = "idle"


class ToolInvocationRequest(BaseModel):
    requestId: str
    workerId: str
    projectId: Optional[str] = None
    taskId: Optional[str] = None
    tool: str
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)
    requiredLevel: PermissionLevel = PermissionLevel.AUTOMATIC
    status: str = "pending"  # pending, approved, rejected, executed
    createdAt: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class ApprovalDecision(BaseModel):
    requestId: str
    approved: bool
    userComment: Optional[str] = None
    modifiedParams: Optional[Dict[str, Any]] = None


class AuditLogEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    actor: str
    role: str
    eventType: str
    details: Dict[str, Any] = Field(default_factory=dict)
    relatedTaskId: Optional[str] = None
    relatedProjectId: Optional[str] = None
