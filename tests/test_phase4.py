"""Phase-4 PM lifetime system tests (Spec 04 §5.3 + Spec 03 §4.5 + §16 Phase 4).

Covers: persistent PM identity across task groups, project/group memory,
task/group history, worker-performance records, evidence-gated lessons,
conventions, decisions, memory isolation, restart survival, and the PM history API.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workdesk import db  # noqa: E402
from workdesk import Engine, TaskState, ProjectManager, ClarificationNeeded  # noqa: E402


def _engine(auto_approve=True, project_dir=None):
    return Engine(db_path=Path(tempfile.mkdtemp()) / "p4.db", auto_approve=auto_approve,
                  project_dir=project_dir)


def _seed(e, fail_data=False):
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                  fail_once=["data.summarize"] if fail_data else None)
    e.seed_worker("worker-writer", "Writer Worker",
                  {"writer.markdown": {"capability": "writer"}})


def _ctx(pid="p4", save=True):
    c = {"project_id": pid, "out_dir": str(Path(tempfile.mkdtemp()))}
    if save:
        c["save_path"] = str(Path(c["out_dir"]) / "r.md")
    return c


# ---------------- persistent PM identity across task groups ----------------
def test_pm_is_persistent_across_groups():
    e = _engine()
    _seed(e)
    t1 = e.submit("Analyze the Q3 sales and save a summary report",
                  ctx={"project_id": "p4", "save_path": str(Path(tempfile.mkdtemp()) / "a.md"),
                       "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    t2 = e.submit("Analyze the Q4 sales and save a summary report",
                  ctx={"project_id": "p4", "save_path": str(Path(tempfile.mkdtemp()) / "b.md"),
                       "inputs": {"dataset": {"q3": [4, 5, 6]}}, "output_type": "markdown"})
    assert t1.state == TaskState.COMPLETED and t2.state == TaskState.COMPLETED
    pm = e.get_pm("p4")
    rec = e.registry.get_pm(pm.pm_id)
    assert rec["status"] == "AVAILABLE"
    # same PM instance, two task groups -> history accumulates
    assert sorted(rec["task_history"]) == sorted([t1.task_id, t2.task_id]), rec["task_history"]
    assert sorted(rec["group_history"]) == sorted([t1.group_id, t2.group_id])
    # different projects get different PMs
    pm_other = e.get_pm("other")
    assert pm_other.pm_id != pm.pm_id


# ---------------- worker performance recorded by the PM ----------------
def test_pm_records_worker_performance():
    e = _engine()
    _seed(e)
    e.submit("Analyze the Q3 sales and save a summary report",
             ctx={"project_id": "p4",
                  "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                  "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    rec = e.registry.get_pm(e.get_pm("p4").pm_id)
    perf = rec["worker_performance"]
    assert "worker-data" in perf and "worker-writer" in perf, perf
    assert perf["worker-data"]["qa_passed"] >= 1
    assert perf["worker-writer"]["tasks_completed"] >= 1


# ---------------- project knowledge + conventions ----------------
def test_pm_project_knowledge_and_conventions():
    e = _engine()
    _seed(e)
    e.submit("Analyze the Q3 sales and save a summary report",
             ctx={"project_id": "p4",
                  "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                  "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    pm = e.get_pm("p4")
    # PROJECT memory layer holds the task result + artifacts
    rows, why = e.memory.read("PM", "PROJECT", "p4", ctx={"own_project_id": "p4"})
    types = {r["type"] for r in rows}
    assert {"task_result", "artifact"} <= types, types
    # conventions: recurring output type is remembered
    rec = e.registry.get_pm(pm.pm_id)
    assert "output_type=markdown" in rec["conventions"], rec["conventions"]


# ---------------- lessons: evidence-gated pipeline ----------------
def test_pm_learns_lesson_from_rework():
    e = _engine()
    _seed(e, fail_data=True)      # data worker fails its FIRST attempt only
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p4",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    assert t.state == TaskState.COMPLETED
    assert t.result["qa_cycles"] == 1              # one rework happened
    lessons = e.registry.get_pm_lessons(e.get_pm("p4").pm_id)
    assert lessons, "PM should store a lesson after a rework"
    lesson = lessons[0]
    assert lesson["lesson_key"] == "data"
    assert lesson["evidence_count"] == 1
    assert lesson["status"] == "candidate"         # not yet promoted
    assert lesson["confidence"] in ("LOW", "MEDIUM")


def test_pm_lesson_evidence_gate_promotes():
    e = _engine()
    # two separate projects so each task reworks independently of the other
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                  fail_once=["data.summarize"])
    e.seed_worker("worker-writer", "Writer Worker",
                  {"writer.markdown": {"capability": "writer"}})
    for pid in ("p-a", "p-b"):
        e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                      fail_once=["data.summarize"])   # re-seed resets the one-shot failure
        t = e.submit("Analyze the Q3 sales and save a summary report",
                     ctx={"project_id": pid,
                          "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                          "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
        assert t.state == TaskState.COMPLETED and t.result["qa_cycles"] == 1
    pm = e.get_pm("p-a")
    lessons = e.registry.get_pm_lessons(pm.pm_id)
    keyed = {l["lesson_key"]: l for l in lessons}
    assert keyed["data"]["evidence_count"] == 1   # each PM aggregates its own evidence
    # force the SAME PM to see the failure pattern again -> promotion threshold
    for _ in range(2):
        e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                      fail_once=["data.summarize"])
        t = e.submit("Analyze the Q3 sales and save a summary report",
                     ctx={"project_id": "p-a",
                          "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                          "inputs": {"dataset": {"q3": [7, 8, 9]}}, "output_type": "markdown"})
        assert t.state == TaskState.COMPLETED and t.result["qa_cycles"] == 1
    lessons = e.registry.get_pm_lessons(pm.pm_id)
    keyed = {l["lesson_key"]: l for l in lessons}
    assert keyed["data"]["evidence_count"] == 3
    assert keyed["data"]["confidence"] == "HIGH"
    assert keyed["data"]["status"] == "stored"    # evidence gate crossed (>= 2)
    # the lesson carries its evidence refs (the tasks that produced it)
    assert len(keyed["data"]["refs"]) == 3


# ---------------- FAILED outcome also becomes a lesson ----------------
def test_pm_records_failed_outcome_lesson():
    e = _engine()
    pm = e.get_pm("p4")
    # unit-level check: a FAILED task records a lesson with the retry-limit text
    from workdesk import Task
    t = Task(task_id="t-fail", request_text="x", project_id="p4",
             spec={"components": [{"id": "x.y", "skill": "x.y", "capability": "x"}]})
    pm.record_after_task(t, _FakeGroup(), "FAILED", qa_cycles=3, rework_count=3)
    lessons = e.registry.get_pm_lessons(pm.pm_id)
    assert lessons and lessons[0]["evidence_count"] == 1
    assert "retry limit" in lessons[0]["content"]


class _FakeGroup:
    artifacts_manifest = []


# ---------------- decisions are logged ----------------
def test_pm_decisions_log():
    e = _engine()
    _seed(e, fail_data=True)
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p4",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    assert t.state == TaskState.COMPLETED and t.rework_count == 1
    rec = e.registry.get_pm(e.get_pm("p4").pm_id)
    decisions = [d for d in rec["decisions"] if d["decision"] == "rework"]
    assert decisions and decisions[0]["outcome"].startswith("reworked 1 cycle"), decisions


# ---------------- memory isolation: PM never auto-reads other projects ----------------
def test_pm_memory_isolation():
    e = _engine()
    _seed(e)
    e.submit("Analyze the Q3 sales and save a summary report",
             ctx={"project_id": "p4",
                  "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                  "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    pm_a = e.get_pm("p4")
    # same-PM reads of ITS OWN project memory work
    rows, why = e.memory.read("PM", "PROJECT", "p4", ctx={"own_project_id": "p4"})
    assert rows and why == "ok"
    # but reading another project's memory is denied (cross-project NEVER automatic)
    rows2, why2 = e.memory.read("PM", "PROJECT", "secret-project",
                                ctx={"own_project_id": "p4"})
    assert rows2 == [] and why2 == "PM scope denied", why2
    # and writing to it is denied too
    try:
        e.memory.write("PM", pm_a.pm_id, "PROJECT", "secret-project", "x", "y",
                       ctx={"own_project_id": "p4"})
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass


# ---------------- restart: PM identity and records survive ----------------
def test_pm_survives_restart():
    db.reset()
    db.init()
    dbp = Path(tempfile.mkdtemp()) / "restart.db"
    e1 = Engine(db_path=dbp, auto_approve=True)
    _seed(e1)
    e1.submit("Analyze the Q3 sales and save a summary report",
              ctx={"project_id": "p4",
                   "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                   "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    pm1 = e1.get_pm("p4")
    e2 = Engine(db_path=dbp, auto_approve=True)      # application restart
    pm2 = e2.get_pm("p4")
    assert pm2.pm_id == pm1.pm_id                    # same persistent identity
    profile = e2.pm_profile("p4")
    assert len(profile["task_history"]) == 1
    assert "worker-data" in profile["worker_performance"]
    assert "output_type=markdown" in profile["conventions"]
    assert profile["lessons"] == []                  # clean run -> no lessons


# ---------------- PM history API ----------------
def test_pm_history_api():
    e = _engine()
    _seed(e)
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p4",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"})
    hist = e.pm_history("p4")
    assert len(hist) == 1
    assert hist[0]["taskId"] == t.task_id
    assert hist[0]["state"] == "COMPLETED"
    assert hist[0]["result"]["qa_cycles"] == 0


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
