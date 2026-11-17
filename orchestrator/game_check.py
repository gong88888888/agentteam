"""Game project detection, playable-slice acceptance and signed evidence.

The acceptance gate is deliberately project-level: role-scoped compile checks
cannot prove that a game boots. A game project is only accepted when the
shipped entry point and its pure logic tests pass.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import signing_key
from .evidence.store import EvidenceStore
from .sandbox import Sandbox, tree_hash

GAME_KEYWORDS = (
    "游戏", "玩家", "关卡", "boss", "迷宫", "职业", "多人", "同屏", "存档",
    "装备", "掉落", "刷装", "横版", "平台跳跃", "像素",
)
WEB_KEYWORDS = ("api", "后台", "财务报表", "csv 导出", "cms", "表单")


def detect_project_type(requirement: str) -> str:
    text = (requirement or "").lower()
    score = sum(1 for word in GAME_KEYWORDS if word.lower() in text)
    web = sum(1 for word in WEB_KEYWORDS if word.lower() in text)
    return "game" if score >= 3 and score > web else "web"


def game_profile(project_dir: str | Path) -> dict[str, Any]:
    root = Path(project_dir)
    game = root / "game"
    return {
        "kind": "game" if game.is_dir() else "unknown",
        "engine": "html5-canvas" if (game / "index.html").exists() else "none",
        "entry": str(game / "index.html"),
        "has_entry": (game / "index.html").is_file(),
        "has_core": (game / "js" / "core.js").is_file(),
        "has_main": (game / "js" / "main.js").is_file(),
        "has_tests": (game / "tests" / "game_logic.test.mjs").is_file(),
    }


def _node(sandbox: Sandbox, args: list[str]) -> dict[str, Any]:
    result = sandbox.run(["node", *args])
    return {
        "ok": result.ok,
        "argv": result.argv,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }


def _chrome_render(game_dir: Path) -> dict[str, Any]:
    chrome = shutil.which("chrome") or shutil.which("google-chrome")
    if not chrome:
        candidate = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        chrome = str(candidate) if candidate.exists() else ""
    if not chrome:
        return {"ok": False, "detail": "Chrome 不可用，跳过渲染证据"}
    with tempfile.TemporaryDirectory() as td:
        shot = Path(td) / "game.png"
        result = sandbox_run_chrome(chrome, game_dir, shot)
        return {"ok": result and shot.exists() and shot.stat().st_size > 20_000,
                "detail": f"screenshot {shot.stat().st_size if shot.exists() else 0} bytes"}


def sandbox_run_chrome(chrome: str, game_dir: Path, shot: Path) -> bool:
    import subprocess
    try:
        subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--virtual-time-budget=4000", "--window-size=1280,720",
            "--allow-file-access-from-files",
            f"--screenshot={shot}", (game_dir / "index.html").as_uri(),
        ], capture_output=True, timeout=60, check=False)
        return shot.exists()
    except Exception:
        return False


def run_game_acceptance(project_dir: str | Path, *,
                        ledger_path: str | Path | None = None,
                        baseline_fp: str = "") -> dict[str, Any]:
    root = Path(project_dir).resolve()
    game_dir = root / "game"
    ledger = Path(ledger_path) if ledger_path else root / "evidence" / "tool-ledger.jsonl"
    store = EvidenceStore(ledger, signing_key())
    checks: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    subject = tree_hash(root)

    def add(name: str, ok: bool, detail: str, payload: dict | None = None) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail,
                       "evidence_id": ""})
        kind = f"game_{name}"
        rec = store.add(kind=kind, subject_hash=subject, tool="node" if "test" in name or name == "smoke" else "game-check",
                        tool_version="html5", result="pass" if ok else "fail",
                        payload={"detail": detail, **(payload or {})},
                        signed_by=f"tool:{'node' if 'test' in name or name == 'smoke' else 'game-check'}",
                        baseline_fp=baseline_fp or "project", ttl_s=7200)
        evidence.append(rec)
        checks[-1]["evidence_id"] = rec["evidence_id"]

    if not game_dir.is_dir():
        add("entry", False, "缺少 game/ 目录；这不是可运行的游戏工程")
        status = "fail"
    else:
        index = game_dir / "index.html"
        main = game_dir / "js" / "main.js"
        core = game_dir / "js" / "core.js"
        tests = game_dir / "tests" / "game_logic.test.mjs"
        html = index.read_text(encoding="utf-8", errors="replace") if index.exists() else ""
        entry_ok = index.is_file() and 'id="game"' in html and "js/main.js" in html
        add("entry", entry_ok,
            "canvas#game + module entry present" if entry_ok
            else "index.html 必须包含 canvas#game 并加载 js/main.js")
        modules_ok = main.is_file() and core.is_file()
        add("modules", modules_ok, "js/main.js + js/core.js present" if modules_ok
            else "缺少 js/main.js 或 js/core.js")
        sandbox = Sandbox(game_dir, timeout_s=60)
        logic = _node(sandbox, ["--test", "tests/game_logic.test.mjs"]) if tests.exists() else {
            "ok": False, "detail": "缺少 tests/game_logic.test.mjs"}
        add("logic", bool(logic.get("ok")), logic.get("stderr_tail") or logic.get("detail", "logic tests passed"),
            logic)
        smoke = _node(sandbox, ["tests/smoke.mjs"]) if tests.exists() else {
            "ok": False, "detail": "缺少 smoke.mjs"}
        add("smoke", bool(smoke.get("ok")), smoke.get("stderr_tail") or smoke.get("stdout_tail", ""),
            smoke)
        qa_files = sorted((game_dir / "tests").glob("qa_*.mjs"))
        if qa_files:
            qa = _node(sandbox, ["--test", *[f"tests/{p.name}" for p in qa_files]])
            add("qa", bool(qa.get("ok")),
                qa.get("stderr_tail") or qa.get("stdout_tail") or "QA tests passed", qa)
        render = _chrome_render(game_dir)
        add("render", bool(render.get("ok")), str(render.get("detail", "")))
        status = "pass" if all(c["ok"] for c in checks) else "fail"

    result = {
        "status": status,
        "engine": "html5-canvas" if (game_dir / "index.html").exists() else "none",
        "checks": checks,
        "evidence_ids": [e["evidence_id"] for e in evidence],
        "subject_hash": subject,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (root / "acceptance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
