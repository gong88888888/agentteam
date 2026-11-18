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
        "acceptance": True,
        "description": "可运行服务入口 + 产品/架构文档 + 运行验收",
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


def _doc_ok(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return False
    lowered = text.lower()
    return len(text) >= 25 and "todo" not in lowered and "scaffold" not in lowered


def definition_of_done(project_dir: str | Path, project_type: str,
                       state: dict[str, Any], *,
                       acceptance: dict[str, Any] | None = None,
                       manifest: Any = None,
                       explicit_legacy: bool = False) -> dict[str, Any]:
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

    if manifest is None:
        add("manifest", False,
            "没有已批准的迭代清单；历史项目必须显式重验（legacy_incomplete）")
        return {"status": "fail", "checks": checks, "legacy_incomplete": True,
                "definition": dod["description"],
                "explicit_legacy": explicit_legacy, "at": time.time()}

    spec = manifest.to_dict() if hasattr(manifest, "to_dict") else dict(manifest)
    checks = []
    add("manifest", True, f"iteration={spec.get('iteration_id')}")
    add("manifest_mode", spec.get("mode", "formal") == "formal",
        f"mode={spec.get('mode', 'formal')}；rehearsal 不能作为正式完成")
    required = [t for t in spec.get("required_tasks", []) if t.get("required", True)]
    missing_roles, blocked_roles, stale_roles = [], [], []
    for task in required:
        role = str(task.get("role", ""))
        meta = state.get(role)
        if not isinstance(meta, dict):
            missing_roles.append(role)
            continue
        if meta.get("status") != "done":
            blocked_roles.append(f"{role}:{meta.get('status')}")
        gate = meta.get("gate") or {}
        if gate.get("status") != "pass":
            blocked_roles.append(f"{role}:gate={gate.get('status')}")
            continue
        role_run = gate.get("run_id") or meta.get("run_id") or ""
        if role_run != spec.get("iteration_id"):
            stale_roles.append(f"{role}:{role_run or 'unknown'}")
    add("required_roles", not missing_roles,
        "缺少承诺任务：" + ", ".join(missing_roles) if missing_roles
        else f"{len(required)} 项承诺任务均有记录")
    add("required_roles_clear", not blocked_roles,
        "; ".join(blocked_roles) if blocked_roles else "所有承诺任务通过")
    add("gate_current", not stale_roles,
        "; ".join(stale_roles) if stale_roles
        else "门禁属于当前迭代，不是历史绿灯")
    docs = [d for d in spec.get("required_docs", []) if not _doc_ok(root / d)]
    add("docs", not docs, "缺少或为空：" + ", ".join(docs) if docs
        else f"{len(spec.get('required_docs', []))} 份承诺文档有效")
    if spec.get("requires_entry"):
        entry_rel = str(spec.get("entry") or dod["entry"])
        add("entry", (root / entry_rel).is_file(), entry_rel)
    else:
        add("entry", True, "本轮不承诺运行入口（文档型交付）")
    required_acc = list(spec.get("required_acceptance") or [])
    acc_list = [c for c in (acceptance or {}).get("checks", [])
                if isinstance(c, dict)]
    acc_checks = {c.get("name"): c for c in acc_list}

    def acc_ok(name: str) -> bool:
        if name in acc_checks:
            return bool(acc_checks[name].get("ok"))
        return any(str(c.get("name", "")).startswith(name + ":") and c.get("ok")
                   for c in acc_list)

    missing_acc = [name for name in required_acc if not acc_ok(name)]
    add("acceptance", not missing_acc,
        ("缺少/失败验收：" + ", ".join(missing_acc)) if missing_acc
        else (f"{len(required_acc)} 项运行验收通过"
              if required_acc else "无运行验收集合"))
    passed = all(c["ok"] for c in checks)
    return {"status": "pass" if passed else "fail",
            "checks": checks, "definition": dod["description"],
            "iteration_id": spec.get("iteration_id"),
            "required_roles": [t.get("role") for t in required],
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
