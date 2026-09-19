"""Phase 5: Tool control layer (Spec §16 Phase 5 + Spec 03 §4.6).

Tools are capabilities; permissions are a separate question. A worker may
hold a tool without holding the right to use it on a given resource: every
invocation resolves the permission matrix (most-specific policy wins, deny by
default), may raise an approval (ASK / EXPLICIT), and is audit-logged as
`tool_executed` with `files_changed` — never chain-of-thought.

Phase-5 scope: filesystem (list/read/write/mkdir/delete), a sandboxed
terminal runner (command blacklist + approval gate), and browser stubs.
Real browser/VS Code/Office tools are Phase 7+; each stub is labelled.
"""
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import db, ids


class ToolError(Exception):
    """Tool invocation failed (unknown tool, policy denial, worker not
    authorized, dangerous terminal command, ...)."""

    def __init__(self, message: str, code: str = "TOOL_ERROR"):
        super().__init__(message)
        self.code = code


@dataclass
class ToolResult:
    ok: bool
    tool: str
    action: str
    params: dict
    level: str = "AUTO"
    result: dict = field(default_factory=dict)
    approval_id: str | None = None
    notify: bool = False
    error: str | None = None
    files_changed: list = field(default_factory=list)
    stub: bool = False

    def to_dict(self) -> dict:
        return {"ok": self.ok, "tool": self.tool, "action": self.action,
                "level": self.level, "result": self.result,
                "approval_id": self.approval_id, "notify": self.notify,
                "error": self.error, "files_changed": self.files_changed,
                "stub": self.stub}


@dataclass
class ToolSpec:
    name: str
    description: str
    handler: callable
    stub: bool = False


# ---------------- path safety ----------------
def resolve_path(engine, raw: str) -> tuple[Path, str, str]:
    """Normalize a path and classify its scope: project (inside the engine
    workspace root) or system (outside). Relative paths anchor at the project
    dir. Never follows symlinks out of the workspace by design."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = engine.project_dir / p
    p = p.resolve()
    root = engine.project_dir.resolve()
    try:
        rel = p.relative_to(root)
        return p, "project", str(rel)
    except ValueError:
        return p, "system", str(p)


# ---------------- filesystem tools ----------------
def _fs_list(engine, params: dict) -> tuple[dict, list]:
    p, scope, rel = resolve_path(engine, params.get("path", "."))
    if not p.exists():
        raise ToolError(f"path does not exist: {p}", code="PATH_MISSING")
    if p.is_file():
        return {"path": str(p), "scope": scope, "type": "file",
                "size": p.stat().st_size}, [str(p)]
    entries = []
    for child in sorted(p.iterdir()):
        entries.append({"name": child.name,
                        "type": "dir" if child.is_dir() else "file",
                        "size": child.stat().st_size if child.is_file() else None})
    return {"path": str(p), "scope": scope, "type": "dir", "entries": entries}, [str(p)]


def _fs_read(engine, params: dict) -> tuple[dict, list]:
    p, scope, rel = resolve_path(engine, params.get("path", ""))
    if not p.is_file():
        raise ToolError(f"not a file: {p}", code="PATH_MISSING")
    if p.stat().st_size > 1024 * 1024:
        raise ToolError("file too large to read (>1MB)", code="TOO_LARGE")
    data = p.read_bytes()
    if b"\x00" in data[:4096]:
        return {"path": str(p), "scope": scope, "binary": True,
                "size": len(data)}, [str(p)]
    return {"path": str(p), "scope": scope, "content": data.decode("utf-8", errors="replace"),
            "size": len(data)}, [str(p)]


def _fs_write(engine, params: dict) -> tuple[dict, list]:
    p, scope, rel = resolve_path(engine, params.get("path", ""))
    # scope is adjudicated by the permission matrix (single point of decision):
    # WORKER create on system:* is BLOCKED / denied by default; project create
    # is NOTIFY. The handler itself never re-decides scope.
    if p.exists() and p.is_dir():
        raise ToolError(f"path is a directory: {p}", code="BAD_PATH")
    p.parent.mkdir(parents=True, exist_ok=True)
    content = params.get("content", "")
    if not isinstance(content, str):
        raise ToolError("content must be text", code="BAD_CONTENT")
    existed = p.exists()
    p.write_text(content, encoding="utf-8")
    return {"path": str(p), "scope": scope, "bytes": len(content.encode("utf-8")),
            "created": not existed}, [str(p)]


def _fs_mkdir(engine, params: dict) -> tuple[dict, list]:
    p, scope, rel = resolve_path(engine, params.get("path", ""))
    p.mkdir(parents=True, exist_ok=True)
    return {"path": str(p), "scope": scope, "created": p.is_dir()}, [str(p)]


def _fs_delete(engine, params: dict) -> tuple[dict, list]:
    p, scope, rel = resolve_path(engine, params.get("path", ""))
    if not p.exists():
        raise ToolError(f"path does not exist: {p}", code="PATH_MISSING")
    if p.is_dir():
        # never delete whole directories through this tool — rework scope first
        raise ToolError("directory deletion is not enabled; delete files only",
                        code="DIR_DELETE_DISABLED")
    p.unlink()
    return {"path": str(p), "deleted": True}, [str(p)]


# ---------------- terminal tool ----------------
# Hard reject-list: regardless of the resolved policy level, these patterns
# are never executed by the sandboxed runner (Phase 5 guardrail; a real
# sandbox/VM is a Phase 8+ item).
_DANGEROUS_CMDS = [
    "rm -rf", "rm -fr", "rd /s", "del /s", "del /f", "erase /s",
    "format ", "diskpart", "shutdown", "reg delete", "net user", "net localgroup",
    "Remove-Item", ":(){", "> nul", "taskkill", "wmic process", "mkfs",
    "dd if=", "sudo ", "powershell -e", "certutil", "bitsadmin",
]

_TERMINAL_TIMEOUT_S = 15


def _terminal_run(engine, params: dict) -> tuple[dict, list]:
    cmd = params.get("command", "")
    if not cmd or not isinstance(cmd, str):
        raise ToolError("command must be a non-empty string", code="BAD_COMMAND")
    norm = " ".join(cmd.lower().split())
    for bad in _DANGEROUS_CMDS:
        if bad in norm:
            raise ToolError(f"command rejected by the safety blacklist: {bad}",
                            code="DANGEROUS_COMMAND")
    try:
        r = subprocess.run(["cmd", "/c", cmd], cwd=str(engine.project_dir),
                           capture_output=True, text=True, timeout=_TERMINAL_TIMEOUT_S,
                           errors="replace")
    except subprocess.TimeoutExpired:
        raise ToolError(f"command timed out after {_TERMINAL_TIMEOUT_S}s",
                        code="TIMEOUT")
    return {"exit_code": r.returncode,
            "stdout": (r.stdout or "")[:8000],
            "stderr": (r.stderr or "")[:2000]}, []


# ---------------- browser stubs (Phase 7: real browser control) ----------------
def _browser_open(engine, params: dict) -> tuple[dict, list]:
    return {"url": params.get("url", ""),
            "note": "Phase-5 stub: real browser control lands in Phase 7."}, []


def _browser_search(engine, params: dict) -> tuple[dict, list]:
    return {"query": params.get("query", ""),
            "note": "Phase-5 stub: real web search lands in Phase 7."}, []


# ---------------- registry ----------------
class ToolRegistry:
    def __init__(self, engine):
        self.engine = engine
        self._tools: dict[str, ToolSpec] = {}
        self._register_builtins()
        self._seed_tool_policies()

    # ---- registration ----
    def _register_builtins(self) -> None:
        specs = [
            ToolSpec("fs.list", "List a directory or stat a file", _fs_list),
            ToolSpec("fs.read", "Read a text file (<=1MB)", _fs_read),
            ToolSpec("fs.write", "Write a text file inside the project workspace", _fs_write),
            ToolSpec("fs.mkdir", "Create a directory inside the project workspace", _fs_mkdir),
            ToolSpec("fs.delete", "Delete a file inside the project workspace (approval-gated)", _fs_delete),
            ToolSpec("terminal.run", "Run a shell command in the project dir (blacklist + approval gate)", _terminal_run),
            ToolSpec("browser.open", "Open a URL (stub)", _browser_open, stub=True),
            ToolSpec("browser.search", "Search the web (stub)", _browser_search, stub=True),
        ]
        for s in specs:
            self._tools[s.name] = s

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list(self) -> list[dict]:
        return [{"name": s.name, "description": s.description, "stub": s.stub}
                for s in sorted(self._tools.values(), key=lambda x: x.name)]

    # ---- Phase 5 tool policies (most-specific match wins over defaults) ----
    def _seed_tool_policies(self) -> None:
        p = self.engine.permissions
        p.add_policy("WORKER", "delete", "project:*", "*", "", "ASK", "project")
        p.add_policy("WORKER", "execute", "terminal:*", "*", "", "ASK", "system")

    # ---- worker authorization: holding a tool != being able to use it ----
    def worker_authorized(self, worker_id: str, tool_name: str) -> bool:
        rec = self.engine.registry.get_worker(worker_id)
        if rec is None:
            return False
        tools = rec.get("tools") or []
        for t in tools:
            name = t.get("tool") if isinstance(t, dict) else t
            if name == "*" or name == tool_name:
                return True
            if name == "FILESYSTEM" and tool_name.startswith("fs."):
                return True
            if name == "TERMINAL" and tool_name.startswith("terminal."):
                return True
            if name == "BROWSER" and tool_name.startswith("browser."):
                return True
        return False

    # ---- execution through the permission gate ----
    def _resource_for(self, tool_name: str, params: dict) -> str:
        if tool_name.startswith("fs."):
            p, scope, rel = resolve_path(self.engine, params.get("path", ""))
            return f"{scope}:{rel}"
        if tool_name.startswith("terminal."):
            return "terminal:run"
        return f"{tool_name}:{params.get('action', 'run')}"

    def _action_for(self, tool_name: str, action: str) -> str:
        if tool_name.startswith("fs."):
            return {"list": "read", "read": "read", "write": "create",
                    "mkdir": "create", "delete": "delete"}.get(action, action)
        if tool_name.startswith("terminal."):
            return "execute"
        return action

    def _last_approval(self, actor_role: str, actor_id: str, action: str,
                       resource: str, tool: str) -> tuple[str | None, str | None]:
        """Most recent approval for this exact action: PENDING blocks (no
        duplicate requests), APPROVED releases the gate, DENIED lets a new
        request be raised."""
        rows = db.query(
            "SELECT approval_id, status FROM approvals WHERE requester_role=? "
            "AND requester_id=? AND action=? AND resource=? AND tool=? "
            "ORDER BY rowid DESC LIMIT 1",
            (actor_role, actor_id, action, resource, tool))
        if not rows:
            return None, None
        return rows[0]["status"], rows[0]["approval_id"]

    def execute(self, actor_role: str, actor_id: str, tool_name: str, action: str,
                params: dict, worker_id: str | None = None,
                task_id: str | None = None) -> ToolResult:
        spec = self.get(tool_name)
        if spec is None:
            raise ToolError(f"unknown tool: {tool_name}", code="UNKNOWN_TOOL")
        if worker_id is not None and not self.worker_authorized(worker_id, tool_name):
            self.engine.permissions.audit(actor_role, actor_id, "tool_denied",
                                          tool=tool_name, reason=f"worker {worker_id} "
                                          "not authorized for this tool", task_id=task_id)
            raise ToolError(f"worker {worker_id} is not authorized for {tool_name}",
                            code="WORKER_TOOL_DENIED")
        if spec.stub:
            result, changed = spec.handler(self.engine, params)
            self.engine.permissions.audit(actor_role, actor_id, "tool_stub",
                                          tool=tool_name,
                                          reason=str(result.get("note", "")),
                                          task_id=task_id)
            return ToolResult(ok=True, tool=tool_name, action=action, params=params,
                              result=result, files_changed=changed, stub=True)
        resource = self._resource_for(tool_name, params)
        action_k = self._action_for(tool_name, action)
        level, policy = self.engine.permissions.resolve(actor_role, action_k, resource, tool_name)
        if level == "DENY":
            self.engine.permissions.audit(actor_role, actor_id, "tool_denied",
                                          tool=tool_name, reason=f"{action_k} {resource}",
                                          task_id=task_id)
            raise ToolError(f"{tool_name} {action_k} on {resource} denied by policy "
                            "(deny by default)", code="POLICY_DENIED")
        if level in ("ASK", "EXPLICIT"):
            status, approval_id = self._last_approval(actor_role, actor_id,
                                                      action_k, resource, tool_name)
            if status == "PENDING":
                return ToolResult(ok=False, tool=tool_name, action=action, params=params,
                                  level=level, approval_id=approval_id,
                                  error="approval required (PENDING)")
            if status != "APPROVED":
                approval_id, _ = self.engine.permissions.require_approval(
                    actor_role, actor_id, action_k, resource, tool_name, task_id)
                if not self.engine.permissions.auto_approve:
                    return ToolResult(ok=False, tool=tool_name, action=action, params=params,
                                      level=level, approval_id=approval_id,
                                      error="approval required (PENDING)")
        result, changed = spec.handler(self.engine, params)
        self.engine.permissions.audit(actor_role, actor_id, "tool_executed", tool=tool_name,
                                      files_changed=changed,
                                      reason=f"{action_k} {resource}", task_id=task_id)
        return ToolResult(ok=True, tool=tool_name, action=action, params=params,
                          level=level, result=result, notify=level == "NOTIFY",
                          files_changed=changed)
