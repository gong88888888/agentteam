#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 specs/ 下的 JSON Schema 可解析、12 份 Agent 规格书满足 9 字段要求。

不依赖第三方 jsonschema；这里做结构性校验，真实实现应接入 jsonschema/OPA。
运行：python -I specs/validate_specs.py
"""
from __future__ import annotations

import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
REQUIRED = ["id", "role", "tools", "scope", "input_contract", "output_contract",
            "examples", "failure_policy", "budget", "prohibitions"]
ROLES = {"pm", "product", "ui", "arch", "frontend", "backend",
         "review", "qa", "security", "ops", "kb", "retro"}


def check_schema(name: str) -> None:
    path = os.path.join(HERE, name)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if data.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError(f"{name}: 缺少 2020-12 $schema")
    if "required" not in data:
        raise ValueError(f"{name}: 缺少 required")


def main() -> None:
    for name in ("agent-spec.schema.json", "task-card.schema.json",
                 "evidence.schema.json", "decision-packet.schema.json",
                 "verdict.schema.json", "agent-output.schema.json",
                 "product-review-output.schema.json"):
        check_schema(name)
    with open(os.path.join(HERE, "agent-specs.yaml"), encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    specs = doc["specs"]
    from orchestrator.skills import SkillRegistry
    skill_registry = SkillRegistry.load(os.path.join(ROOT, "skills", "registry.yaml"))
    if skill_registry.errors:
        raise ValueError("技能注册表错误：" + "; ".join(skill_registry.errors))
    skill_names = skill_registry.names()
    ids = [s["id"] for s in specs]
    if len(specs) != 12:
        raise ValueError(f"需要 12 份规格书，实际 {len(specs)}")
    if len(set(ids)) != 12:
        raise ValueError(f"id 重复：{ids}")
    if set(ids) != ROLES:
        raise ValueError(f"角色集合不一致：{set(ids) ^ ROLES}")
    for s in specs:
        missing = [k for k in REQUIRED if k not in s]
        if missing:
            raise ValueError(f"{s['id']} 缺少字段：{missing}")
        if not s["tools"] or not all("name" in t and "allow" in t for t in s["tools"]):
            raise ValueError(f"{s['id']} tools 不合法")
        if set(s["scope"]) != {"read", "write", "deny"}:
            raise ValueError(f"{s['id']} scope 不合法")
        for key in ("input_contract", "output_contract"):
            if not s[key].endswith(".json"):
                raise ValueError(f"{s['id']} {key} 必须是 schema 文件")
        for key in ("good", "bad"):
            if not s["examples"].get(key):
                raise ValueError(f"{s['id']} examples.{key} 为空")
        if not s["failure_policy"].get("escalate_if"):
            raise ValueError(f"{s['id']} failure_policy.escalate_if 为空")
        for key in ("max_tokens", "max_minutes", "max_usd"):
            if key not in s["budget"]:
                raise ValueError(f"{s['id']} budget.{key} 缺失")
        if not s["prohibitions"]:
            raise ValueError(f"{s['id']} prohibitions 为空")
        for skill in s.get("skills", []):
            if skill not in skill_names:
                raise ValueError(f"{s['id']} 引用了未注册技能：{skill}")
    print(f"OK: {len(specs)} 份 Agent 规格书，7 个 Schema 可解析")


if __name__ == "__main__":
    main()
