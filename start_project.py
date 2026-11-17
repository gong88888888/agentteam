#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Start a role-based project run from a requirement file.

  python start_project.py --requirements requirements/examples/csv-export/selected.md \
      --project-dir projects/example-csv-export --offline

  python start_project.py --requirements ... --project-dir ... --real \
      --roles pm,product,arch,backend,frontend --kb
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.config import load_config  # noqa: E402
from orchestrator.project_runner import ProjectRunner  # noqa: E402
from orchestrator.game_check import detect_project_type  # noqa: E402


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Start a role-based AgentTeam project")
    p.add_argument("--requirements", required=True,
                   help="需求 Markdown/YAML（建议用 requirements select 生成的 selected.md）")
    p.add_argument("--project-dir", required=True,
                   help="开发文件夹；角色记录、代码与日志写入这里")
    p.add_argument("--offline", action="store_true", default=True,
                   help="使用确定性 stub（默认）")
    p.add_argument("--real", action="store_true",
                   help="调用本地 Qwen 3.6；DeepSeek 作为 fallback")
    p.add_argument("--roles", default=None,
                   help="逗号分隔角色；默认 12 个角色全跑")
    p.add_argument("--kb", action="store_true",
                   help="检索 data/knowledge.db 并注入角色上下文")
    p.add_argument("--stop-on-error", action="store_true")
    p.add_argument("--force", action="store_true",
                   help="允许写入已存在的非空项目目录")
    p.add_argument("--template", default=None,
                   help="项目模板 ID（新目录默认 web-2d-game/minimal-api，已有目录用 none）")
    p.add_argument("--project-type", default="auto", choices=("auto", "game", "web"),
                   help="项目类型；auto 根据需求关键词判断")
    p.add_argument("--tool-profile", default="basic", choices=("basic", "standard", "full"),
                   help="工具证据 profile；standard/full 需要 semgrep/trivy")
    p.add_argument("--no-gates", action="store_true", help="关闭角色门禁（不推荐）")
    p.add_argument("--sandbox", action="store_true",
                   help="代码角色在隔离工作区写入，门禁通过后才提升")
    p.add_argument("--stop-on-gate", action="store_true",
                   help="任一门禁未通过即停止后续角色")
    p.add_argument("--no-quality", action="store_true", help="不计算角色质量分")
    p.add_argument("--merge", action="store_true",
                   help="保留未运行角色的既有记录（用于单角色重跑）")
    p.add_argument("--note", default="", help="给角色的调整要求（用于单角色重跑）")
    p.add_argument("--decision-db", default=None,
                   help="门禁升级写入的决策库（默认 data/decisions.db）")
    p.add_argument("--config", default=None)
    args = p.parse_args()

    project_dir = Path(args.project_dir).resolve()
    exists_nonempty = project_dir.exists() and any(project_dir.iterdir())
    if exists_nonempty and not args.force:
        print(json.dumps({"error": f"项目目录非空：{project_dir}；加 --force 覆盖写入"},
                         ensure_ascii=False, indent=2))
        return 2
    requirement_text = Path(args.requirements).read_text(encoding="utf-8", errors="replace")
    project_type = (detect_project_type(requirement_text)
                    if args.project_type == "auto" else args.project_type)
    template = args.template
    if template is None:
        template = "none" if exists_nonempty else (
            "web-2d-game" if project_type == "game" else "minimal-api")
    roles = [r.strip() for r in args.roles.split(",")] if args.roles else None
    cfg = load_config(args.config)
    runner = ProjectRunner(
        requirements=args.requirements, project_dir=project_dir, cfg=cfg,
        offline=not args.real, roles=roles, use_kb=args.kb,
        stop_on_error=args.stop_on_error, template=template,
        tool_profile=args.tool_profile, gates=not args.no_gates,
        sandbox=args.sandbox, decision_db=args.decision_db,
        stop_on_gate=args.stop_on_gate, quality=not args.no_quality,
        merge_state=args.merge, project_type=project_type,
        extra_note=args.note)
    result = runner.run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
