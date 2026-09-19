"""Phase 10 — personal utilities & working area backend tests.

Covers the workspace file API (save/read/list/delete + traversal escape),
the notes API (save/list/delete + section isolation), and the sandboxed
code runner (ok path + failing code). The bridge is constructed against a
temporary WORKDESK_DB so the real production database is untouched.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ["WORKDESK_DB"] = str(Path(tempfile.mkdtemp()) / "p10.db")

from bridge import WorkDeskBridge  # noqa: E402

# Isolate the workspace root so tests never touch the production data dir.
_TMP_WS = Path(tempfile.mkdtemp(prefix="p10_ws_"))
WorkDeskBridge.WS_ROOT = _TMP_WS


class TestWorkspaceFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def setUp(self):
        self.b.ws_delete("code/t.py")
        self.b.ws_delete("notes/n.md")
        self.b.notes_delete("__test__")

    def test_save_read_list_delete(self):
        r = self.b.ws_save("code/hello.py", "print(1)")
        self.assertTrue(r["ok"])
        d = self.b.ws_read("code/hello.py")
        self.assertEqual(d["content"], "print(1)")
        listing = self.b.ws_list()["files"]
        self.assertTrue(any(f["path"] == "code/hello.py" for f in listing))
        self.b.ws_delete("code/hello.py")
        self.assertEqual(self.b.ws_read("code/hello.py")["error"], "not_found")

    def test_traversal_escape_denied(self):
        r = self.b.ws_save("../../evil.txt", "nope")
        self.assertEqual(r.get("error"), "invalid_path")
        d = self.b.ws_read("../workdesk.db")
        self.assertEqual(d.get("error"), "not_found")
        r = self.b.ws_upload("a.txt", b"x", subdir="../..")
        self.assertEqual(r.get("error"), "invalid_path")

    def test_upload_bytes(self):
        r = self.b.ws_upload("pic.png", b"\x89PNG", subdir="media")
        self.assertTrue(r["ok"])
        self.assertEqual(self.b.ws_read("media/pic.png")["error"], "binary")
        self.b.ws_delete("media/pic.png")


class TestNotes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def test_save_list_section_delete(self):
        r = self.b.notes_save(None, "user", "t1", "body")
        self.assertTrue(r["ok"])
        uid = r["note_id"]
        self.b.notes_save(None, "mb", "m1", "mb body")
        user = self.b.notes_list("user")
        self.assertEqual(len(user), 1)
        self.assertEqual(user[0]["title"], "t1")
        mb = self.b.notes_list("mb")
        self.assertEqual(len(mb), 1)
        self.assertEqual(mb[0]["title"], "m1")
        # update in place
        self.b.notes_save(uid, "user", "t1 v2", "body2")
        self.assertEqual(self.b.notes_list("user")[0]["content"], "body2")
        self.b.notes_delete(uid)
        self.assertEqual(len(self.b.notes_list("user")), 0)


class TestCodeRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = WorkDeskBridge()

    def test_run_ok(self):
        r = self.b.code_run("print(6*7)")
        self.assertTrue(r["ok"])
        self.assertEqual(r["stdout"].strip(), "42")

    def test_run_error(self):
        r = self.b.code_run("raise ValueError('boom')")
        self.assertFalse(r["ok"])
        self.assertIn("boom", r["stderr"])

    def test_code_too_large(self):
        r = self.b.code_run("x" * 70_000)
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("error"), "code_too_large")


if __name__ == "__main__":
    unittest.main(verbosity=2)
