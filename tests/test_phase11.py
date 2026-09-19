"""Phase 11 — WorkDesk 2.0 backend tests.

Covers: Obsidian-style vault (CRUD/search/traversal), clear-history,
GitHub-skill worker design (mocked fetch), worker create/merge/update,
and worker studio read model. All filesystem roots are redirected to
temporary directories so production data is never touched.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["WORKDESK_DB"] = str(Path(tempfile.mkdtemp(prefix="p11_db_")) / "p11.db")

import core.config as app_config  # noqa: E402
_TMP_CONV = Path(tempfile.mkdtemp(prefix="p11_conv_"))
_TMP_PROJ = Path(tempfile.mkdtemp(prefix="p11_proj_"))
app_config.CONV_DIR = _TMP_CONV
app_config.PROJ_DIR = _TMP_PROJ

from bridge import WorkDeskBridge  # noqa: E402

_TMP_WS = Path(tempfile.mkdtemp(prefix="p11_ws_"))
_TMP_VAULT = Path(tempfile.mkdtemp(prefix="p11_vault_"))
WorkDeskBridge.WS_ROOT = _TMP_WS
WorkDeskBridge.VAULT_ROOT = _TMP_VAULT

FAKE_SKILL = """---
name: Research Deep Dive
description: Deep research and web scraping agent that gathers sources, searches the web and writes findings.
---

Use the browser to search the web, crawl pages and collect citations.
"""


class TestVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def test_save_read_tree_search_delete(self):
        r = self.b.vault_save("my", "projects/workdesk.md",
                              "# WorkDesk\n\nA personal AI OS. See [[main-brain]].")
        self.assertTrue(r["ok"])
        d = self.b.vault_read("my", "projects/workdesk.md")
        self.assertEqual(d["content"].startswith("# WorkDesk"), True)
        self.assertEqual(d["links"], ["main-brain"])
        tree = self.b.vault_tree("my")
        self.assertTrue(any(f["path"] == "projects/workdesk.md" for f in tree))
        hits = self.b.vault_search("my", "personal ai os")
        self.assertTrue(any(h["path"] == "projects/workdesk.md" for h in hits))
        self.b.vault_delete("my", "projects/workdesk.md")
        self.assertEqual(self.b.vault_read("my", "projects/workdesk.md")["error"], "not_found")

    def test_traversal_denied(self):
        r = self.b.vault_save("my", "../../evil.md", "x")
        self.assertEqual(r.get("error"), "invalid_path")
        self.assertEqual(self.b.vault_read("my", "../workdesk.db").get("error"), "not_found")

    def test_section_isolation(self):
        self.b.vault_save("mb", "mb-note.md", "memory")
        self.assertEqual(len(self.b.vault_tree("mb")), 1)
        self.assertEqual(len(self.b.vault_tree("my")), 0)


class TestClearHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def setUp(self):
        app_config.CONV_DIR.mkdir(parents=True, exist_ok=True)
        app_config.PROJ_DIR.mkdir(parents=True, exist_ok=True)

    def test_clears_chats_tasks_audit(self):
        (app_config.CONV_DIR / "conv-x.json").write_text("{}", encoding="utf-8")
        (app_config.PROJ_DIR / "proj-x.json").write_text("{}", encoding="utf-8")
        from src.workdesk import db as wd_db
        wd_db.execute("INSERT INTO tasks(task_id, request_text, state) VALUES('t1','req','done')")
        wd_db.execute("INSERT INTO approvals(approval_id, request_id, status) VALUES('a1','r1','pending')")
        wd_db.execute("INSERT INTO audit_events(ts, action) VALUES('now','run')")
        r = self.b.clear_history("all")
        self.assertTrue(r["ok"])
        self.assertEqual(len(list(app_config.CONV_DIR.glob("*.json"))), 0)
        self.assertEqual(len(list(app_config.PROJ_DIR.glob("*.json"))), 0)
        self.assertEqual(wd_db.query_one("SELECT COUNT(*) FROM tasks")[0], 0)
        self.assertEqual(wd_db.query_one("SELECT COUNT(*) FROM approvals")[0], 0)
        self.assertEqual(wd_db.query_one("SELECT COUNT(*) FROM audit_events")[0], 0)


class TestWorkerDesign(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()
        cls.b._locate_skill = lambda owner, repo, branch, subpath="": ("SKILL.md", FAKE_SKILL)
    def test_design_from_skill(self):
        d = self.b.worker_design("https://github.com/acme/research-agent")
        self.assertNotIn("error", d)
        c = d["candidate"]
        self.assertEqual(c["name"], "Research Deep Dive")
        self.assertEqual(c["studio_type"], "research")
        self.assertIn("BROWSER", [t["tool"] for t in c["tools"]])
        self.assertIn("TERMINAL", [t["tool"] for t in c["tools"]])
        self.assertIsInstance(d["matches"], list)

    def test_apply_create_and_merge_and_update(self):
        d = self.b.worker_design("https://github.com/acme/research-agent")
        c = d["candidate"]
        r = self.b.worker_apply(c, "create")
        self.assertTrue(r["ok"])
        wid = r["worker_id"]
        # idempotent update (edit worker)
        u = self.b.worker_update(wid, {"name": "Research Deep Dive v2"})
        self.assertTrue(u["ok"])
        self.assertEqual(self.b.engine.registry.get_worker(wid)["name"], "Research Deep Dive v2")
        # merge into an existing worker (researcher)
        merged = self.b.worker_apply(c, "merge", "researcher")
        self.assertTrue(merged["ok"])
        self.assertEqual(merged["worker_id"], "researcher")
        rw = self.b.engine.registry.get_worker("researcher")
        caps = {s.get("capability") for s in (rw.get("skills") or [])}
        self.assertIn("research-deep-dive", caps)

    def test_studio_read_model(self):
        d = self.b.worker_design("https://github.com/acme/research-agent")
        r = self.b.worker_apply(d["candidate"], "create")
        st = self.b.worker_studio(r["worker_id"])
        self.assertEqual(st["studio_type"], "research")
        self.assertIn("worker", st)
        self.assertIn("feed", st)


if __name__ == "__main__":
    unittest.main(verbosity=2)
