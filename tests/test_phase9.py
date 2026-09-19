"""Phase 9 — learning system tests (Spec 01 §8, Phase 9).

Covers the full pipeline: task outcome -> lesson candidates in three scopes
(pm / worker / global), evidence gating (LOW -> MEDIUM -> HIGH + stored),
aggregation of global evidence across projects, HIGH-lesson hints applied to
future QA runs (applied_count + lesson_applied audit), stats, and memory
boundaries (each owner sees only its own lessons). Also verifies Phase-4 PM
lesson compatibility (same lesson_key convention).
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from workdesk import db  # noqa: E402
from workdesk.engine import Engine  # noqa: E402
from workdesk.learning import LearningSystem  # noqa: E402


def _engine(auto_approve=True):
    return Engine(db_path=Path(tempfile.mkdtemp()) / "p9.db",
                  auto_approve=auto_approve)


def _seed(e, fail_data=True):
    e.seed_worker("worker-data", "Data Worker",
                  {"data.summarize": {"capability": "data"}},
                  fail_once=["data.summarize"] if fail_data else None)
    e.seed_worker("worker-writer", "Writer Worker",
                  {"writer.markdown": {"capability": "writer"}})


def _ctx(out_dir=None, pid="p9"):
    out = out_dir or tempfile.mkdtemp()
    return {"project_id": pid, "out_dir": out,
            "save_path": str(Path(out) / "r.md"),
            "inputs": {"dataset": {"q3": [1, 2, 3]}}, "output_type": "markdown"}


class TestLearningPipeline(unittest.TestCase):
    def test_rework_task_creates_three_scope_lessons(self):
        db.reset()
        e = _engine()
        _seed(e)
        t = e.submit("Analyze the Q3 sales and save a summary report", _ctx())
        self.assertEqual(t.state.value, "COMPLETED")
        pm = e.get_pm("p9")
        pm_lessons = e.learning.list_all(scope="pm", limit=50)
        self.assertTrue(any(l["owner_id"] == pm.pm_id and l["lesson_key"] == "data"
                            for l in pm_lessons))
        worker_lessons = e.learning.list_all(scope="worker", limit=50)
        self.assertTrue(any(l["owner_id"] == "worker-data" and l["lesson_key"] == "data"
                            for l in worker_lessons))
        global_lessons = e.learning.list_all(scope="global", limit=50)
        self.assertTrue(any(l["owner_id"] == "MB" and l["lesson_key"] == "data"
                            for l in global_lessons))

    def test_evidence_gating_promotes_to_high(self):
        db.reset()
        e = _engine()
        _seed(e, fail_data=True)
        ls = LearningSystem(e.registry)
        # first failure -> LOW candidate
        ls.learn_from_task(task=_FakeTask("t1", "data"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["w1"],
                           pm_id="pm1")
        row = ls._get("global", "MB", "data")
        self.assertEqual(row["confidence"], "LOW")
        self.assertEqual(row["status"], "candidate")
        # corroborating failure -> HIGH + stored at the promote threshold
        ls.learn_from_task(task=_FakeTask("t2", "data"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["w1"],
                           pm_id="pm1")
        row = ls._get("global", "MB", "data")
        self.assertEqual(row["evidence_count"], 2)
        self.assertEqual(row["confidence"], "HIGH")
        self.assertEqual(row["status"], "stored")

    def test_global_lesson_aggregates_across_projects(self):
        db.reset()
        e = _engine()
        _seed(e, fail_data=True)
        ls = LearningSystem(e.registry)
        ls.learn_from_task(task=_FakeTask("t1", "data"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["w1"], pm_id="pmA")
        ls.learn_from_task(task=_FakeTask("t2", "data"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["w1"], pm_id="pmB")
        g = ls._get("global", "MB", "data")
        self.assertEqual(g["evidence_count"], 2)
        self.assertEqual(g["confidence"], "HIGH")
        # each PM keeps its own pm-scope lesson (memory boundary)
        self.assertEqual(ls._get("pm", "pmA", "data")["evidence_count"], 1)
        self.assertEqual(ls._get("pm", "pmB", "data")["evidence_count"], 1)

    def test_hints_and_qa_application_loop(self):
        db.reset()
        e = _engine()
        _seed(e, fail_data=True)
        # build a HIGH stored lesson directly
        ls = LearningSystem(e.registry)
        ls.learn_from_task(task=_FakeTask("t1", "data"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["w1"], pm_id="pmX")
        ls.learn_from_task(task=_FakeTask("t2", "data"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["w1"], pm_id="pmX")
        hints = e.learning.hints_for("data")
        self.assertGreaterEqual(len(hints), 1)
        self.assertTrue(any(h["scope"] == "global" for h in hints))
        before = e.learning.stats()["applied"]
        # a fresh task on the same capability (no fail_once left) passes QA-2
        t = e.submit("Analyze the Q3 sales and save a summary report", _ctx())
        self.assertEqual(t.state.value, "COMPLETED")
        after = e.learning.stats()["applied"]
        self.assertGreaterEqual(after, before + 1)
        audit = e.permissions.timeline()
        self.assertTrue(any(a["action"] == "lesson_applied" for a in audit))

    def test_successful_tasks_do_not_create_lessons(self):
        db.reset()
        e = _engine()
        _seed(e, fail_data=False)
        t = e.submit("Analyze the Q3 sales and save a summary report", _ctx())
        self.assertEqual(t.state.value, "COMPLETED")
        self.assertEqual(e.learning.stats()["total"], 0)

    def test_memory_boundaries(self):
        db.reset()
        e = _engine()
        _seed(e, fail_data=True)
        ls = LearningSystem(e.registry)
        ls.learn_from_task(task=_FakeTask("t1", "data"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["worker-data"],
                           pm_id="pmA")
        ls.learn_from_task(task=_FakeTask("t2", "writer"), outcome="FAILED",
                           qa_cycles=1, rework_count=3, worker_ids=["worker-writer"],
                           pm_id="pmB")
        wd = ls.for_owner("worker", "worker-data")
        self.assertEqual(len(wd), 1)
        self.assertEqual(wd[0]["lesson_key"], "data")
        ww = ls.for_owner("worker", "worker-writer")
        self.assertEqual(len(ww), 1)
        self.assertEqual(ww[0]["lesson_key"], "writer")
        pmA = ls.for_owner("pm", "pmA")
        self.assertTrue(all(l["lesson_key"] == "data" for l in pmA))

    def test_stats_and_pm_compat(self):
        db.reset()
        e = _engine()
        _seed(e, fail_data=True)
        t = e.submit("Analyze the Q3 sales and save a summary report", _ctx())
        self.assertEqual(t.state.value, "COMPLETED")
        st = e.learning.stats()
        self.assertGreaterEqual(st["total"], 3)
        self.assertIn("pm", st["by_scope"])
        self.assertIn("worker", st["by_scope"])
        self.assertIn("global", st["by_scope"])
        # Phase-4 API still works against pm-scope lessons
        pm = e.get_pm("p9")
        legacy = e.registry.get_pm_lessons(pm.pm_id)
        self.assertTrue(any(l["lesson_key"] == "data" for l in legacy))


class _FakeTask:
    """Minimal task stand-in for direct LearningSystem unit tests."""
    def __init__(self, task_id: str, capability: str):
        self.task_id = task_id
        self.spec = {"components": [{"capability": capability}]}


if __name__ == "__main__":
    unittest.main(verbosity=2)
