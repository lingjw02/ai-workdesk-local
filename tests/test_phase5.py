"""Phase-5 Tool control tests (Spec §16 Phase 5 + Spec 03 §4.6).

Covers: tool catalog, filesystem read/write/delete through the permission
gate, path-traversal containment, approval-gated delete/terminal, terminal
safety blacklist, worker tool authorization (capability != permission),
browser stubs, and the audit trail for every tool action.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workdesk import db  # noqa: E402
from workdesk import Engine, ToolError  # noqa: E402


def _engine(auto_approve=True):
    return Engine(db_path=Path(tempfile.mkdtemp()) / "p5.db",
                  auto_approve=auto_approve,
                  project_dir=Path(tempfile.mkdtemp()) / "ws")


def _seed(e, tools=None, name="File Worker"):
    e.seed_worker("w1", name, {"fs.tool": {"capability": "fs"}})
    if tools is not None:
        e.registry.register_worker(worker_id="w1", name=name,
                                   role_class="WORKER", tools=tools,
                                   skills=[{"skill_id": "s1", "primary": True,
                                            "capability": "fs"}],
                                   personality={}, behavior_rules=[],
                                   permissions={}, memory_rules={})
    return "w1"


def _proj_path(e, name):
    p = e.project_dir / name
    return str(p)


# ---------------- catalog ----------------
def test_tool_catalog():
    e = _engine()
    cats = {t["name"]: t for t in e.tool_catalog()}
    for expected in ("fs.list", "fs.read", "fs.write", "fs.mkdir", "fs.delete",
                     "terminal.run", "browser.open", "browser.search"):
        assert expected in cats, expected
    assert cats["browser.open"]["stub"] is True
    assert cats["fs.read"]["stub"] is False


# ---------------- filesystem: read AUTO / write NOTIFY ----------------
def test_fs_write_notify_and_read_auto():
    e = _engine()
    wid = _seed(e)
    p = _proj_path(e, "notes.txt")
    r = e.execute_tool(wid, "fs.write", "write", {"path": p, "content": "hello p5"})
    assert r.ok and r.level == "NOTIFY" and r.notify is True
    assert r.files_changed == [p] and r.result["created"] is True
    r2 = e.execute_tool(wid, "fs.read", "read", {"path": p})
    assert r2.ok and r2.level == "AUTO"
    assert r2.result["content"] == "hello p5"
    # overwriting an existing file still reports the file and level
    r3 = e.execute_tool(wid, "fs.write", "write", {"path": p, "content": "v2"})
    assert r3.ok and r3.result["created"] is False
    # audit trail records both actions with files_changed
    evs = [a for a in e.permissions.timeline() if a["action"] == "tool_executed"]
    assert any(ev["tool"] == "fs.write" and ev["files_changed_json"] and "notes.txt"
               in ev["files_changed_json"] for ev in evs)


# ---------------- containment: no escaping the workspace ----------------
def test_fs_escape_denied():
    e = _engine()
    wid = _seed(e)
    outside = str(Path(tempfile.mkdtemp()) / "evil.txt")
    for bad in (outside, "../../escape.txt", "..\\..\\escape2.txt"):
        try:
            e.execute_tool(wid, "fs.write", "write",
                           {"path": bad, "content": "x"})
            raise AssertionError(f"escape should be denied: {bad}")
        except ToolError as ex:
            assert ex.code in ("SCOPE_DENIED", "POLICY_DENIED"), ex.code


# ---------------- delete: ASK gate ----------------
def test_fs_delete_requires_approval_when_not_autoapprove():
    e = _engine(auto_approve=False)
    wid = _seed(e)
    p = _proj_path(e, "tmp.txt")
    assert e.execute_tool(wid, "fs.write", "write",
                          {"path": p, "content": "x"}).ok
    r = e.execute_tool(wid, "fs.delete", "delete", {"path": p})
    assert r.ok is False and r.error == "approval required (PENDING)"
    assert r.approval_id is not None
    assert Path(p).exists()                     # not executed while PENDING
    e.permissions.decide(r.approval_id, "APPROVED", "user approved")
    r2 = e.execute_tool(wid, "fs.delete", "delete", {"path": p})
    assert r2.ok and r2.level == "ASK"
    assert not Path(p).exists()


def test_fs_delete_autoapprove_executes():
    e = _engine(auto_approve=True)
    wid = _seed(e)
    p = _proj_path(e, "tmp.txt")
    e.execute_tool(wid, "fs.write", "write", {"path": p, "content": "x"})
    r = e.execute_tool(wid, "fs.delete", "delete", {"path": p})
    assert r.ok and not Path(p).exists()


# ---------------- terminal: safe command + blacklist + approval gate ----------------
def test_terminal_run_safe_command():
    e = _engine()
    wid = _seed(e, tools=[{"tool": "TERMINAL", "permissions": {"run": True}}])
    r = e.execute_tool(wid, "terminal.run", "run", {"command": "echo p5-ok"})
    assert r.ok
    assert r.result["exit_code"] == 0
    assert "p5-ok" in r.result["stdout"]


def test_terminal_blacklist_rejects_dangerous():
    e = _engine()                                  # auto-approve ON: gate would pass
    wid = _seed(e, tools=[{"tool": "TERMINAL", "permissions": {"run": True}}])
    for bad in ("del /s /q C:\\Windows", "rm -rf /", "format c:", "shutdown /s"):
        try:
            e.execute_tool(wid, "terminal.run", "run", {"command": bad})
            raise AssertionError(f"dangerous command should be rejected: {bad}")
        except ToolError as ex:
            assert ex.code == "DANGEROUS_COMMAND", ex.code


def test_terminal_requires_approval_when_not_autoapprove():
    e = _engine(auto_approve=False)
    wid = _seed(e, tools=[{"tool": "TERMINAL", "permissions": {"run": True}}])
    r = e.execute_tool(wid, "terminal.run", "run", {"command": "echo hi"})
    assert r.ok is False and r.approval_id is not None
    e.permissions.decide(r.approval_id, "APPROVED")
    r2 = e.execute_tool(wid, "terminal.run", "run", {"command": "echo hi"})
    assert r2.ok and r2.result["exit_code"] == 0


# ---------------- capability != permission ----------------
def test_worker_without_tool_denied():
    e = _engine()
    wid = _seed(e, tools=[{"tool": "BROWSER", "permissions": {"open": True}}])
    try:
        e.execute_tool(wid, "fs.read", "read", {"path": _proj_path(e, "x")})
        raise AssertionError("worker without fs tools must be denied")
    except ToolError as ex:
        assert ex.code == "WORKER_TOOL_DENIED"
    # BROWSER is granted, so the stub runs
    r = e.execute_tool(wid, "browser.open", "open", {"url": "https://example.com"})
    assert r.ok and r.stub is True


def test_worker_fs_class_grant():
    e = _engine()
    wid = _seed(e)                                # default FILESYSTEM class grant
    r = e.execute_tool(wid, "fs.mkdir", "mkdir", {"path": _proj_path(e, "sub")})
    assert r.ok and r.level == "NOTIFY"
    r2 = e.execute_tool(wid, "fs.list", "list", {"path": str(e.project_dir)})
    assert r2.ok and any(x["name"] == "sub" for x in r2.result["entries"])


def test_worker_cannot_touch_system_scope():
    e = _engine()
    wid = _seed(e)
    sysfile = Path(tempfile.mkdtemp()) / "sys.txt"
    sysfile.write_text("secrets", encoding="utf-8")
    for tool, action, params in (("fs.read", "read", {"path": str(sysfile)}),
                                 ("fs.delete", "delete", {"path": str(sysfile)})):
        try:
            e.execute_tool(wid, tool, action, params)
            raise AssertionError(f"WORKER must be blocked from system scope: {tool}")
        except ToolError as ex:
            assert ex.code == "POLICY_DENIED", ex.code
    # the MB, however, holds the EXPLICIT system-delete policy
    r = e.tools.execute("MB", "mb.1", "fs.delete", "delete",
                        {"path": str(sysfile)}, task_id=None)
    assert r.ok and r.level == "EXPLICIT"
    assert not sysfile.exists()


# ---------------- browser stubs ----------------
def test_browser_stub_labelled():
    e = _engine()
    wid = _seed(e, tools=[{"tool": "BROWSER", "permissions": {"open": True}}])
    r = e.execute_tool(wid, "browser.search", "search", {"query": "AI WorkDesk"})
    assert r.ok and r.stub is True
    assert "Phase-5 stub" in r.result["note"]
    assert any(a["action"] == "tool_stub" for a in e.permissions.timeline())


# ---------------- unknown tool ----------------
def test_unknown_tool():
    e = _engine()
    wid = _seed(e)
    try:
        e.execute_tool(wid, "nope.nope", "run", {})
        raise AssertionError("unknown tool must raise")
    except ToolError as ex:
        assert ex.code == "UNKNOWN_TOOL"


# ---------------- approval records persist ----------------
def test_approval_record_persisted():
    e = _engine(auto_approve=False)
    wid = _seed(e)
    p = _proj_path(e, "keep.txt")
    e.execute_tool(wid, "fs.write", "write", {"path": p, "content": "x"})
    r = e.execute_tool(wid, "fs.delete", "delete", {"path": p})
    from workdesk import db as _db
    row = _db.query_one("SELECT * FROM approvals WHERE approval_id=?",
                        (r.approval_id,))
    assert row is not None and row["status"] == "PENDING"
    assert row["tool"] == "fs.delete" and row["level"] == "ASK"


def _all():
    import traceback
    failed = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        try:
            db.reset()
            db.init()
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_all())
