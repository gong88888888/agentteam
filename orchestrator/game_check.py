"""Game project detection, playable-slice acceptance and signed evidence.

The acceptance gate is deliberately project-level: role-scoped compile checks
cannot prove that a game boots. A game project is only accepted when the
shipped entry point and its pure logic tests pass.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import signing_key
from .evidence.store import EvidenceStore
from .sandbox import Sandbox, tree_hash

TEMPLATE_GAME = (Path(__file__).resolve().parents[1]
                 / "templates" / "web-2d-game" / "game")
MODULE_DIRS = ("game/js/gameplay", "game/js/ui")
IMPORT_RE = re.compile(
    r"""(?:from\s+|import\s*\(\s*)["']([^"']+)["']""")
SCRIPT_RE = re.compile(r"""<script[^>]+src=["']([^"']+)["']""")

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
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def increment_modules(project_dir: str | Path) -> list[str]:
    """Generated/modified gameplay or UI modules relative to the template.

    Baseline modules shipped with the template are not considered increments.
    """
    root = Path(project_dir)
    result: list[str] = []
    for rel_dir in MODULE_DIRS:
        base = root / rel_dir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.js")):
            rel = path.relative_to(root).as_posix()
            template = TEMPLATE_GAME / Path(rel).relative_to("game")
            if template.is_file() and template.stat().st_size == path.stat().st_size \
                    and _sha(template) == _sha(path):
                continue
            result.append(rel)
    return result


def entry_reachable(project_dir: str | Path) -> set[str]:
    """Modules statically reachable from index.html/main.js/core.js."""
    root = Path(project_dir).resolve()
    game = root / "game"
    reachable: set[str] = set()
    queue: list[Path] = []
    index = game / "index.html"
    if index.is_file():
        for src in SCRIPT_RE.findall(index.read_text(encoding="utf-8", errors="replace")):
            if src.startswith("."):
                queue.append((game / src).resolve())
    for core in (game / "js" / "main.js", game / "js" / "core.js",
                 game / "js" / "extensions" / "registry.js"):
        if core.is_file():
            queue.append(core)
    seen: set[Path] = set()
    while queue:
        path = queue.pop()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if rel.endswith(".js"):
            reachable.add(rel)
        text = path.read_text(encoding="utf-8", errors="replace")
        for spec in IMPORT_RE.findall(text):
            if not spec.startswith("."):
                continue
            target = (path.parent / spec).resolve()
            if target.suffix == "":
                target = target.with_suffix(".js")
            if target.is_file():
                queue.append(target)
    return reachable


def load_extension_manifest(project_dir: str | Path) -> tuple[list[dict[str, Any]],
                                                              list[str]]:
    root = Path(project_dir)
    path = root / "game" / "js" / "extensions" / "manifest.json"
    if not path.is_file():
        return [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"manifest 无法解析：{exc}"]
    entries = data if isinstance(data, list) else (data.get("extensions") or [])
    errors: list[str] = []
    clean: list[dict[str, Any]] = []
    ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("manifest 条目不是对象")
            continue
        eid = str(entry.get("id", "")).strip()
        module = str(entry.get("module", "")).replace("\\", "/").strip()
        if module.startswith("game/"):
            module = module[len("game/"):]
        if not eid or not module:
            errors.append(f"manifest 条目缺少 id/module：{entry}")
            continue
        if eid in ids:
            errors.append(f"重复 extension id：{eid}")
        ids.add(eid)
        if ".." in Path(module).parts or not module.startswith("js/"):
            errors.append(f"非法模块路径：{module}")
            continue
        if not (root / "game" / module).is_file():
            errors.append(f"模块不存在：game/{module}")
            continue
        clean.append({**entry, "id": eid, "module": module,
                      "path": f"game/{module}"})
    return clean, errors


def integration_report(project_dir: str | Path, sandbox: Sandbox) -> dict[str, Any]:
    root = Path(project_dir)
    increments = increment_modules(root)
    entries, manifest_errors = load_extension_manifest(root)
    registered = {f"game/{e['module']}" for e in entries}
    reachable = entry_reachable(root)
    unreachable = [m for m in increments if m not in registered and m not in reachable]
    harness = None
    harness_error = ""
    harness_path = root / "game" / "tests" / "integration.mjs"
    harness_result_path = root / "game" / "tests" / ".integration-result.json"
    if harness_result_path.exists():
        try:
            harness_result_path.unlink()
        except OSError:
            pass
    if (entries or increments) and not harness_path.is_file():
        harness_error = "缺少 game/tests/integration.mjs"
    elif entries or increments:
        result = _node(sandbox, ["tests/integration.mjs"])
        if harness_result_path.is_file():
            try:
                harness = json.loads(harness_result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                harness_error = "integration 结果文件不是合法 JSON"
        if harness is None:
            text = (result.get("stdout_tail") or "") + (result.get("stderr_tail") or "")
            line = next((ln for ln in text.splitlines()
                         if ln.startswith("INTEGRATION_RESULT ")), "")
            if line:
                try:
                    harness = json.loads(line[len("INTEGRATION_RESULT "):])
                except json.JSONDecodeError:
                    harness_error = "INTEGRATION_RESULT 不是合法 JSON"
            else:
                harness_error = (result.get("stderr_tail") or "集成测试没有输出结果")[:500]
        if harness and (not result.get("ok") or harness.get("failures")):
            harness_error = "; ".join(str(f.get("message")) for f in
                                      harness.get("failures", []))[:500]
    problems = list(manifest_errors)
    if unreachable:
        problems.append("增量模块未注册或入口不可达：" + ", ".join(unreachable))
    if harness_error:
        problems.append(harness_error)
    if harness and harness.get("loaded", 0) < len(entries):
        problems.append(f"清单 {len(entries)} 项，仅加载 {harness.get('loaded', 0)} 项")
    return {
        "ok": not problems,
        "detail": ("；".join(problems) if problems
                   else ("无增量模块" if not entries and not increments
                         else f"{len(entries)} 个扩展已加载/调用/断言")),
        "increments": increments,
        "registered": sorted(registered),
        "reachable": sorted(reachable),
        "unreachable": unreachable,
        "manifest_errors": manifest_errors,
        "harness": harness,
    }


def run_game_acceptance(project_dir: str | Path, *,
                        ledger_path: str | Path | None = None,
                        baseline_fp: str = "",
                        report_name: str = "acceptance.json") -> dict[str, Any]:
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
        is_node = "test" in name or name in ("smoke", "integration")
        kind = f"game_{name}"
        rec = store.add(kind=kind, subject_hash=subject,
                        tool="node" if is_node else "game-check",
                        tool_version="html5", result="pass" if ok else "fail",
                        payload={"detail": detail, **(payload or {})},
                        signed_by=f"tool:{'node' if is_node else 'game-check'}",
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
        integration = integration_report(root, sandbox)
        add("integration", bool(integration.get("ok")), str(integration.get("detail", "")),
            integration)
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
