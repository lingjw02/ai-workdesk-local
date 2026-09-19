"""Message envelope + message types (Spec 02 §3.2-3.3)."""
from dataclasses import dataclass, field, asdict
from typing import Any

from . import ids

MESSAGE_TYPES = {
    "COMMAND", "REQUEST", "REPLY", "EVENT", "QA_VERDICT",
    "CLARIFY_REQUEST", "CLARIFY_RESPONSE", "APPROVAL_REQUEST",
    "APPROVAL_RESPONSE", "ESCALATION", "HEARTBEAT", "ACK",
}
ROLES = {"USER", "MB", "PM", "WORKER", "QA"}
PRIORITIES = {"CRITICAL", "HIGH", "NORMAL", "LOW"}


@dataclass
class Envelope:
    type: str
    from_role: str = ""
    from_id: str = ""
    to_role: str = ""
    to_id: str = ""
    task_id: str | None = None
    group_id: str | None = None
    correlation_id: str | None = None
    reply_to: str | None = None
    priority: str = "NORMAL"
    deadline_ts: str | None = None
    ttl_ms: int = 60_000
    idempotency_key: str = ""
    payload: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)
    version: str = "1.0"
    msg_id: str = field(default_factory=ids.new_id)
    ts: str = field(default_factory=ids.now_iso)

    def __post_init__(self) -> None:
        if self.type not in MESSAGE_TYPES:
            raise ValueError(f"unknown message type: {self.type}")
        if self.correlation_id is None:
            self.correlation_id = self.msg_id

    def traced(self, actor: str, action: str) -> "Envelope":
        self.trace = [*self.trace, {"actor": actor, "action": action, "ts": ids.now_iso()}]
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
