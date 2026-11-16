"""Deterministic requirement selection with a readable decision record."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

WEIGHTS = {"value": 2, "strategic_fit": 2, "effort": 1, "risk": 1,
           "dependency": 1}


@dataclass
class Requirement:
    id: str
    title: str
    description: str = ""
    users: list[str] = field(default_factory=list)
    value: int = 1
    effort: int = 1
    risk: int = 1
    dependency: int = 0
    strategic_fit: int = 1
    acceptance: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    def validate(self) -> None:
        for key in ("value", "effort", "risk", "dependency", "strategic_fit"):
            v = getattr(self, key)
            if not isinstance(v, int) or not 0 <= v <= 2:
                raise ValueError(f"{self.id}.{key} 必须是 0-2 的整数")
        if not self.id or not self.title:
            raise ValueError("requirement 缺少 id/title")
        if not self.acceptance:
            raise ValueError(f"{self.id} 缺少验收标准")

    @property
    def raw_score(self) -> int:
        return (self.value * 2 + self.strategic_fit * 2
                + (2 - self.effort) + (2 - self.risk) + (2 - self.dependency))

    @property
    def score(self) -> float:
        return round(self.raw_score / 12 * 10, 1)

    def band(self) -> str:
        if self.depends_on:
            return "next"
        if self.score >= 8:
            return "now"
        if self.score >= 6:
            return "next"
        return "later"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "description": self.description,
            "users": self.users, "value": self.value, "effort": self.effort,
            "risk": self.risk, "dependency": self.dependency,
            "strategic_fit": self.strategic_fit, "acceptance": self.acceptance,
            "non_goals": self.non_goals, "constraints": self.constraints,
            "tags": self.tags, "depends_on": self.depends_on,
        }


def load_backlog(path: str | Path) -> tuple[str, list[Requirement]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    reqs = []
    for raw in data.get("requirements") or []:
        req = Requirement(**raw)
        req.validate()
        reqs.append(req)
    if not reqs:
        raise ValueError("backlog 没有 requirements")
    return str(data.get("project", "project")), reqs


def select(backlog: str | Path, out_dir: str | Path) -> dict[str, Any]:
    project, reqs = load_backlog(backlog)
    ranked = sorted(reqs, key=lambda r: (r.score, r.value, -r.effort), reverse=True)
    chosen = next((r for r in ranked if r.band() == "now"), ranked[0])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "selected.yaml").write_text(
        yaml.safe_dump({"project": project, "selected": chosen.to_dict(),
                        "score": chosen.score, "band": chosen.band()},
                       allow_unicode=True, sort_keys=False), encoding="utf-8")
    lines = [
        f"# {project} 需求选择", "",
        f"- 选中：**{chosen.title}**（{chosen.id}）",
        f"- 评分：{chosen.score}/10 · 分类：{chosen.band()}",
        f"- 理由：价值 {chosen.value}/2 · 战略 {chosen.strategic_fit}/2 · "
        f"工作量 {chosen.effort}/2 · 风险 {chosen.risk}/2 · 依赖 {chosen.dependency}/2",
        "", "| 需求 | 价值 | 战略 | 工作量 | 风险 | 依赖 | 评分 | 分类 |",
        "|---|---|---|---|---|---|---|---|",
        *[f"| {r.title} | {r.value} | {r.strategic_fit} | {r.effort} | "
          f"{r.risk} | {r.dependency} | {r.score} | {r.band()} |" for r in ranked],
        "",
        "## 选择规则", "",
        "评分 = (价值×2 + 战略×2 + (2-工作量) + (2-风险) + (2-依赖)) / 12 × 10。",
        "≥8 进入 now；6-8 进入 next；<6 进入 later；有未满足依赖一律 next。",
        "选择是**策略所有者设定的确定性规则**，不由执行 Agent 自由扩范围；"
        "模型只可用于补充风险/验收澄清。",
        "",
    ]
    (out / "selection.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    md = [
        f"# 需求：{chosen.title}", "",
        f"- ID：{chosen.id}",
        f"- 项目：{project}",
        f"- 评分：{chosen.score}/10（{chosen.band()}）",
        f"- 目标用户：{', '.join(chosen.users) or '未指定'}",
        f"- 标签：{', '.join(chosen.tags) or '无'}",
        "", "## 目标", "", chosen.description or chosen.title, "",
        "## 非目标", "", *([f"- {x}" for x in chosen.non_goals] or ["- 未指定"]), "",
        "## 验收标准", "", *[f"- {x}" for x in chosen.acceptance], "",
        "## 约束", "", *([f"- {x}" for x in chosen.constraints] or ["- 未指定"]), "",
    ]
    (out / "selected.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"project": project, "selected": chosen.to_dict(),
            "score": chosen.score, "band": chosen.band(),
            "ranked": [{"id": r.id, "title": r.title, "score": r.score,
                        "band": r.band()} for r in ranked],
            "out_dir": str(out)}


def show(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if p.suffix in (".yaml", ".yml"):
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    return {"path": str(p), "text": p.read_text(encoding="utf-8")}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Requirement selection")
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select")
    s.add_argument("--backlog", required=True)
    s.add_argument("--out", required=True)
    sh = sub.add_parser("show")
    sh.add_argument("--file", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "select":
        print(json.dumps(select(args.backlog, args.out), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(show(args.file), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
