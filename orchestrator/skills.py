"""Local skill registry.

Skills live under RAG-Agent-Toolkit/agent-toolkit/skills. They are prompt-time
references, not executable plugins: the agent is told to read the SKILL.md
before doing the corresponding work.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ROOT


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    agents: list[str]
    triggers: list[str]

    def relative(self) -> str:
        try:
            return str(self.path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            return str(self.path)


def _frontmatter(text: str) -> dict[str, Any]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


class SkillRegistry:
    def __init__(self, skills: dict[str, Skill], errors: list[str]) -> None:
        self.skills = skills
        self.errors = errors

    @classmethod
    def load(cls, registry_path: str | Path | None = None) -> "SkillRegistry":
        path = Path(registry_path) if registry_path else ROOT / "skills" / "registry.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        root = ROOT / data.get("root", "RAG-Agent-Toolkit/agent-toolkit/skills")
        skills: dict[str, Skill] = {}
        errors: list[str] = []
        for name, meta in (data.get("skills") or {}).items():
            p = root / meta.get("path", "")
            if not p.exists():
                errors.append(f"{name}: 文件不存在 {p}")
                continue
            fm = _frontmatter(p.read_text(encoding="utf-8"))
            actual = fm.get("name", name)
            if actual != name:
                errors.append(f"{name}: frontmatter name={actual!r} 不一致")
            skills[name] = Skill(
                name=name,
                description=meta.get("description") or fm.get("description", ""),
                path=p,
                agents=list(meta.get("agents") or []),
                triggers=list(meta.get("triggers") or []),
            )
        return cls(skills, errors)

    def for_role(self, role: str) -> list[Skill]:
        return [s for s in self.skills.values() if role in s.agents]

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)

    def names(self) -> set[str]:
        return set(self.skills)

    def prompt_context(self, role: str, max_chars: int = 1600) -> str:
        items = self.for_role(role)
        if not items:
            return ""
        lines = ["可用本地技能（在开始工作前先读取对应 SKILL.md，不要凭记忆代替）："]
        for s in items:
            line = f"- {s.name}: {s.description}（{s.relative()}）"
            if sum(len(x) + 1 for x in lines) + len(line) > max_chars:
                break
            lines.append(line)
        return "\n".join(lines)

    def report(self) -> dict[str, Any]:
        return {
            "skills": [{"name": s.name, "description": s.description,
                        "path": s.relative(), "agents": s.agents}
                       for s in self.skills.values()],
            "errors": self.errors,
        }
