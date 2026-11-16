"""Reusable project scaffolds for role-based runs.

Templates are data, not generated claims: copying a scaffold never satisfies a
role gate. Gates inspect the role's own output and tool evidence.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from .config import ROOT

TEMPLATES_ROOT = ROOT / "templates"
REGISTRY = TEMPLATES_ROOT / "registry.yaml"


def list_templates() -> list[dict[str, Any]]:
    if not REGISTRY.exists():
        return []
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    return data.get("templates", [])


def get_template(template_id: str) -> dict[str, Any] | None:
    return next((t for t in list_templates() if t.get("id") == template_id), None)


def template_hash(template_id: str) -> str:
    base = TEMPLATES_ROOT / template_id
    h = hashlib.sha256()
    for f in sorted(p for p in base.rglob("*") if p.is_file()):
        h.update(f.relative_to(base).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(f.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16]


def apply_template(project_dir: str | Path, template_id: str,
                   *, overwrite: bool = False) -> dict[str, Any]:
    if template_id in ("", "none"):
        return {"template": "none", "copied": [], "skipped": []}
    meta = get_template(template_id)
    base = TEMPLATES_ROOT / template_id
    if not meta or not base.is_dir():
        raise ValueError(f"未知模板：{template_id}")
    project_dir = Path(project_dir).resolve()
    copied: list[str] = []
    skipped: list[str] = []
    for src in sorted(p for p in base.rglob("*") if p.is_file()):
        rel = src.relative_to(base)
        dst = project_dir / rel
        if dst.exists() and not overwrite:
            skipped.append(rel.as_posix())
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied.append(rel.as_posix())
    record = {
        "template": template_id,
        "title": meta.get("title", template_id),
        "hash": template_hash(template_id),
        "copied": copied,
        "skipped": skipped,
        "overwrite": overwrite,
    }
    state = project_dir / ".agentteam"
    state.mkdir(parents=True, exist_ok=True)
    (state / "template.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record
