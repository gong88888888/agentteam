"""Project lifecycle policy: preflight, stage gates and Definition of Done.

The job of this module is to make "the project is complete" a property of the
project artifact, not of a role's summary. It is intentionally independent of
the game implementation so web/API projects use the same lifecycle.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

PROJECT_DOD: dict[str, dict[str, Any]] = {
    "game": {
        "entry": "game/index.html",
        "required_docs": [
            "docs/product/product-baseline.md",
            "docs/architecture/architecture.md",
        ],
        "required_tools": ["node"],
        "acceptance": True,
        "description": "可运行游戏入口 + 产品/架构文档 + 项目验收",
    },
    "web": {
        "entry": "src/backend/app.py",
        "required_docs": [
            "docs/product/product-baseline.md",
            "docs/architecture/architecture.md",
        ],
        "required_tools": ["python"],
        "acceptance": False,
        "description": "可运行服务入口 + 产品/架构文档 + 角色门禁",
    },
}


def stage_plan(project_type: str) -> list[dict[str, Any]]:
    common = [
        {"id": "intake", "title": "需求与项目画像", "roles": ["pm"]},
        {"id": "product", "title": "产品流程与验收", "roles": ["product"]},
        {"id": "design", "title": "UI 与架构契约", "roles": ["ui", "arch"]},
        {"id": "implementation", "title": "可运行垂直切片", "roles": ["backend", "frontend"]},
        {"id": "quality", "title": "评审、测试与安全", "roles": ["review", "qa", "security"]},
        {"id": "release", "title": "发布、知识沉淀与复盘", "roles": ["ops", "kb", "retro"]},
    ]
    if project_type == "game":
        common[3]["gate"] = "game_acceptance"
    else:
        common[3]["gate"] = "tool_evidence"
    return common


def preflight(project_dir: str | Path, project_type: str,
              template: str = "none") -> dict[str, Any]:
    root = Path(project_dir).resolve()
    dod = PROJECT_DOD.get(project_type, PROJECT_DOD["web"])
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    entry = root / dod["entry"]
    add("entry", entry.is_file(), f"{dod['entry']} {'存在' if entry.is_file() else '缺失'}")
    add("template", template not in ("", "none"),
        f"template={template}")
    for tool in dod["required_tools"]:
        path = shutil.which(tool)
        add(f"tool:{tool}", bool(path), path or f"缺少 {tool}")
    for doc in dod["required_docs"]:
        # Documents are produced by roles; preflight records that they are required.
        add(f"doc-required:{doc}", True, "由 product/arch 角色产出")
    if project_type == "game":
        add("playable-entry", (root / "game" / "js" / "core.js").is_file()
            and (root / "game" / "js" / "main.js").is_file(),
            "game/js/core.js + main.js")
    blockers = [c for c in checks if not c["ok"]]
    return {"status": "pass" if not blockers else "fail",
            "checks": checks, "blockers": blockers, "at": time.time()}


def definition_of_done(project_dir: str | Path, project_type: str,
                       state: dict[str, Any], *,
                       acceptance: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(project_dir)
    dod = PROJECT_DOD.get(project_type, PROJECT_DOD["web"])
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    role_rows = [v for v in state.values() if isinstance(v, dict)]
    add("roles_present", len(role_rows) > 0, f"{len(role_rows)} roles")
    bad = [r for r in role_rows if r.get("status") in ("error", "blocked")]
    add("roles_clear", not bad, f"{len(bad)} blocked/error")
    gates = [r.get("gate") or {} for r in role_rows]
    add("gate_pass", all(g.get("status") == "pass" for g in gates),
        f"{sum(1 for g in gates if g.get('status') == 'pass')}/{len(gates)} gate pass")
    entry = root / dod["entry"]
    add("entry", entry.is_file(), dod["entry"])
    missing_docs = [d for d in dod["required_docs"] if not (root / d).is_file()]
    add("docs", not missing_docs, "缺少 " + ", ".join(missing_docs) if missing_docs else "产品/架构文档齐全")
    if dod["acceptance"]:
        add("acceptance", bool(acceptance and acceptance.get("status") == "pass"),
            (acceptance or {}).get("status", "not run"))
    passed = all(c["ok"] for c in checks)
    return {"status": "pass" if passed else "fail",
            "checks": checks, "definition": dod["description"],
            "at": time.time()}


def stage_summary(project_dir: str | Path) -> dict[str, Any]:
    path = Path(project_dir) / "state" / "stages.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"stages": [], "status": "unknown"}


def write_stages(project_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(project_dir) / "state" / "stages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"stages": rows, "updated_at": time.time()},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
