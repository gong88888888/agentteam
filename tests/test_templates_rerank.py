from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.knowledge.embed import HashingEmbedder  # noqa: E402
from orchestrator.knowledge.rerank import rerank_hits  # noqa: E402
from orchestrator.templates import apply_template, get_template  # noqa: E402


class TemplateTest(unittest.TestCase):
    def test_apply_and_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            rec = apply_template(p, "minimal-api")
            self.assertIn("src/backend/app.py", rec["copied"])
            (p / "src" / "backend" / "app.py").write_text("custom\n", encoding="utf-8")
            rec2 = apply_template(p, "minimal-api")
            self.assertIn("src/backend/app.py", rec2["skipped"])
            self.assertEqual((p / "src" / "backend" / "app.py").read_text(
                encoding="utf-8"), "custom\n")

    def test_registry(self) -> None:
        self.assertIsNotNone(get_template("minimal-api"))


class RerankTest(unittest.TestCase):
    def test_reorders_and_keeps_base(self) -> None:
        cands = [
            {"chunk_id": 1, "heading": "Other", "text": "unrelated words",
             "path": "a.md", "score": 0.03},
            {"chunk_id": 2, "heading": "Lock lease", "text": "shared file lock lease",
             "path": "b.md", "score": 0.02},
        ]
        out = rerank_hits("shared file lock", cands, HashingEmbedder(), 2)
        self.assertEqual(out[0]["chunk_id"], 2)
        self.assertIn("base_score", out[0])
        self.assertIn("citation", out[0])
        self.assertGreaterEqual(out[0]["rerank_score"], out[1]["rerank_score"])


if __name__ == "__main__":
    unittest.main()
