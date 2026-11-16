#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W3 regression: parallel vs serial, shared-file conflicts, contract impact, dashboard.

Run: python sim/w3_selfcheck.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import w3  # noqa: E402


def main() -> None:
    print("W3 selfcheck")
    p = w3.run_mode("parallel")
    s = w3.run_mode("serial")
    assert p["status"] == "completed", p["status"]
    assert s["status"] == "completed", s["status"]
    assert p["lock_conflicts"] >= 1, p["lock_conflicts"]
    assert s["lock_conflicts"] == 0, s["lock_conflicts"]
    assert p["contract_changes"] == 1
    assert p["contract_impacted_tasks"] == 6
    assert s["contract_impacted_tasks"] == 6
    assert p["contract_evidence_invalidated"] >= 1
    assert p["elapsed_minutes"] < s["elapsed_minutes"]
    assert p["peak_concurrency"] > s["peak_concurrency"]
    print("  parallel/serial OK:", p["elapsed_minutes"], "vs",
          s["elapsed_minutes"], "min")
    print("  shared-file conflicts:", p["lock_conflicts"], "/",
          s["lock_conflicts"])
    print("  contract impact tasks:", p["contract_impacted_tasks"])

    subprocess.run([sys.executable, str(ROOT / "dashboard" / "build.py")],
                   cwd=str(ROOT), check=True)
    index = ROOT / "dashboard" / "index.html"
    assert index.exists() and index.stat().st_size > 100_000
    text = index.read_text(encoding="utf-8")
    assert "W3 Delivery Monitor" in text and "task-bar" in text
    print("  dashboard OK:", index.stat().st_size, "bytes")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
