"""Versioned role prompt registry."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ROOT

PROMPTS = ROOT / "prompts"
ROLES = PROMPTS / "roles"
FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass
class Prompt:
    role: str
    version: int
    text: str
    hash: str
    path: Path

    def metadata(self) -> dict[str, Any]:
        return {"role": self.role, "version": self.version,
                "hash": self.hash, "path": str(self.path.relative_to(ROOT))}


def _parse(text: str) -> tuple[dict[str, Any], str]:
    m = FRONTMATTER.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, text[m.end():]


def load_prompt(role: str, prompt_dir: str | Path | None = None) -> Prompt:
    base = Path(prompt_dir) if prompt_dir else Path(
        os.environ.get("AGENT_PROMPT_DIR", ROLES))
    if not base.is_absolute():
        base = ROOT / base
    path = base.resolve() / f"{role}.md"
    if not path.exists():
        raise FileNotFoundError(f"角色提示词不存在：{path}")
    text = path.read_text(encoding="utf-8")
    meta, _ = _parse(text)
    if meta.get("role") and meta["role"] != role:
        raise ValueError(f"{path} frontmatter role={meta['role']} 与 {role} 不一致")
    return Prompt(role=role, version=int(meta.get("version", 1)), text=text,
                  hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                  path=path)


def load_registry() -> dict[str, Any]:
    path = PROMPTS / "registry.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def list_prompts() -> list[dict[str, Any]]:
    return [
        {"role": p.stem, "version": _parse(p.read_text(encoding="utf-8"))[0].get("version", 1),
         "path": str(p.relative_to(ROOT))}
        for p in sorted(ROLES.glob("*.md"))
    ]


def agent_messages(role: str, task: str, prompt_dir: str | Path | None = None,
                   prompt: Prompt | None = None) -> tuple[list[dict[str, str]], Prompt]:
    p = prompt or load_prompt(role, prompt_dir)
    return ([{"role": "system", "content": p.text},
             {"role": "user", "content": task}], p)
