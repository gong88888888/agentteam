#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate versioned role prompts from specs + local skills.

  python prompts/build_prompts.py

Writes:
  prompts/roles/<role>.md                  baseline v1
  prompts/candidates/strict-json/<role>.md candidate v2 (stricter JSON contract)
  prompts/registry.yaml                    role/version/hash/skills
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.skills import SkillRegistry  # noqa: E402


def base_prompt(spec: dict, skills_text: str) -> str:
    return f"""---
role: {spec['id']}
version: 1
generated_from: specs/agent-specs.yaml
skills: {json.dumps(spec.get('skills', []), ensure_ascii=False)}
---
# ROLE: {spec['id']}

{spec['role']}

## 工具白名单
{json.dumps(spec['tools'], ensure_ascii=False, indent=2)}

## 读写范围
{json.dumps(spec['scope'], ensure_ascii=False, indent=2)}

## 禁止事项
{json.dumps(spec['prohibitions'], ensure_ascii=False, indent=2)}

## 输出契约
只输出一个 JSON 对象，必须符合 `specs/agent-output.schema.json`：
- `task_id`、`role`、`status`、`artifacts`、`claims`、`evidence_refs`、`open_questions`、`summary`
- `claims` 不参与门禁，`counts_as_evidence` 必须为 false
- `artifacts` 每项必须含 `path` 和 `sha256`；没有真实产物时使用 `[]`
示例：{{"task_id":"T-1","role":"{spec['id']}","status":"done","artifacts":[],"claims":[{{"claim":"一句话结论","counts_as_evidence":false}}],"evidence_refs":[],"open_questions":[],"summary":"..."}}

## 失败处理
{json.dumps(spec['failure_policy'], ensure_ascii=False, indent=2)}

{skills_text}
"""


def candidate_prompt(spec: dict, skills_text: str) -> str:
    body = base_prompt(spec, skills_text).replace("version: 1", "version: 2", 1)
    return body + """
## 严格输出契约（候选 v2）
- 输出必须是一个 JSON 对象，不要 Markdown 代码块、不要解释文字。
- `claims` 至少 1 条，每条只包含 `claim` 与 `counts_as_evidence`（可选 `evidence_refs`）。
- `artifacts` 每项只包含 `path` 与 `sha256`；没有真实产物用 `[]`。
- `status` 只能是 done / need_evidence / blocked；`role` 必须等于本角色。
- 输出前自检：字段齐全、JSON 可解析、没有额外顶层字段。
"""


def main() -> None:
    specs = yaml.safe_load((ROOT / "specs" / "agent-specs.yaml").read_text(encoding="utf-8"))["specs"]
    registry = SkillRegistry.load(ROOT / "skills" / "registry.yaml")
    if registry.errors:
        raise SystemExit("技能注册表错误：" + "; ".join(registry.errors))
    roles = HERE / "roles"
    cand = HERE / "candidates" / "strict-json"
    roles.mkdir(parents=True, exist_ok=True)
    cand.mkdir(parents=True, exist_ok=True)
    entries = []
    for spec in specs:
        skills_text = registry.prompt_context(spec["id"]) or "可用本地技能：无"
        v1 = base_prompt(spec, skills_text)
        v2 = candidate_prompt(spec, skills_text)
        (roles / f"{spec['id']}.md").write_text(v1, encoding="utf-8")
        (cand / f"{spec['id']}.md").write_text(v2, encoding="utf-8")
        entries.append({
            "role": spec["id"],
            "version": 1,
            "file": f"roles/{spec['id']}.md",
            "hash": hashlib.sha256(v1.encode("utf-8")).hexdigest()[:16],
            "skills": spec.get("skills", []),
        })
        entries.append({
            "role": spec["id"],
            "version": 2,
            "variant": "strict-json",
            "file": f"candidates/strict-json/{spec['id']}.md",
            "hash": hashlib.sha256(v2.encode("utf-8")).hexdigest()[:16],
            "skills": spec.get("skills", []),
        })
    doc = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "baseline": "roles", "candidate": "candidates/strict-json",
           "entries": entries}
    (HERE / "registry.yaml").write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"generated {len(specs)} baseline + {len(specs)} candidate prompts")


if __name__ == "__main__":
    main()
