"""Phase 14: task priority reorder + live office heartbeat inputs.

Covers (bridge level):
  - tasks gained a priority column; list ordering follows it
  - reorder_tasks persists a user-chosen order and rejects foreign task ids
  - hive_state still exposes a live worker roster usable as heartbeat source
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="wd_p14_")
os.environ["WORKDESK_DB"] = str(Path(_TMP) / "test.db")

from core import config as app_config  # noqa: E402
app_config.CONV_DIR = Path(_TMP) / "conv"
app_config.PROJ_DIR = Path(_TMP) / "proj"
app_config.CONV_DIR.mkdir(parents=True, exist_ok=True)
app_config.PROJ_DIR.mkdir(parents=True, exist_ok=True)

from bridge import WorkDeskBridge  # noqa: E402
from src.workdesk import db  # noqa: E402
from src.workdesk.runtime import ClarificationNeeded  # noqa: E402
WorkDeskBridge.WS_ROOT = Path(_TMP) / "workspace"
WorkDeskBridge.VAULT_ROOT = Path(_TMP) / "vault"
WorkDeskBridge.HIVE_ROOT = Path(_TMP) / "hive"


class TestPriorityReorder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def setUp(self):
        shutil.rmtree(WorkDeskBridge.HIVE_ROOT, ignore_errors=True)
        WorkDeskBridge.HIVE_ROOT.mkdir(parents=True)
        # fresh task state per test (shared class-level DB)
        for t in ("tasks", "task_transitions", "task_groups", "checkpoints",
                  "approvals", "qa_verdicts"):
            try:
                db.execute(f"DELETE FROM {t}")
            except Exception:
                pass

    def _three(self):
        cid = "conv-p14"
        ids = []
        for text in ("first task", "second task", "third task"):
            try:
                t = self.b.engine.submit(text, ctx={"conversation_id": cid})
            except ClarificationNeeded as exc:
                t = self.b.engine.clarify(exc.task_id, {"output_type": "report"})
            ids.append(t.task_id)
        return cid, ids[0], ids[1], ids[2]

    def test_default_order_newest_first(self):
        cid, t1, t2, t3 = self._three()
        ids = [t["task_id"] for t in self.b.tasks_list(conversation_id=cid)]
        self.assertEqual(ids, [t3, t2, t1])
        self.assertTrue(all(t.get("priority", 0) == 0
                            for t in self.b.tasks_list(conversation_id=cid)))

    def test_reorder_persists_and_wins(self):
        cid, t1, t2, t3 = self._three()
        self.b.reorder_tasks(cid, [t1, t3, t2])
        self.assertEqual([t["task_id"] for t in self.b.tasks_list(conversation_id=cid)],
                         [t1, t3, t2])
        self.b.reorder_tasks(cid, [t2, t1, t3])
        self.assertEqual([t["task_id"] for t in self.b.tasks_list(conversation_id=cid)],
                         [t2, t1, t3])

    def test_foreign_task_rejected(self):
        cid, t1, _, _ = self._three()
        try:
            t = self.b.engine.submit("other conv", ctx={"conversation_id": "conv-other"})
        except ClarificationNeeded as exc:
            t = self.b.engine.clarify(exc.task_id, {"output_type": "report"})
        other = t.task_id
        with self.assertRaises(ValueError):
            self.b.reorder_tasks(cid, [t1, other])
        self.assertEqual([t["task_id"] for t in self.b.tasks_list(conversation_id="conv-other")],
                         [other])

    def test_hive_state_has_live_roster(self):
        cid, _, _, _ = self._three()
        st = self.b.hive_state(cid)
        self.assertIsInstance(st.get("workers"), list)
        self.assertIn("board", st)
        self.assertIn("messages", st)
        self.assertIn("log", st)
        if st["workers"]:
            self.assertIn("status", st["workers"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
