"""Rubric loading and gate-to-rubric mapping."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..config import ROOT
from ..evidence.signing import sha256_hex


@dataclass
class Rubric:
    id: str
    version: str
    data: dict[str, Any]
    hash: str

    def for_prompt(self) -> dict[str, Any]:
        return {"id": self.id, "version": self.version,
                "mandatory": self.data.get("mandatory", []),
                "scored": self.data.get("scored", []),
                "auto_reject": self.data.get("auto_reject", [])}


def load_rubric(name_or_path: str) -> Rubric:
    p = Path(name_or_path)
    if not p.exists():
        p = ROOT / "rubrics" / f"{name_or_path.removesuffix('.yaml')}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"rubric 不存在：{name_or_path}")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not data.get("id") or not data.get("version"):
        raise ValueError(f"rubric 缺少 id/version：{p}")
    return Rubric(data["id"], str(data["version"]), data,
                  sha256_hex({"id": data["id"], "version": data["version"],
                              "data": data}))


def rubric_for_gate(gate_id: str, decision_type: str = "gate") -> Rubric:
    g = gate_id.upper()
    if decision_type == "release" or "RELEASE" in g:
        return load_rubric("release-gate")
    if "ACCEPT" in g or decision_type in ("project_close",):
        return load_rubric("acceptance-gate")
    if any(x in g for x in ("S1", "S2", "S3", "CODE")):
        return load_rubric("code-gate")
    if "ARCH" in g:
        return load_rubric("arch-gate")
    if "PRODUCT" in g:
        return load_rubric("product-gate")
    return load_rubric("code-gate")
