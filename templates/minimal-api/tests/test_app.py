"""Runnable evidence for the minimal API scaffold."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.app import export_csv, health_payload, monthly_csv  # noqa: E402


class MonthlyCsvTest(unittest.TestCase):
    def test_header_and_filter(self) -> None:
        text = monthly_csv([
            {"month": "2026-02", "date": "2026-02-01", "amount": "10",
             "category": "food", "note": "lunch"},
            {"month": "2026-01", "date": "2026-01-31", "amount": "5",
             "category": "transport", "note": ""},
        ], "2026-02")
        lines = text.strip().splitlines()
        self.assertEqual(lines[0], "date,amount,category,note")
        self.assertEqual(len(lines), 2)
        self.assertIn("2026-02-01", lines[1])

    def test_quotes_special_values(self) -> None:
        text = monthly_csv([
            {"month": "2026-02", "date": "2026-02-02", "amount": "1",
             "category": "misc", "note": 'a,b"c'},
        ], "2026-02")
        self.assertIn('"a,b""c"', text)

    def test_health(self) -> None:
        self.assertEqual(health_payload(), {"status": "ok"})

    def test_export_csv_business_flow(self) -> None:
        text = export_csv("2026-02")
        lines = text.strip().splitlines()
        self.assertEqual(lines[0], "date,amount,category,note")
        self.assertIn("2026-02-01", lines[1])

    def test_export_empty_month_is_header_only(self) -> None:
        self.assertEqual(export_csv("1999-01").strip(),
                         "date,amount,category,note")


if __name__ == "__main__":
    unittest.main()
