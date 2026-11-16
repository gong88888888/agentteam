#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the self-contained W3 monitoring dashboard.

  python dashboard/build.py

Reads sim/out/w3/{parallel,serial} and writes dashboard/index.html with
embedded JSON, so the page opens offline with no server or CDN.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
W3 = ROOT / "sim" / "out" / "w3"


def ensure_outputs() -> None:
    needed = [
        W3 / "comparison.json",
        W3 / "parallel" / "metrics.json",
        W3 / "parallel" / "events.jsonl",
        W3 / "parallel" / "impact.json",
        W3 / "serial" / "metrics.json",
        W3 / "serial" / "events.jsonl",
        W3 / "serial" / "impact.json",
    ]
    if all(p.exists() for p in needed):
        return
    print("W3 outputs missing; running sim/w3.py --mode both ...")
    subprocess.run([sys.executable, str(ROOT / "sim" / "w3.py"), "--mode", "both"],
                   cwd=str(ROOT), check=True)


def load_mode(name: str) -> dict:
    base = W3 / name
    metrics = json.loads((base / "metrics.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in
              (base / "events.jsonl").read_text(encoding="utf-8").splitlines()
              if line.strip()]
    impact = json.loads((base / "impact.json").read_text(encoding="utf-8"))
    return {"metrics": metrics, "events": events, "impact": impact}


def main() -> None:
    ensure_outputs()
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "project": "MiniLedger · W3",
        "comparison": json.loads((W3 / "comparison.json").read_text(encoding="utf-8")),
        "modes": {
            "parallel": load_mode("parallel"),
            "serial": load_mode("serial"),
        },
    }
    payload = json.dumps(data, ensure_ascii=False,
                         separators=(",", ":")).replace("</", "<\\/")
    (HERE / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    template = (HERE / "template.html").read_text(encoding="utf-8")
    html = template.replace("__DATA_JSON__", payload)
    (HERE / "index.html").write_text(html, encoding="utf-8")
    print(f"built {HERE / 'index.html'}")
    print(f"events: {len(data['modes']['parallel']['events'])} parallel / "
          f"{len(data['modes']['serial']['events'])} serial")


if __name__ == "__main__":
    main()
