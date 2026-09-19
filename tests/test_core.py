"""Core engine tests — run with:  python tests/test_core.py

Covers Spec 01 (state machine, cancellation, resume), Spec 02 (bus), Spec 03
(memory isolation, permissions, audit) and Spec 04 (registry) plus the MVP flow.
"""
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workdesk import db  # noqa: E402
from workdesk.bus import MessageBus  # noqa: E402
from workdesk.envelope import Envelope  # noqa: E402
from workdesk.engine import Engine  # noqa: E402
from workdesk.memory import can_access  # noqa: E402
from workdesk.permissions import PermissionManager  # noqa: E402
from workdesk.runtime import ClarificationNeeded  # noqa: E402
from workdesk.states import ALLOWED, StateMachine, TaskState, TransitionError  # noqa: E402


def _engine(db_path=None):
    return Engine(db_path=db_path or Path(tempfile.mkdtemp()) / "test.db", auto_approve=True)


def _seed(e):
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}})
    e.seed_worker("worker-writer", "Writer Worker", {"writer.markdown": {"capability": "writer"}})


# ---------------- Spec 01: state machine ----------------
def test_state_machine():
    sm = StateMachine(task_id="t1")
    sm.transition(TaskState.ANALYZING, actor="MB")
    sm.transition(TaskState.READY, actor="QA")
    sm.transition(TaskState.RUNNING, actor="PM")
    sm.transition(TaskState.IN_QA, actor="PM")
    sm.transition(TaskState.COMPLETED, actor="QA")
    assert sm.state == TaskState.COMPLETED and len(sm.events) == 5
    try:
        sm.transition(TaskState.RUNNING)
        raise AssertionError("illegal transition should raise")
    except TransitionError:
        pass
    # terminal is final; stop allowed from any non-terminal state
    sm3 = StateMachine(task_id="t3")
    sm3.transition(TaskState.ANALYZING)
    sm3.transition(TaskState.CANCELLED, actor="USER")
    assert sm3.state == TaskState.CANCELLED
    # resume/restart transitions exist (used by engine.resume / recover_pending)
    assert (TaskState.PAUSED, TaskState.READY) in ALLOWED
    assert (TaskState.CANCELLED, TaskState.READY) in ALLOWED
    assert (TaskState.RUNNING, TaskState.READY) in ALLOWED


# ---------------- Spec 02: message bus ----------------
def test_bus_request_reply_and_dedup():
    bus = MessageBus()

    def handler(env):
        bus.respond(env, payload={"echo": env.payload.get("x")})

    bus.subscribe("default", "*", handler)
    req = Envelope(type="REQUEST", from_role="MB", from_id="mb", to_role="PM", to_id="pm",
                   payload={"x": 42})
    rep = bus.request(req, timeout=5)
    assert rep.payload == {"echo": 42}
    assert rep.reply_to == req.msg_id and rep.correlation_id == req.msg_id

    dup = Envelope(type="REQUEST", from_role="MB", from_id="mb", to_role="PM", to_id="pm",
                   payload={}, idempotency_key="k1")
    assert bus.send(dup) is True
    assert bus.send(dup) is False
    assert bus.stats["deduped"] == 1


# ---------------- Spec 03: memory isolation ----------------
def test_memory_isolation():
    e = _engine()
    ctx_w = {"own_group_id": "g1", "own_worker_id": "w1"}
    assert can_access("WORKER", "read", "GROUP", "g1", ctx_w)[0] is True
    assert can_access("WORKER", "read", "GROUP", "g2", ctx_w)[0] is False
    assert can_access("WORKER", "read", "PROJECT", "p1", ctx_w)[0] is False
    ctx_pm = {"own_project_id": "p1", "own_group_id": "g1"}
    assert can_access("PM", "read", "PROJECT", "p1", ctx_pm)[0] is True
    assert can_access("PM", "read", "PROJECT", "p2", ctx_pm)[0] is False
    assert can_access("PM", "read", "GLOBAL", "global", ctx_pm)[0] is False
    # cross-project: NEVER automatic, MB grants explicitly
    assert can_access("MB", "read", "PROJECT", "p9", {"grants": {}})[0] is False
    e.memory.grant_scope("MB", "mb-1", "PROJECT", "p9", granted_by="MB")
    ctx_mb = {"grants": e.memory.grants_for("MB", "mb-1")}
    assert can_access("MB", "read", "PROJECT", "p9", ctx_mb)[0] is True
    # memory record round-trip
    mem_id = e.memory.write("WORKER", "w1", "WORKER", "w1", "experience", "did X",
                            ctx={"own_worker_id": "w1"})
    rows, why = e.memory.read("WORKER", "WORKER", "w1", ctx={"own_worker_id": "w1"})
    assert rows and rows[0]["mem_id"] == mem_id and why == "ok"
    assert e.memory.read("WORKER", "WORKER", "w2", ctx={"own_worker_id": "w1"})[0] == []


# ---------------- Spec 03: permissions + approvals ----------------
def test_permission_resolution():
    pm = PermissionManager(db.init(), auto_approve=False)
    assert pm.resolve("WORKER", "read", "project:/x/a.txt", "FILESYSTEM")[0] == "AUTO"
    assert pm.resolve("WORKER", "create", "project:/x/b.txt", "FILESYSTEM")[0] == "NOTIFY"
    assert pm.resolve("WORKER", "modify", "project:config:settings.json", "FILESYSTEM")[0] == "ASK"
    assert pm.resolve("WORKER", "delete", "project:/tmp/x.tmp", "FILESYSTEM")[0] == "EXPLICIT"
    assert pm.resolve("WORKER", "read", "system:C:/Windows/x", "FILESYSTEM")[0] == "DENY"
    # most specific match wins
    pm.add_policy("WORKER", "read", "project:special:*", "FILESYSTEM", "", "ASK", "project")
    assert pm.resolve("WORKER", "read", "project:special:x", "FILESYSTEM")[0] == "ASK"
    assert pm.resolve("WORKER", "read", "project:/x/a.txt", "FILESYSTEM")[0] == "AUTO"
    # approval flow
    ap_id, level = pm.require_approval("WORKER", "w1", "delete", "project:/x", "FILESYSTEM")
    assert level == "EXPLICIT" and ap_id is not None
    pm.decide(ap_id, "APPROVED", "test")
    row = db.query_one("SELECT status FROM approvals WHERE approval_id=?", (ap_id,))
    assert row["status"] == "APPROVED"


# ---------------- Spec 04: registry ----------------
def test_registry_lifecycle_and_stats():
    e = _engine()
    wid = e.registry.register_worker(name="R1",
                                     skills=[{"skill_id": "s1", "primary": True, "capability": "data"}])
    assert e.registry.get_worker(wid)["status"] == "REGISTERED"
    e.registry.activate(wid)
    assert e.registry.get_worker(wid)["status"] == "AVAILABLE"
    assert any(w["worker_id"] == wid for w in e.registry.find_workers(["data"]))
    e.registry.record_result(wid, "t1", passed=True, exec_ms=100)
    e.registry.record_result(wid, "t2", passed=False, exec_ms=200)
    w = e.registry.get_worker(wid)
    assert w["tasks_completed"] == 2
    assert (w["qa_passed"], w["qa_failed"]) == (1, 1)
    assert abs(w["qa_pass_rate"] - 0.5) < 1e-9
    assert 0.0 < w["failure_rate"] < 1.0  # EWMA decayed, not raw


# ---------------- MVP flow: full pipeline + selective rework ----------------
def test_mvp_flow_with_rework():
    e = _engine()
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                  fail_once=["data.summarize"])
    e.seed_worker("worker-writer", "Writer Worker", {"writer.markdown": {"capability": "writer"}})
    out = e.project_dir / "r.md"
    dataset = {"region": ["East", "West", "North"], "q3": [120, 80, 100]}
    task = e.submit("Analyze the Q3 sales and save a summary report",
                    ctx={"inputs": {"dataset": dataset}, "save_path": out,
                         "output_type": "markdown"})
    assert task.state == TaskState.COMPLETED, task.state.value
    assert task.rework_count == 1 and task.result["qa_cycles"] == 1
    content = out.read_text(encoding="utf-8")
    assert "Total: 300" in content and "Summary" in content
    actions = [ev["action"] for ev in e.timeline(task.task_id)]
    assert any("rework" in a for a in actions)
    assert any("task_state:COMPLETED" in a for a in actions)
    w = e.registry.get_worker("worker-data")
    assert (w["qa_failed"], w["qa_passed"]) == (1, 1)   # first wrong + redo correct


# ---------------- QA-1 clarification loop ----------------
def test_clarification_loop():
    e = _engine()
    _seed(e)
    out = e.project_dir / "c.md"
    dataset = {"region": ["E"], "q3": [7]}
    try:
        e.submit("Help me with the Q3 sales data",
                 ctx={"inputs": {"dataset": dataset}, "save_path": out})
        raise AssertionError("expected ClarificationNeeded")
    except ClarificationNeeded as exc:
        assert "output_type" in exc.missing
        task_id = exc.task_id
    task = e.clarify(task_id, {"output_type": "markdown"})
    assert task.state == TaskState.COMPLETED
    assert "Total: 7" in out.read_text(encoding="utf-8")


# ---------------- Stop + resume ----------------
def test_cancellation_and_resume():
    e = _engine()
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                  sleep_skill={"data.summarize": 0.6})
    e.seed_worker("worker-writer", "Writer Worker", {"writer.markdown": {"capability": "writer"}})
    out = e.project_dir / "k.md"
    dataset = {"region": ["E"], "q3": [5]}
    result = {}

    def run():
        result["task"] = e.submit("Write a summary report",
                                  ctx={"inputs": {"dataset": dataset}, "save_path": out,
                                       "output_type": "markdown"})

    t = threading.Thread(target=run)
    t.start()
    assert e.workers["worker-data"]._started.wait(5)
    row = db.query_one("SELECT task_id FROM tasks ORDER BY created_ts DESC")
    task_id = row["task_id"]
    e.stop(task_id)
    t.join(5)
    assert result["task"].state == TaskState.CANCELLED
    # resume from checkpoint -> re-run -> completed
    task2 = e.resume(task_id)
    assert task2.state == TaskState.COMPLETED, task2.state.value
    assert out.exists()


# ---------------- restart recovery ----------------
def test_recover_pending():
    db_path = Path(tempfile.mkdtemp()) / "r.db"
    e1 = Engine(db_path=db_path, auto_approve=True)
    _seed(e1)
    out = e1.project_dir / "p.md"
    dataset = {"region": ["E"], "q3": [3]}
    task = e1.submit("Write a report",
                     ctx={"inputs": {"dataset": dataset}, "save_path": out,
                          "output_type": "markdown"})
    assert task.state == TaskState.COMPLETED
    db.reset()  # simulated shutdown
    e2 = Engine(db_path=db_path, auto_approve=True)
    assert e2.recover_pending() == []   # nothing pending
    # cancelled task survives in DB with its transition history
    hist = db.query("SELECT to_state FROM task_transitions WHERE task_id=?", (task.task_id,))
    assert [r["to_state"] for r in hist][-1] == "COMPLETED"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        db.reset()
        try:
            t()
            print(f"PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            import traceback
            traceback.print_exc()
            print(f"FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
