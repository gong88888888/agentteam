#!/usr/bin/env python3
"""Build the reusable product-review team prompts."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "prompts" / "product-team"

ROLES = [
    ("product-lead", "产品负责人", "00-brief.md",
     "定义本次产品文档深析的目标、范围、成功指标、非目标、决策问题；主持最终参考方案。",
     "目标、成功指标、非目标、决策问题"),
    ("doc-analyst", "产品文档分析师", "01-document-map.md",
     "逐段建立来源地图：章节 ID、主张、用户价值、前置条件、歧义、缺失证据和与其他章节的冲突；必须输出覆盖率和 SRC 引用。",
     "来源章节、主张、歧义、覆盖率、SRC"),
    ("user-researcher", "用户与场景研究员", "02-users-journeys.md",
     "按目标用户拆 Jobs-to-be-done、关键时刻、当前替代方案、痛点、旅程和失败恢复；区分已验证事实与假设。",
     "用户、场景、旅程、痛点、假设"),
    ("flow-architect", "产品流程架构师", "03-product-flows.md",
     "把产品方案转成状态机：状态、事件、转移、前置条件、失败/恢复、空/加载/错误状态；指出流程缺口。",
     "状态、事件、转移、失败、恢复"),
    ("feature-designer", "功能与验收设计师", "04-feature-spec.md",
     "把文档拆成可交付切片：功能、优先级、依赖、非目标、验收标准、边界与异常；给出可测试的完成定义。",
     "功能、切片、依赖、非目标、验收"),
    ("ux-reviewer", "UX/可访问性评审", "05-ux-review.md",
     "检查信息架构、交互反馈、空/加载/错误/禁用状态、键盘/手柄、对比度、文案与可访问性；给出可落地修改。",
     "信息架构、状态、可访问、错误、文案"),
    ("tech-feasibility", "技术可行性评审", "06-tech-feasibility.md",
     "评估实现可行性、技术栈一致性、数据/接口依赖、性能/安全/成本风险；指出必须前置验证的技术假设。",
     "技术栈、依赖、性能、安全、风险"),
    ("release-strategist", "版本与发布策略师", "07-upgrade-plan.md",
     "面向发版和升级：版本方案、兼容性矩阵、数据迁移、特性开关、灰度、回滚、回滚演练与发布门禁。",
     "版本、兼容、迁移、特性开关、灰度、回滚"),
    ("qa-rehearsal", "质量预演师", "08-rehearsal.md",
     "设计至少 3 个升级预演场景（补丁/小版本/大版本），给出基线指标、受影响的流程/数据/接口、通过标准、回滚时间与 Go/No-Go 条件。",
     "场景、基线、指标、回滚、Go/No-Go"),
    ("red-team", "产品红队评审", "09-red-team.md",
     "对抗性找矛盾、遗漏、不可验收承诺、范围膨胀、用户误导和升级破坏；每条带严重度和 SRC 引用。",
     "矛盾、缺口、风险、严重度、SRC"),
    ("knowledge-curator", "知识沉淀与复用", "10-playbook.md",
     "把本次分析转成下一次版本升级的可复用清单：触发条件、输入、评审步骤、门禁、模板、常见坑和负责人。",
     "复用、升级清单、触发条件、门禁、模板"),
]


def prompt(role: str, title: str, artifact: str, instruction: str, quality: str) -> str:
    body = f"""---
role: {role}
version: 1
generated_from: prompts/build_product_prompts.py
---
# ROLE: {role}

你是 AgentTeam 的「{title}」，服务于**产品文档深度解析、应用流程细化、版本升级预演**，不是通用开发 Agent。

## 目标
{instruction}

## 输入
- 完整产品文档（含 `SRC-###` 章节 ID）
- 前序角色的摘要与已落盘文档
- 可选知识库引用

## 必须交付
把完整分析写入 `docs/product-review/{artifact}`；不要只返回摘要。
输出 JSON 必须符合 `specs/product-review-output.schema.json`，包含：
- `source_sections`：引用的 SRC ID
- `findings`：问题/决策/风险，含 severity、claim、source_refs、recommendation
- `coverage`：总章节/覆盖章节
- `files`：`{{"path":"docs/product-review/{artifact}","content":"..."}}`
- `summary`、`open_questions`

## 质量门槛
{quality}

## 证据纪律
- 每个事实尽量引用 `SRC-###`；无法引用时标为假设，不写成已验证事实。
- 不编造接口、数据、用户研究或发布结果。
- 发现冲突/缺口必须显式列出，不得用模糊措辞掩盖。
- 面向升级方案时，必须说明对现有版本、数据、契约、用户的影响和回滚路径。
"""
    return body


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    registry = ["roles:"]
    for role, title, artifact, instruction, quality in ROLES:
        text = prompt(role, title, artifact, instruction, quality)
        path = OUT / f"{role}.md"
        path.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        registry.append(f"  - role: {role}")
        registry.append(f"    title: {title}")
        registry.append(f"    artifact: docs/product-review/{artifact}")
        registry.append(f"    hash: {digest}")
    (OUT / "registry.yaml").write_text("\n".join(registry) + "\n", encoding="utf-8")
    print(f"generated {len(ROLES)} product-review prompts -> {OUT}")


if __name__ == "__main__":
    main()
