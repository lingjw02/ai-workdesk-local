"""Phase 12 — WorkDesk 2.1 backend tests.

Covers the Main Brain auto-sync pipeline: MB knowledge (global memory,
lessons, todo, PM knowledge) is automatically written into the
vault/mb/_auto/ section. All roots redirected to temp dirs.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["WORKDESK_DB"] = str(Path(tempfile.mkdtemp(prefix="p12_db_")) / "p12.db")

import core.config as app_config  # noqa: E402
_TMP_CONV = Path(tempfile.mkdtemp(prefix="p12_conv_"))
_TMP_PROJ = Path(tempfile.mkdtemp(prefix="p12_proj_"))
app_config.CONV_DIR = _TMP_CONV
app_config.PROJ_DIR = _TMP_PROJ

from bridge import WorkDeskBridge  # noqa: E402

_TMP_WS = Path(tempfile.mkdtemp(prefix="p12_ws_"))
_TMP_VAULT = Path(tempfile.mkdtemp(prefix="p12_vault_"))
WorkDeskBridge.WS_ROOT = _TMP_WS
WorkDeskBridge.VAULT_ROOT = _TMP_VAULT


import shutil


class TestMbSync(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def setUp(self):
        WorkDeskBridge.VAULT_ROOT = _TMP_VAULT
        mb_dir = _TMP_VAULT / "mb"
        if mb_dir.exists():
            shutil.rmtree(mb_dir, ignore_errors=True)

    def test_sync_writes_four_auto_notes(self):
        r = self.b.mb_sync()
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 4)
        tree = self.b.vault_tree("mb")
        paths = [f["path"] for f in tree]
        for rel in ("_auto/global-memory.md", "_auto/lessons.md",
                    "_auto/todo.md", "_auto/pm-knowledge.md"):
            self.assertIn(rel, paths)

    def test_global_memory_appears_in_memory_note(self):
        self.b.memory_update({"user_language": "中文"})
        self.b.mb_sync()
        d = self.b.vault_read("mb", "_auto/global-memory.md")
        self.assertIn("user_language", d["content"])
        self.assertIn("中文", d["content"])

    def test_sync_is_idempotent(self):
        r1 = self.b.mb_sync()
        r2 = self.b.mb_sync()
        self.assertEqual(r1["written"], r2["written"])
        t1 = self.b.vault_tree("mb")
        self.assertEqual(len(t1), 4)

    def test_auto_notes_searchable(self):
        self.b.mb_sync()
        hits = self.b.vault_search("mb", "to do")
        self.assertTrue(any(h["path"] == "_auto/todo.md" for h in hits))


if __name__ == "__main__":
    unittest.main(verbosity=2)
