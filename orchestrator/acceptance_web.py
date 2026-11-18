"""Web/API runtime acceptance: start the real service, prove health and a flow.

Existence of ``src/backend/app.py`` is not acceptance. The service is started in
an isolated working directory on a free port, a health signal must be observed,
and at least one declared business flow must succeed against the real HTTP
server. Every result is written to the signed evidence ledger.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import signing_key
from .evidence.store import EvidenceStore
from .sandbox import tree_hash

PLAN_FILE = "acceptance.web-plan.json"
REPORT_FILE = "acceptance.web.json"
DEFAULT_HEALTH = "/health"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _scrubbed_env(port: int) -> dict[str, str]:
    keep = ("PATH", "HOME", "USERPROFILE", "TMP", "TEMP", "SYSTEMROOT", "WINDIR",
            "COMSPEC", "PATHEXT", "PYTHONIOENCODING", "PYTHONUTF8")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env["PORT"] = str(port)
    env["AGENTTEAM_PORT"] = str(port)
    return env


def resolve_plan(project_dir: str | Path) -> dict[str, Any]:
    root = Path(project_dir)
    path = root / PLAN_FILE
    if path.is_file():
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(plan, dict):
                return plan
        except (OSError, json.JSONDecodeError):
            pass
    entry = "src/backend/app.py" if (root / "src" / "backend" / "app.py").is_file() else ""
    return {
        "schema_version": "1.0",
        "profile": "web-api",
        "entry": entry,
        "start_argv": ["{python}", entry, "--port", "{port}"] if entry else [],
        "health": {"path": DEFAULT_HEALTH, "expect_status": 200,
                   "expect_json": {"status": "ok"}},
        "flow": [],
        "startup_timeout_s": 15,
        "source": "detected" if entry else "missing",
    }


def _request(url: str, *, timeout: float = 5.0,
             method: str = "GET", body: bytes | None = None,
             headers: dict[str, str] | None = None) -> tuple[int, str, str]:
    req = urllib.request.Request(url, data=body, method=method.upper(),
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace"), ""
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace"), str(exc)
    except Exception as exc:  # connection refused / timeout
        return 0, "", str(exc)


def _wait_health(base: str, health: dict[str, Any], timeout_s: float,
                 proc: subprocess.Popen | None) -> tuple[bool, str, dict[str, Any]]:
    path = str(health.get("path", DEFAULT_HEALTH))
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            return False, f"服务提前退出，exit={proc.returncode}", {}
        code, text, err = _request(base + path, timeout=2.0)
        last = err or f"HTTP {code}: {text[:200]}"
        if code == int(health.get("expect_status", 200)):
            expected = health.get("expect_json") or {}
            if expected:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    last = f"健康响应不是 JSON：{text[:200]}"
                else:
                    if all(data.get(k) == v for k, v in expected.items()):
                        return True, "", data
                    last = f"健康 JSON 不匹配：{data}"
            else:
                return True, "", {}
        time.sleep(0.25)
    return False, f"健康检查超时（{timeout_s}s）：{last}", {}


def run_web_acceptance(project_dir: str | Path, *,
                       ledger_path: str | Path | None = None,
                       baseline_fp: str = "") -> dict[str, Any]:
    root = Path(project_dir).resolve()
    plan = resolve_plan(root)
    ledger = (Path(ledger_path) if ledger_path
              else root / "evidence" / "tool-ledger.jsonl")
    store = EvidenceStore(ledger, signing_key())
    subject = tree_hash(root)
    checks: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    logs: dict[str, str] = {}

    def add(name: str, ok: bool, detail: str, payload: dict[str, Any] | None = None) -> None:
        kind = "web_flow" if name.startswith("web_flow") else name
        rec = store.add(kind=kind, subject_hash=subject, tool="web-acceptance",
                        tool_version="1", result="pass" if ok else "fail",
                        payload={"check": name, "detail": detail, **(payload or {})},
                        signed_by="tool:web-acceptance",
                        baseline_fp=baseline_fp or "project", ttl_s=3600)
        evidence.append(rec)
        checks.append({"name": name, "ok": bool(ok), "detail": detail,
                       "evidence_id": rec["evidence_id"]})

    entry = str(plan.get("entry", "") or "")
    start_argv = plan.get("start_argv") or []
    if not entry or not (root / entry).is_file():
        add("web_start", False, f"入口不存在：{entry or '未声明'}")
        return _finish(root, checks, evidence, subject, plan, logs, "fail")
    port = _free_port()
    argv = [str(a).format(python=sys.executable, port=port, project=str(root))
            for a in start_argv] or [sys.executable, entry, "--port", str(port)]
    proc: subprocess.Popen | None = None
    try:
        proc = subprocess.Popen(argv, cwd=str(root), env=_scrubbed_env(port),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
        base = f"http://127.0.0.1:{port}"
        timeout_s = float(plan.get("startup_timeout_s", 15))
        health = plan.get("health") or {"path": DEFAULT_HEALTH}
        health_ok, health_detail, health_data = _wait_health(base, health, timeout_s, proc)
        if proc.poll() is not None:
            out, err = proc.communicate(timeout=2)
            logs["stdout"] = (out or "")[-3000:]
            logs["stderr"] = (err or "")[-3000:]
        add("web_start", proc.poll() is None or health_ok,
            f"argv={argv} exit={proc.poll()}", {"argv": argv, "port": port})
        add("web_health", health_ok, health_detail or json.dumps(health_data,
                                                                ensure_ascii=False),
            {"health_path": health.get("path"), "response": health_data})
        flows = plan.get("flow") or []
        if not flows:
            add("web_flow", False,
                "验收计划没有声明业务流程；模板/契约存在不等于业务可用")
        for spec in flows:
            name = str(spec.get("name") or spec.get("path") or "flow")
            path = str(spec.get("path", "/"))
            method = str(spec.get("method", "GET"))
            url = base + path
            body = None
            headers = dict(spec.get("headers") or {})
            if spec.get("json_body") is not None:
                body = json.dumps(spec["json_body"], ensure_ascii=False).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            code, text, err = _request(url, method=method, body=body,
                                       headers=headers,
                                       timeout=float(spec.get("timeout_s", 10)))
            expect_status = int(spec.get("expect_status", 200))
            ok = code == expect_status
            detail = err or f"HTTP {code} {url}"
            contains = spec.get("expect_contains")
            if ok and contains and str(contains) not in text:
                ok = False
                detail = f"响应缺少 {contains!r}：{text[:300]}"
            add(f"web_flow:{name}", ok, detail,
                {"method": method, "path": path, "status": code,
                 "response_tail": text[-1000:]})
    except Exception as exc:
        add("web_start", False, f"启动失败：{exc}")
        add("web_health", False, "服务未启动")
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate(timeout=5)
            logs["stdout"] = (out or "")[-3000:]
            logs["stderr"] = (err or "")[-3000:]
    hard = [c for c in checks if c["name"] in ("web_start", "web_health")
            and not c["ok"]]
    if hard:
        status = "fail"
    elif any(c["name"] == "web_flow" and not c["ok"] for c in checks):
        status = "need_evidence"
    elif all(c["ok"] for c in checks):
        status = "pass"
    else:
        status = "fail"
    return _finish(root, checks, evidence, subject, plan, logs, status)

def _finish(root: Path, checks: list[dict[str, Any]],
            evidence: list[dict[str, Any]], subject: str,
            plan: dict[str, Any], logs: dict[str, str],
            status: str) -> dict[str, Any]:
    result = {
        "status": status,
        "profile": plan.get("profile", "web-api"),
        "plan_source": plan.get("source", "declared"),
        "entry": plan.get("entry", ""),
        "checks": checks,
        "evidence_ids": [e["evidence_id"] for e in evidence],
        "subject_hash": subject,
        "logs": logs,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (root / REPORT_FILE).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
