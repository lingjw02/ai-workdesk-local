"""Phase-3 Worker ecosystem tests (Spec §16 Phase 3 + §5 Worker creation paths).

Covers: Worker Creator profile design, capability-gap auto-fill (permission-gated),
idempotent creation, worker lifecycle, full-profile catalog, dynamic stub skills,
manual install from profile, PM-requested creation, and worker upgrade.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from workdesk import db  # noqa: E402
from workdesk import Engine, WorkerCreator, TaskState, ClarificationNeeded  # noqa: E402


def _engine(auto_approve=True, project_dir=None):
    return Engine(db_path=Path(tempfile.mkdtemp()) / "p3.db", auto_approve=auto_approve,
                  project_dir=project_dir)


def _seed(e):
    e.seed_worker("worker-data", "Data Worker", {"data.summarize": {"capability": "data"}})
    e.seed_worker("worker-writer", "Writer Worker", {"writer.markdown": {"capability": "writer"}})


def _ctx():
    return {"project_id": "p3", "out_dir": str(Path(tempfile.mkdtemp()))}


# ---------------- Worker Creator: profile design ----------------
def test_worker_creator_designs_complete_profile():
    e = _engine()
    profile = e.worker_creator.design("slides", description="build slide decks")
    assert profile["worker_id"] == "w-slides"
    assert profile["name"] == "Slides Worker"
    # identity
    assert profile["role_class"] == "WORKER"
    assert "slide" in profile["description"]
    # personality + communication style
    assert profile["personality"]["communication_style"]
    assert profile["personality"]["tone"]
    # behavior rules
    assert any("permission" in r for r in profile["behavior_rules"])
    # skills / tools / memory rules
    assert profile["skills"][0]["capability"] == "slides"
    assert profile["tools"][0]["tool"] == "FILESYSTEM"
    assert profile["memory_rules"]["cross_project"] == "NEVER"
    assert profile["permissions"] == {}


# ---------------- capability-gap auto-fill (auto_approve path) ----------------
def test_capability_gap_auto_fills_worker():
    e = _engine(auto_approve=True)
    _seed(e)
    assert "w-slides" not in e.workers
    task = e.submit("Build a slide deck about the project", ctx=_ctx())
    assert task.state == TaskState.COMPLETED, task.state.value
    # the worker was designed, registered, activated and instantiated
    rec = e.registry.get_worker("w-slides")
    assert rec is not None and rec["status"] == "AVAILABLE"
    assert "w-slides" in e.workers
    # audit trail records the creation and the run
    tl = e.timeline(task.task_id)
    assert any("worker_created" in ev["action"] for ev in tl), tl
    # the dynamic stub skill produced an artifact that passed QA-2
    arts = e._group_artifacts(task.group_id)
    assert any("slides_output" in a["path"] for a in arts), arts


# ---------------- idempotency ----------------
def test_worker_creator_is_idempotent():
    e = _engine(auto_approve=True)
    _seed(e)
    e.submit("Build a slide deck about the project", ctx=_ctx())
    e.submit("Build another slide deck for Q3", ctx=_ctx())
    # one worker, one skill record for slides, no duplicates
    assert len(e.registry.find_workers(["slides"])) == 1
    assert len([w for w in e.workers if w == "w-slides"]) == 1
    # direct create() reports "existing"
    wid, status = e.worker_creator.create(e, "slides")
    assert status == "existing" and wid == "w-slides"


# ---------------- lifecycle ----------------
def test_worker_lifecycle():
    e = _engine()
    wid, status = e.worker_creator.create(e, "excel")
    assert status == "created"
    assert e.registry.get_worker(wid)["status"] == "AVAILABLE"
    assert len(e.registry.find_workers(["excel"])) == 1
    e.registry.suspend(wid)
    assert e.registry.get_worker(wid)["status"] == "SUSPENDED"
    assert len(e.registry.find_workers(["excel"])) == 0     # not selectable while suspended
    e.registry.activate(wid)
    assert len(e.registry.find_workers(["excel"])) == 1
    e.registry.retire(wid)
    assert e.registry.get_worker(wid)["status"] == "RETIRED"


# ---------------- worker catalog: full profiles + stats ----------------
def test_worker_catalog_full_profiles():
    e = _engine(auto_approve=True)
    _seed(e)
    e.submit("Build a slide deck about the project", ctx=_ctx())
    e.submit("Analyze the Q3 sales and save a summary report",
             ctx={"project_id": "p3", "out_dir": _ctx()["out_dir"],
                  "inputs": {"dataset": {"q3": [1, 2, 3]}},
                  "save_path": str(Path(_ctx()["out_dir"]) / "r.md"),
                  "output_type": "markdown"})
    catalog = e.worker_catalog()
    by_id = {w["worker_id"]: w for w in catalog}
    assert {"worker-data", "worker-writer", "w-slides"} <= set(by_id)
    # profile completeness
    for wid in ("worker-data", "w-slides"):
        rec = by_id[wid]
        assert rec["personality"]["communication_style"]
        assert rec["behavior_rules"]
        assert rec["skills"] and rec["tools"] and rec["memory_rules"]
    # statistics are recorded and readable
    assert by_id["w-slides"]["tasks_completed"] >= 1
    assert by_id["w-slides"]["times_triggered"] >= 1


# ---------------- production path: gap requires approval ----------------
def test_capability_gap_requires_approval():
    e = _engine(auto_approve=False)
    _seed(e)
    try:
        e.submit("Draft an email about the Q3 results", ctx=_ctx())
        raise AssertionError("expected ClarificationNeeded")
    except ClarificationNeeded as exc:
        gaps = (exc.verdict or {}).get("feasibility", {}).get("gaps") or []
        assert any("email" in g for g in gaps), gaps
        task_id = exc.task_id
    assert "w-email" not in e.workers, "no worker created without approval"
    # insisting on the unsupported output -> honest FAILED (QA1_FAIL_FINAL)
    t = e.clarify(task_id, {"output_type": "email"})
    assert t.state == TaskState.FAILED
    # the Worker Creator's own install gate: EXPLICIT approval stays PENDING
    wid, status = e.worker_creator.create(e, "email")
    assert status == "pending" and wid is None
    assert e.registry.get_worker("w-email") is None


# ---------------- dynamic stub skill produces QA-2-valid artifact ----------------
def test_dynamic_skill_produces_artifact():
    e = _engine(auto_approve=True)
    _seed(e)
    task = e.submit("Build a slide deck about the project", ctx=_ctx())
    arts = e._group_artifacts(task.group_id)
    path = next(a["path"] for a in arts if "slides_output" in a["path"])
    content = Path(path).read_text(encoding="utf-8")
    assert "Summary:" in content                       # QA-2 content check
    assert "slides" in content                         # capability labelled
    assert "stub" in content                           # honest about being a stub


# ---------------- manual install from profile (user path) ----------------
def test_install_worker_from_profile():
    e = _engine()
    profile = e.worker_creator.design("email", description="write emails")
    profile["worker_id"] = "custom-email"             # user chooses the id
    wid = e.install_worker_from_profile(profile)
    assert wid == "custom-email"
    rec = e.registry.get_worker(wid)
    assert rec["status"] == "AVAILABLE"
    assert any(s.get("capability") == "email" for s in rec["skills"])
    assert "custom-email" in e.workers


# ---------------- creation is permission-audited ----------------
def test_worker_creation_is_audited():
    e = _engine(auto_approve=True)
    _seed(e)
    task = e.submit("Build a slide deck about the project", ctx=_ctx())
    tl = e.timeline(task.task_id)
    created = [ev for ev in tl if ev["action"] == "worker_created"]
    assert created, tl
    assert any("slides" in ev["reason"] for ev in created)


# ---------------- worker upgrade ----------------
def test_worker_upgrade_adds_capability():
    e = _engine()
    _seed(e)
    e.worker_creator.upgrade(e, "worker-writer", "email")
    rec = e.registry.get_worker("worker-writer")
    caps = {s.get("capability") for s in rec["skills"]}
    assert {"writer", "email"} <= caps
    # idempotent: upgrading again changes nothing
    e.worker_creator.upgrade(e, "worker-writer", "email")
    rec2 = e.registry.get_worker("worker-writer")
    assert {s.get("capability") for s in rec2["skills"]} == caps


# ---------------- persistence: workers survive a restart ----------------
def test_workers_survive_restart():
    db.reset()
    db.init()   # fresh schema for this test
    dbp = Path(tempfile.mkdtemp()) / "restart.db"
    e1 = Engine(db_path=dbp, auto_approve=True)
    _seed(e1)
    task = e1.submit("Build a slide deck about the project", ctx=_ctx())
    assert task.state == TaskState.COMPLETED
    # second engine over the SAME database = application restart
    e2 = Engine(db_path=dbp, auto_approve=True)
    assert "w-slides" in e2.workers
    rec = e2.registry.get_worker("w-slides")
    assert rec["status"] == "AVAILABLE" and rec["tasks_completed"] >= 1
    # the gap is covered after restart: same request completes without clarification
    t2 = e2.submit("Build a slide deck about the project", ctx=_ctx())
    assert t2.state == TaskState.COMPLETED, t2.state.value


# ---------------- QA-2 completeness: a component with no artifact must fail ----
def test_qa2_fails_when_component_produces_no_artifact():
    e = _engine()
    spec = {"components": [{"id": "x.y", "skill": "x.y", "capability": "x"}],
            "criteria": [{"id": "file_exists"}, {"id": "has_summary"}],
            "inputs": None}
    v = e.qa.qa2(None, [], spec)
    assert not v["pass"]
    assert any(f["criterion"] == "artifact_missing" for f in v["failures"]), v


# ---------------- writer defaults to a project path when no save_path is given ----
def test_writer_defaults_save_path():
    out = Path(tempfile.mkdtemp())
    e = _engine(project_dir=out)
    _seed(e)
    t = e.submit("Analyze the Q3 sales and write a summary report",
                 ctx={"project_id": "p3w", "inputs": {"dataset": {"q3": [1, 2, 3]}},
                      "output_type": "markdown"})
    assert t.state == TaskState.COMPLETED, t.state.value
    arts = e._group_artifacts(t.group_id)
    files = [a for a in arts if a.get("kind") == "file"]
    assert files, arts
    assert Path(files[0]["path"]).exists()
    assert "Summary" in Path(files[0]["path"]).read_text(encoding="utf-8")


def _all():
    import traceback
    failed = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        try:
            db.reset()          # isolate each test: fresh in-memory schema
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
