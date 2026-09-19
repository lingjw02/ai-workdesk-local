"""Phase-7 WorkDesk UI read-model tests (Engine queries only — pure reads).

Covers: task list with QA summary, full task detail (spec / group / state
machine / QA history / validation / audit), PM registry read model, virtual
office snapshot, and engine settings snapshot.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workdesk import db  # noqa: E402
from workdesk import Engine, TaskState  # noqa: E402


def _engine(auto_approve=True):
    return Engine(db_path=Path(tempfile.mkdtemp()) / "p7.db",
                  auto_approve=auto_approve,
                  project_dir=Path(tempfile.mkdtemp()) / "ws")


def _seed(e, fail_data=False):
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                  fail_once=["data.summarize"] if fail_data else None)
    e.seed_worker("worker-writer", "Writer Worker",
                  {"writer.markdown": {"capability": "writer"}})


def _run_completed(e, pid="p7"):
    return e.submit("Analyze the Q3 sales and save a summary report",
                    ctx={"project_id": pid,
                         "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                         "inputs": {"dataset": {"q3": [1, 2, 3]}},
                         "output_type": "markdown"})


# ---------------- task list read model ----------------
def test_list_tasks_includes_qa_summary():
    e = _engine()
    _seed(e, fail_data=True)
    t = _run_completed(e)
    assert t.state == TaskState.COMPLETED
    tasks = e.list_tasks()
    assert len(tasks) == 1
    row = tasks[0]
    assert row["task_id"] == t.task_id
    assert row["state"] == "COMPLETED"
    assert row["qa_cycles"] == 1                 # failed once, passed once
    assert row["qa_score"] == 1.0                # pass cycle scored 1.0
    assert row["rework_count"] == 1
    assert {a["component"] for a in row["artifacts"]} == {"data.summarize", "writer.markdown"}


def test_list_tasks_filters_by_project_and_orders():
    e = _engine()
    _seed(e)
    _run_completed(e, pid="a")
    _run_completed(e, pid="b")
    only_a = e.list_tasks(project_id="a")
    assert len(only_a) == 1 and only_a[0]["project_id"] == "a"
    both = e.list_tasks(limit=10)
    assert len(both) == 2 and both[0]["created_ts"] >= both[1]["created_ts"]


def test_list_tasks_without_result_has_none_score():
    e = _engine()
    _seed(e)
    from workdesk.runtime import ClarificationNeeded
    try:
        e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p7", "save_path": "r.md",
                      "inputs": {}, "output_type": "markdown"})
    except ClarificationNeeded:
        pass                                        # task exists in CLARIFYING state
    rows = e.list_tasks()
    assert rows and any(r["state"] == "CLARIFYING" for r in rows)
    for row in rows:
        if row["state"] not in ("COMPLETED", "FAILED"):
            assert row["qa_score"] is None and row["qa_cycles"] == 0


# ---------------- task detail read model ----------------
def test_task_detail_full_read_model():
    e = _engine()
    _seed(e, fail_data=True)
    t = _run_completed(e)
    d = e.task_detail(t.task_id)
    assert d["task"]["state"] == "COMPLETED"
    assert d["task"]["spec"]["output_type"] == "markdown"
    assert d["task"]["result"]["qa_score"] == 1.0
    assert d["group"]["members"] and d["group"]["artifacts"]
    # state machine events + audit timeline + QA history are all present
    assert d["transitions"] and d["transitions"][0]["to_state"] == "ANALYZING"
    assert any(x["action"] == "rework" for x in d["timeline"])
    assert any(v["stage"] == "QA1" for v in d["qa_history"])
    assert any(v["stage"] == "QA2" and not v["passed"] for v in d["qa_history"])
    assert d["validation"]["state"] == "COMPLETED"


def test_task_detail_404():
    e = _engine()
    try:
        e.task_detail("no-such-task")
        assert False, "expected KeyError"
    except KeyError:
        pass


# ---------------- PM read model ----------------
def test_list_pms_read_model():
    e = _engine()
    _seed(e, fail_data=True)
    _run_completed(e)
    pms = e.list_pms()
    assert len(pms) == 1
    pm = pms[0]
    assert pm["project_id"] == "p7"
    assert pm["task_count"] == 1
    # the single QA failure produced a lesson CANDIDATE (evidence=1, not yet HIGH)
    assert pm["lessons"] and pm["lessons"][0]["confidence"] != "HIGH"
    assert isinstance(pm["knowledge"], list)
    assert isinstance(pm["worker_performance"], dict)
    # a retry-limit failure stores a lesson -> visible in the read model
    db.reset()                                       # isolate: db is a module-level singleton
    e2 = _engine()
    e2.seed_worker("worker-bad", "Bad Data Worker", {"data.summarize": {"capability": "data"}})
    _orig = e2.workers["worker-bad"]._run_skill

    def _always_wrong(task, group, comp, inject_error=False):
        if comp.get("skill") == "data.summarize":
            ds = (task.spec.get("inputs") or {}).get("dataset") or {}
            return {"kind": "computation", "total": sum(ds.get("q3") or []) + 10,
                    "regions": ds.get("region")}
        return _orig(task, group, comp, inject_error)

    e2.workers["worker-bad"]._run_skill = _always_wrong
    e2.seed_worker("worker-writer", "Writer Worker",
                   {"writer.markdown": {"capability": "writer"}})
    t2 = e2.submit("Analyze the Q3 sales and save a summary report",
                   ctx={"project_id": "p7b",
                        "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                        "inputs": {"dataset": {"q3": [1, 2, 3]}},
                        "output_type": "markdown"})
    assert t2.state == TaskState.FAILED
    pms2 = e2.list_pms()
    pm2 = [p for p in pms2 if p["project_id"] == "p7b"][0]
    assert pm2["lessons"] and any("retry limit" in l["content"] for l in pm2["lessons"])


# ---------------- virtual office snapshot ----------------
def test_virtual_office_snapshot():
    e = _engine()
    _seed(e, fail_data=True)
    _run_completed(e)
    vo = e.virtual_office()
    assert {w["id"] for w in vo["workers"]} == {"worker-data", "worker-writer"}
    data_w = [w for w in vo["workers"] if w["id"] == "worker-data"][0]
    assert data_w["stats"]["times_triggered"] == 2
    assert data_w["stats"]["qa_failed"] == 1 and data_w["stats"]["qa_passed"] == 1
    assert data_w["capabilities"] == ["data"]
    assert vo["task_states"].get("COMPLETED") == 1
    assert vo["pending_approvals"] == 0
    assert vo["recent_activity"]


def test_virtual_office_counts_pending_approvals():
    e = _engine(auto_approve=False)
    e.seed_worker("worker-fs", "FS Worker", {"fs.ops": {"capability": "fileops"}})
    out = e.project_dir / "delete_me.txt"
    out.write_text("x", encoding="utf-8")
    e.execute_tool("worker-fs", "fs.delete", "delete", {"path": str(out)})  # ASK -> PENDING
    vo = e.virtual_office()
    assert vo["pending_approvals"] == 1


# ---------------- settings snapshot ----------------
def test_settings_snapshot():
    e = _engine()
    s = e.settings_snapshot()
    assert s["max_rework_cycles"] == 3
    assert s["auto_approve"] is True
    assert s["db_path"] != "(in-memory)"
    assert set(s["counts"]) >= {"tasks", "pms", "workers", "skills", "lessons", "qa_verdicts"}


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
