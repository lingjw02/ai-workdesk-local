"""Phase-6 QA/rework engine tests (Spec §16 Phase 6).

Covers: structured failure reports, persisted validation history (QA-1 +
every QA-2 cycle), deterministic format checks, selective rework scope,
PM-lesson-guided rework (HIGH lessons steer execution), rework guidance in
artifacts, retry limits, and the task validation report API.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workdesk import db  # noqa: E402
from workdesk import Engine, TaskState, FailureReport  # noqa: E402


def _engine(auto_approve=True):
    return Engine(db_path=Path(tempfile.mkdtemp()) / "p6.db",
                  auto_approve=auto_approve,
                  project_dir=Path(tempfile.mkdtemp()) / "ws")


def _seed(e, fail_data=False):
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                  fail_once=["data.summarize"] if fail_data else None)
    e.seed_worker("worker-writer", "Writer Worker",
                  {"writer.markdown": {"capability": "writer"}})


def _task(e, text="Analyze the Q3 sales and save a summary report", pid="p6",
          fail_data=False):
    _seed(e, fail_data=fail_data)
    return e.submit(text, ctx={"project_id": pid,
                               "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                               "inputs": {"dataset": {"q3": [1, 2, 3]}},
                               "output_type": "markdown"})


# ---------------- structured failure reports ----------------
def test_failure_report_structure():
    e = _engine()
    _seed(e, fail_data=True)                       # data worker fails first attempt
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    assert t.state == TaskState.COMPLETED
    # the first (failed) QA-2 cycle is recorded in the validation history
    hist = e.qa_history(t.task_id)
    qa2_fail = [v for v in hist if v["stage"] == "QA2" and not v["passed"]]
    assert qa2_fail, hist
    assert qa2_fail[0]["component"] == "data.summarize"
    assert qa2_fail[0]["criterion"] == "totals_correct"
    assert qa2_fail[0]["severity"] == "high"
    assert "expected total" in qa2_fail[0]["evidence"]
    assert qa2_fail[0]["fix_hint"]
    # and the passing cycle is recorded too
    assert any(v["stage"] == "QA2" and v["passed"] for v in hist)


def test_qa2_persists_history_with_cycle_numbers():
    e = _engine()
    _seed(e, fail_data=True)
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    cycles = sorted({v["cycle"] for v in e.qa_history(t.task_id) if v["stage"] == "QA2"})
    assert cycles == [0, 1], cycles            # fail on 0, pass on 1


def test_qa1_history_recorded():
    e = _engine()
    _seed(e)
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    qa1 = [v for v in e.qa_history(t.task_id) if v["stage"] == "QA1"]
    assert qa1 and qa1[0]["passed"] == 1


# ---------------- deterministic format checks ----------------
def test_format_check_rejects_unheaded_markdown():
    e = _engine()
    fr = FailureReport("writer.markdown", "format_ok", "low", "x", "fix it")
    assert fr.criterion == "format_ok" and fr.fix_hint == "fix it"
    # a file that does not start with a heading fails the markdown format check
    path = Path(tempfile.mkdtemp()) / "bad.md"
    path.write_text("plain text without heading\n", encoding="utf-8")
    hint = e.qa._format_check({"kind": "file", "path": str(path)},
                              path.read_text(encoding="utf-8"), "markdown")
    assert hint and "heading" in hint


def test_format_check_accepts_good_outputs():
    e = _engine()
    assert e.qa._format_check({"kind": "file"}, "# Q3 Sales Summary\n...", "markdown") is None
    assert e.qa._format_check({"kind": "file"}, "a,b,c\n1,2,3\n", "csv") is None
    assert e.qa._format_check({"kind": "file"},
                              "# slides output\n\nSummary: stub\n", "slides") is None


def test_format_check_rejects_bad_csv():
    e = _engine()
    hint = e.qa._format_check({"kind": "file"},
                              "no delimiter at all\nsecond row here\n", "csv")
    assert hint and "comma" in hint


# ---------------- selective rework: never the full project ----------------
def test_selective_rework_redoes_only_failed_components():
    e = _engine()
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}},
                  fail_once=["data.summarize"])
    e.seed_worker("worker-research", "Research Worker",
                  {"research.search": {"capability": "research"}})
    e.seed_worker("worker-writer", "Writer Worker",
                  {"writer.markdown": {"capability": "writer"}})
    t = e.submit("Analyze the Q3 sales, research the topic and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    assert t.state == TaskState.COMPLETED
    # data was redone (failed once); writer is data's downstream consumer so it
    # re-renders; research (unrelated) is NOT re-triggered
    rec_d = e.registry.get_worker("worker-data")
    rec_r = e.registry.get_worker("worker-research")
    rec_w = e.registry.get_worker("worker-writer")
    assert rec_d["times_triggered"] == 2, rec_d   # first run + redo
    assert rec_r["times_triggered"] == 1, rec_r   # untouched by rework
    assert rec_w["times_triggered"] == 2, rec_w   # downstream consumer re-renders
    reworks = [a for a in e.permissions.timeline(t.task_id)
               if a["action"] == "rework"]
    assert {a["reason"].split("=")[-1] for a in reworks} == {"data.summarize", "writer.markdown"}


# ---------------- PM lessons steer rework (Phase 4 -> 6 hand-off) ----------------
def test_pm_lesson_guides_rework_after_promotion():
    e = _engine()
    pm = e.get_pm("p6")
    # seed a HIGH lesson directly: capability "writer" has failed twice before
    e.registry.add_pm_lesson(pm.pm_id, "writer",
                             "writer.markdown reports often miss the Summary section",
                             2, "HIGH", ["t-1", "t-2"])
    _seed(e)
    # make the writer's FIRST attempt produce a report without a Summary section
    _orig = e.workers["worker-writer"]._run_skill
    state = {"n": 0}

    def _first_no_summary(task, group, comp, inject_error=False):
        if comp.get("skill") == "writer.markdown" and state["n"] == 0:
            state["n"] += 1
            p = task.spec.get("save_path")
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_text("# Q3 Report\n\nTotal: 6\n", encoding="utf-8")
            return {"kind": "file", "path": str(p)}
        return _orig(task, group, comp, inject_error)

    e.workers["worker-writer"]._run_skill = _first_no_summary
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    assert t.state == TaskState.COMPLETED
    # the HIGH lesson was applied during rework and audited
    applied = [a for a in e.permissions.timeline(t.task_id)
               if a["action"] == "rework_lesson_applied"]
    assert applied and "writer" in applied[0]["reason"]
    # and the reworked artifact carries the QA Note from the lesson
    from workdesk import db as _db
    row = _db.query_one("SELECT result_json FROM tasks WHERE task_id=?", (t.task_id,))
    import json
    result = json.loads(row["result_json"] or "null") or {}
    paths = [a["path"] for a in (result.get("artifacts") or []) if a.get("path")]
    assert paths
    content = Path(paths[-1]).read_text(encoding="utf-8")
    assert "QA Note: writer.markdown reports often miss" in content, content


def test_no_lesson_no_guidance():
    e = _engine()
    _seed(e, fail_data=True)                       # rework happens, no HIGH lesson
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    assert t.state == TaskState.COMPLETED
    applied = [a for a in e.permissions.timeline(t.task_id)
               if a["action"] == "rework_lesson_applied"]
    assert applied == []


# ---------------- retry limits + validation report ----------------
def test_retry_limit_fails_and_report_shows_cycles():
    e = _engine()
    # a worker that ALWAYS computes wrong totals (permanent failure via handler patch)
    e.seed_worker("worker-bad", "Bad Data Worker",
                  {"data.summarize": {"capability": "data"}})
    _orig = e.workers["worker-bad"]._run_skill

    def _always_wrong(task, group, comp, inject_error=False):
        if comp.get("skill") == "data.summarize":
            ds = (task.spec.get("inputs") or {}).get("dataset") or {}
            return {"kind": "computation", "total": sum(ds.get("q3") or []) + 10,
                    "regions": ds.get("region")}
        return _orig(task, group, comp, inject_error)

    e.workers["worker-bad"]._run_skill = _always_wrong
    e.seed_worker("worker-writer", "Writer Worker",
                  {"writer.markdown": {"capability": "writer"}})
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    assert t.state == TaskState.FAILED
    assert t.rework_count > 1
    report = e.task_validation_report(t.task_id)
    assert report["state"] == "FAILED"
    assert len(report["qa2_cycles"]) == e.config.MAX_REWORK_CYCLES + 1   # 0..limit
    assert any(v["criterion"] == "totals_correct" for v in report["failures"])
    # the PM stored a retry-limit lesson from this failure
    lessons = e.registry.get_pm_lessons(e.get_pm("p6").pm_id)
    assert any("retry limit" in l["content"] for l in lessons)


def test_validation_report_on_clean_task():
    e = _engine()
    _seed(e)
    t = e.submit("Analyze the Q3 sales and save a summary report",
                 ctx={"project_id": "p6",
                      "save_path": str(Path(tempfile.mkdtemp()) / "r.md"),
                      "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    report = e.task_validation_report(t.task_id)
    assert report["state"] == "COMPLETED"
    assert report["qa2_cycles"] == [0]
    assert report["failures"] == []


def test_verdict_score():
    e = _engine()
    v = e.qa.qa2(None, [], {"components": [{"id": "x.y"}], "criteria": [],
                            "inputs": None, "output_type": "markdown"})
    assert v["pass"] is False
    assert v["score"] <= 0.99 and v["score"] >= 0.0
    v2 = e.qa.qa2(None, [], {"components": [], "criteria": [], "inputs": None,
                              "output_type": "markdown"})
    assert v2["pass"] is True and v2["score"] == 1.0


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
