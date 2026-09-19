"""Phase-2 Main Brain tests — run with:  python tests/test_phase2.py

Covers the Phase-2 intelligence layer (Spec §16 Phase 2):
structured requirement understanding, enhanced QA-1 (ambiguity / contradiction /
capability-gap feasibility), simple/complex classification, stats-ranked worker
selection, team-based Task Group creation, permission planning, and
global-memory preference consultation + evidence-gated learning.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workdesk import db  # noqa: E402
from workdesk.engine import Engine  # noqa: E402
from workdesk.runtime import ClarificationNeeded  # noqa: E402
from workdesk.states import TaskState  # noqa: E402


def _engine(auto_approve=True):
    return Engine(db_path=Path(tempfile.mkdtemp()) / "p2.db", auto_approve=auto_approve)


def _seed(e):
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}})
    e.seed_worker("worker-writer", "Writer Worker", {"writer.markdown": {"capability": "writer"}})


def _ctx(dataset=None, **extra):
    c = {"project_id": "p2", "out_dir": str(Path(tempfile.mkdtemp()))}
    if dataset is not None:
        c["inputs"] = {"dataset": dataset}
    c.update(extra)
    return c


# ---------------- structured requirement understanding ----------------
def test_requirement_spec_structure():
    e = _engine()
    _seed(e)
    spec = e.mb.intelligence.analyze(
        "Analyze the Q3 sales and save a summary report", _ctx({"q3": [1, 2, 3]}), None, e)
    assert spec["intent"] == "execute"
    assert spec["output_type"] == "report"
    assert spec["needs_data"] is True
    assert any(c["id"] == "data.summarize" for c in spec["components"])
    assert any(c["id"] == "writer.markdown" for c in spec["components"])
    assert spec["save_path"] and spec["save_path"].endswith("report.md")
    assert any(c["id"] == "file_exists" for c in spec["criteria"])
    assert spec["risk_level"] == "low"
    assert spec["model_hint"] == "auto"


def test_analyze_request_preview():
    e = _engine()
    _seed(e)
    out = e.analyze_request("Analyze the Q3 sales and save a summary report",
                            ctx=_ctx({"q3": [1, 2, 3]}))
    assert out["complexity"] == "complex"
    assert out["spec"]["team_plan"]["data.summarize"] == "worker-data"
    assert out["qa1"]["pass"] is True
    # preview does not create any task
    assert db.query("SELECT COUNT(*) AS n FROM tasks")[0]["n"] == 0


# ---------------- QA-1: ambiguity + contradiction + feasibility ----------------
def test_qa1_ambiguity_detection():
    e = _engine()
    _seed(e)
    spec = e.mb.intelligence.analyze(
        "分析一下这个数据集，写几个要点", _ctx({"q3": [1, 2, 3]}), None, e)
    v1 = e.mb.intelligence.qa1(spec, e)
    assert v1["pass"] is False
    assert any("vague" in a for a in v1["ambiguities"])


def test_qa1_contradiction_detection():
    e = _engine()
    _seed(e)
    spec = e.mb.intelligence.analyze(
        "Write a Python script and PPT slides about it", _ctx(), None, e)
    v1 = e.mb.intelligence.qa1(spec, e)
    assert v1["pass"] is False
    assert any("conflict" in c for c in v1["contradictions"])


def test_qa1_capability_gap_feasibility():
    # production path (auto_approve=False): a capability gap must NOT auto-create
    # a worker; MB surfaces it for clarification and fails honestly when insisted on.
    # (auto-fill behaviour is covered by tests/test_phase3.py)
    e = _engine(auto_approve=False)
    _seed(e)                      # no slides/excel/email workers seeded
    try:
        e.submit("Build a slide deck about the project", ctx=_ctx())
        raise AssertionError("expected ClarificationNeeded for capability gap")
    except ClarificationNeeded as exc:
        gaps = (exc.verdict or {}).get("feasibility", {}).get("gaps") or []
        assert any("slides" in g for g in gaps), gaps
        task_id = exc.task_id
    assert "w-slides" not in e.workers, "capability gap must not auto-create without approval"
    # insisting on the unsupported output -> honest FAILED (QA1_FAIL_FINAL)
    t = e.clarify(task_id, {"output_type": "slides"})
    assert t.state == TaskState.FAILED
    # a NEW task switching to a supported output -> completes
    t2 = e.submit("Build a slide deck about the project", ctx=_ctx(),
                  answers={"output_type": "report"})
    assert t2.state == TaskState.COMPLETED, t2.state.value


# ---------------- simple / complex classification ----------------
def test_classification_simple_vs_complex():
    e = _engine()
    _seed(e)
    assert e.mb.classify_text("hello there") == "simple"
    assert e.mb.classify_text("thanks!") == "simple"
    assert e.mb.classify_text("what is Python") == "simple"
    # execute intents always go through the task pipeline (never the simple fast-path)
    assert e.mb.classify_text("Write a document about my project") == "complex"
    # capability gap forces complex (MB must intervene even for a single component)
    assert e.mb.classify_text("Build a slide deck about the project") == "complex"
    assert e.mb.classify_text(
        "Analyze the Q3 sales and save a summary report") == "complex"
    assert e.mb.classify_text("Research Python 3.13 and write a demo script") == "complex"


# ---------------- worker selection: stats-ranked + team group ----------------
def test_worker_selection_ranks_by_stats():
    e = _engine()
    e.seed_worker("w-good", "Good Data Worker", {"data.summarize": {"capability": "data"}})
    e.seed_worker("w-slow", "Slow Data Worker", {"data.summarize": {"capability": "data"}})
    # build statistics: w-good reliable, w-slow flaky
    for _ in range(3):
        e.registry.record_result("w-good", "t1", passed=True, exec_ms=40)
        e.registry.record_result("w-slow", "t1", passed=False, exec_ms=900)
    e.seed_worker("worker-writer", "Writer Worker", {"writer.markdown": {"capability": "writer"}})
    spec = e.mb.intelligence.analyze("Analyze the Q3 sales and save a summary report",
                                     _ctx({"q3": [1, 2, 3]}), None, e)
    team, gaps = e.mb.intelligence.select_workers(spec, e)
    assert gaps == []
    assert team["data.summarize"] == "w-good"      # better qa_pass_rate / lower failure
    assert team["writer.markdown"] == "worker-writer"


def test_task_group_contains_only_selected_team():
    e = _engine()
    _seed(e)
    e.seed_worker("researcher", "Researcher", {"research.search": {"capability": "research"}})
    e.seed_worker("coder", "Coder", {"coding.python": {"capability": "coding"}})
    out = e.project_dir / "t.md"
    task = e.submit("Analyze the Q3 sales and save a summary report",
                    ctx={"inputs": {"dataset": {"region": ["E"], "q3": [5]}},
                         "save_path": out, "project_id": "p2"})
    assert task.state == TaskState.COMPLETED, task.state.value
    row = db.query_one("SELECT member_ids_json FROM task_groups WHERE task_id=?", (task.task_id,))
    import json
    members = json.loads(row["member_ids_json"])
    assert members == ["worker-data", "worker-writer"]      # not researcher/coder
    assert task.spec["team_plan"] == {"data.summarize": "worker-data",
                                      "writer.markdown": "worker-writer"}


# ---------------- permission planning ----------------
def test_permission_planning_high_risk():
    e = _engine()
    _seed(e)
    task = e.submit("Analyze the Q3 sales, write a report, and delete the old draft",
                    ctx=_ctx({"q3": [1, 2, 3]}))
    assert task.state == TaskState.COMPLETED, task.state.value
    assert task.spec["risk_level"] == "high"
    levels = {p["action"]: p["level"] for p in task.spec["approvals_expected"]}
    # Phase 5 refined delete: ordinary project files -> ASK; the more specific
    # important-file / system policy remains EXPLICIT (see DECISIONS.md)
    assert levels.get("delete") in ("ASK", "EXPLICIT")
    assert levels.get("install") == "DENY"         # worker install is blocked outright
    assert levels.get("modify") == "ASK"           # config modify asks first
    assert any(ev["action"] == "permission_plan" for ev in e.timeline(task.task_id))


def test_permission_planning_sensitive_local_routing():
    e = _engine()
    _seed(e)
    spec = e.mb.intelligence.analyze(
        "Write a report about the salary data", _ctx({"q3": [1]}), None, e)
    assert spec["privacy"] == "sensitive"
    assert spec["model_hint"] == "local"          # sensitive -> local model routing hint


# ---------------- global memory: consultation + evidence-gated learning ----------------
def test_global_memory_learning_loop():
    e = _engine()
    _seed(e)
    # first ambiguous task -> clarification required (nothing learned yet)
    try:
        e.submit("Help me with the Q3 sales data", ctx=_ctx({"q3": [7]}))
        raise AssertionError("expected ClarificationNeeded")
    except ClarificationNeeded as exc:
        assert "output_type" in exc.missing
        task_id = exc.task_id
    # user picks markdown -> MB learns the preference (evidence #1)
    t = e.clarify(task_id, {"output_type": "markdown"})
    assert t.state == TaskState.COMPLETED
    rows, _ = e.memory.read("MB", "GLOBAL", "global")
    prefs = [r for r in rows if r["type"] == "preference"]
    assert prefs and "default_output_format=markdown" in prefs[0]["content"]
    assert prefs[0]["confidence"] == "MEDIUM"

    # second identical request: MB auto-resolves from global memory, no clarification
    t2 = e.submit("Help me with the Q3 sales data", ctx=_ctx({"q3": [8]}))
    assert t2.state == TaskState.COMPLETED, t2.state.value
    assert t2.spec["output_type"] == "markdown"
    assert t2.spec["provenance"].get("output_type") == "global_memory:default_output_format"
    # the learned output format actually yields a component (components are rebuilt
    # AFTER global-memory injection — otherwise the task completes vacuously with 0)
    assert any(c["capability"] == "writer" for c in t2.spec["components"]), t2.spec["components"]
    # the corroborating case promotes confidence to HIGH (>= 2 evidence)
    rows, _ = e.memory.read("MB", "GLOBAL", "global")
    prefs = [r for r in rows if r["type"] == "preference"]
    assert prefs[0]["confidence"] == "HIGH"


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
