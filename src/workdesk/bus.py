"""In-process message bus (Spec 02).

Phase-1 headless implementation of the protocol: envelopes, channels, dedup,
at-least-once with retry + dead-letter, request/reply with deadline, audit hook.
Heartbeat supervision is Phase 1.1 (constants reserved in config).
"""
import queue
import threading
import time
from collections import defaultdict
from typing import Callable

from . import config
from .envelope import Envelope

Handler = Callable[[Envelope], None]


class MessageBus:
    def __init__(self, retries: int | None = None, backoff: float | None = None):
        self._handlers: dict[tuple[str, str], list[Handler]] = defaultdict(list)
        self._seen: set[str] = set()
        # RLock: request() holds the condition lock while send() re-acquires it
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._replies: dict[str, Envelope] = {}
        self.retries = retries if retries is not None else config.RETRY_MESSAGE
        self.backoff = backoff if backoff is not None else config.BACKOFF_BASE_SEC
        self.dlq: list[tuple] = []
        self.stats = {"sent": 0, "delivered": 0, "deduped": 0, "failed": 0}
        self.audit_hook: Callable[[Envelope], None] | None = None

    # ---- routing (Spec 02 §3.4) ----
    def route(self, env: Envelope) -> str:
        if env.group_id and env.type in ("EVENT", "COMMAND", "REQUEST"):
            return f"group.{env.group_id}"
        if env.task_id:
            suffix = "event" if env.type in ("EVENT", "QA_VERDICT") else "cmd"
            return f"task.{env.task_id}.{suffix}"
        if env.to_role == "USER":
            return "user.out"
        if env.from_role == "USER":
            return "user.in"
        return "default"

    def subscribe(self, channel: str, role: str, handler: Handler) -> None:
        self._handlers[(channel, role)].append(handler)

    # ---- delivery ----
    def send(self, env: Envelope) -> bool:
        with self._lock:
            self.stats["sent"] += 1
        if env.idempotency_key:
            with self._lock:
                if env.idempotency_key in self._seen:
                    self.stats["deduped"] += 1
                    return False
                self._seen.add(env.idempotency_key)
        if self.audit_hook is not None and env.type not in ("ACK", "HEARTBEAT"):
            try:
                self.audit_hook(env)
            except Exception:
                pass
        ch = self.route(env)
        threading.Thread(target=self._dispatch, args=(ch, env), daemon=True).start()
        return True

    def _dispatch(self, ch: str, env: Envelope) -> None:
        handlers = [h for (c, role), hs in self._handlers.items()
                    if c == ch and (role == "*" or role == env.to_role)
                    for h in hs]
        if not handlers:
            with self._lock:
                self.stats["failed"] += 1
            self.dlq.append((env, "no_handler"))
            return
        for h in handlers:
            self._run_handler(h, env)

    def _run_handler(self, h: Handler, env: Envelope) -> None:
        for attempt in range(self.retries):
            try:
                h(env)
                with self._lock:
                    self.stats["delivered"] += 1
                return
            except Exception as exc:  # noqa: BLE001 - bus retry contract
                if attempt == self.retries - 1:
                    with self._lock:
                        self.stats["failed"] += 1
                    self.dlq.append((env, repr(exc)))
                else:
                    time.sleep(self.backoff * (2 ** attempt))

    # ---- request/reply (Spec 02 §3.5) ----
    def request(self, env: Envelope, timeout: float | None = None) -> Envelope:
        if env.type == "REQUEST":
            pass
        with self._cond:
            self.send(env)
            deadline = time.time() + (timeout if timeout is not None else config.REQUEST_DEFAULT_TIMEOUT_S)
            while env.msg_id not in self._replies:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError(f"no reply for {env.msg_id} ({env.type})")
                self._cond.wait(remaining)
            return self._replies.pop(env.msg_id)

    def respond(self, req: Envelope, payload: dict | None = None,
                from_role: str | None = None, from_id: str | None = None,
                to_role: str | None = None, to_id: str | None = None) -> Envelope:
        rep = Envelope(
            type="REPLY",
            from_role=from_role or req.to_role,
            from_id=from_id or req.to_id,
            to_role=to_role or req.from_role,
            to_id=to_id or req.from_id,
            task_id=req.task_id,
            group_id=req.group_id,
            correlation_id=req.correlation_id or req.msg_id,
            reply_to=req.msg_id,
            payload=payload or {},
        )
        with self._cond:
            self._replies[rep.correlation_id] = rep
            self._cond.notify_all()
        return rep

    def drain(self) -> None:
        """Block until the dispatch queue is idle (deterministic tests/demo)."""
        while True:
            with self._lock:
                active = self.stats["sent"] - self.stats["delivered"] - self.stats["failed"] - self.stats["deduped"]
            if active <= 0:
                return
            time.sleep(0.01)
