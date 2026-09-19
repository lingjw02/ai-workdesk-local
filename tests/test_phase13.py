"""Phase 13 tests — Hive layer: mailbox messaging, speech-act protocol,
anti-livelock hop cap, blackboard single-scribe, event log, state snapshot.
Isolated: HIVE_ROOT + DB + workspace/vault all redirected to temp dirs.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = tempfile.mkdtemp(prefix="wd_p13_")
os.environ["WORKDESK_DB"] = str(Path(_TMP) / "test.db")

from core import config as app_config  # noqa: E402
app_config.CONV_DIR = Path(_TMP) / "conv"
app_config.PROJ_DIR = Path(_TMP) / "proj"

from bridge import WorkDeskBridge  # noqa: E402
WorkDeskBridge.WS_ROOT = Path(_TMP) / "workspace"
WorkDeskBridge.VAULT_ROOT = Path(_TMP) / "vault"
WorkDeskBridge.HIVE_ROOT = Path(_TMP) / "hive"


class TestHive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def setUp(self):
        # fresh hive root per test
        shutil.rmtree(WorkDeskBridge.HIVE_ROOT, ignore_errors=True)
        WorkDeskBridge.HIVE_ROOT.mkdir(parents=True)

    def test_send_roundtrip_inbox_outbox(self):
        r = self.b.hive_send("conv-1", "mb", "researcher", "request",
                             "Find sources on X", "please research X")
        self.assertTrue(r.get("ok"))
        m = r["message"]
        self.assertEqual(m["from"], "mb")
        self.assertEqual(m["to"], "researcher")
        self.assertEqual(m["act"], "request")
        self.assertTrue(m["requires_reply"])
        self.assertEqual(m["hops"], 0)
        # delivered to researcher's inbox and mb's outbox
        inbox = list((WorkDeskBridge.HIVE_ROOT / "agents" / "researcher" / "inbox").glob("*.json"))
        outbox = list((WorkDeskBridge.HIVE_ROOT / "agents" / "mb" / "outbox").glob("*.json"))
        self.assertEqual(len(inbox), 1)
        self.assertEqual(len(outbox), 1)
        self.assertEqual(self.b.hive_get_message(m["id"])["id"], m["id"])
        # log line written
        log = (WorkDeskBridge.HIVE_ROOT / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("hive_msg", log)
        self.assertIn(m["id"], log)

    def test_invalid_act_rejected(self):
        r = self.b.hive_send("conv-1", "mb", "coder", "explode", "bad", "")
        self.assertEqual(r.get("error"), "bad_act")

    def test_hop_cap_anti_livelock(self):
        # chain replies; hops increment; past cap -> refused
        prev = None
        last = None
        for i in range(10):
            r = self.b.hive_send("conv-2", "a", "b", "query", f"q{i}", "", prev)
            last = r
            if r.get("error"):
                break
            prev = r["message"]["id"]
        self.assertEqual(last.get("error"), "hop_cap")
        self.assertGreaterEqual(last.get("hops"), 8)
        log = (WorkDeskBridge.HIVE_ROOT / "log.jsonl").read_text(encoding="utf-8")
        self.assertIn("hive_refused", log)

    def test_messages_filter(self):
        self.b.hive_send("conv-a", "mb", "w1", "inform", "done A", "")
        self.b.hive_send("conv-a", "w1", "mb", "done", "ack A", "")
        self.b.hive_send("conv-b", "mb", "w1", "request", "other chat", "")
        all_a = self.b.hive_messages("conv-a")
        self.assertEqual(len(all_a), 2)
        self.assertEqual({m["act"] for m in all_a}, {"inform", "done"})
        # agent filter: everything touching w1 (its inbox + its outbox)
        only_w1 = self.b.hive_messages("conv-a", agent_id="w1")
        self.assertEqual(len(only_w1), 2)
        self.assertEqual({m["to"] for m in only_w1}, {"mb", "w1"})

    def test_board_single_scribe(self):
        r = self.b.hive_board_put("conv-1", "# Plan\n\n1. Research\n2. Code", "pm")
        self.assertTrue(r.get("ok"))
        g = self.b.hive_board_get("conv-1")
        self.assertIn("1. Research", g["content"])
        self.assertEqual(g["scribe"], "pm")
        # board is per conversation
        other = self.b.hive_board_get("conv-2")
        self.assertEqual(other["content"], "")

    def test_hive_state_snapshot(self):
        self.b.hive_send("conv-s", "mb", "researcher", "request", "Go", "")
        st = self.b.hive_state("conv-s")
        self.assertIn("workers", st)
        self.assertIn("board", st)
        self.assertIn("messages", st)
        self.assertIn("log", st)
        self.assertEqual(st["hop_cap"], 8)
        self.assertEqual(len(st["messages"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
