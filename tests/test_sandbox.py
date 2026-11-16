from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.sandbox import (IsolatedWorkspace, Sandbox, SandboxError,
                                  tree_hash)


class SandboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_allowlist_and_shell_metacharacters(self) -> None:
        sb = Sandbox(self.root)
        with self.assertRaises(SandboxError):
            sb.validate(["bash", "-c", "echo hi"])
        with self.assertRaises(SandboxError):
            sb.validate(["python", "-c", "print(1); print(2)"])

    def test_env_scrubs_secrets(self) -> None:
        sb = Sandbox(self.root)
        (self.root / "env_probe.py").write_text(
            "import os;print(os.environ.get('DEEPSEEK_API_KEY','MISSING'))\n",
            encoding="utf-8")
        r = sb.run([sys.executable, "env_probe.py"],
                   extra_env={"DEEPSEEK_API_KEY": "secret-value"})
        self.assertTrue(r.ok, r.stderr)
        self.assertEqual(r.stdout.strip(), "MISSING")

    def test_timeout(self) -> None:
        sb = Sandbox(self.root, timeout_s=1)
        (self.root / "sleep_probe.py").write_text(
            "import time;time.sleep(3)\n", encoding="utf-8")
        r = sb.run([sys.executable, "sleep_probe.py"])
        self.assertTrue(r.timed_out)
        self.assertEqual(r.exit_code, 124)

    def test_tree_hash_tracks_src(self) -> None:
        h1 = tree_hash(self.root)
        (self.root / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")
        self.assertNotEqual(h1, tree_hash(self.root))

    def test_workspace_copy_and_promote(self) -> None:
        ws = IsolatedWorkspace(self.root, "backend")
        with ws:
            self.assertIsNotNone(ws.path)
            (ws.path / "src" / "new.py").write_text("y = 2\n", encoding="utf-8")
            promoted = ws.promote(["src/new.py"])
            self.assertEqual(promoted, ["src/new.py"])
            tmp_path = ws.path
        self.assertTrue((self.root / "src" / "new.py").is_file())
        self.assertFalse(tmp_path.exists())

    def test_promote_rejects_traversal(self) -> None:
        ws = IsolatedWorkspace(self.root, "backend")
        with ws:
            with self.assertRaises(SandboxError):
                ws.promote(["../outside.py"])


if __name__ == "__main__":
    unittest.main()
