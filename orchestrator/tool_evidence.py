"""Tool evidence: real commands, signed records, explicit missing-tool states.

Profiles:
  basic    compile + unit tests (stdlib-friendly)
  standard basic + SAST (semgrep) + OpenAPI contract check
  full     standard + secret scan / dependency scan (trivy)

A missing tool or a missing prerequisite is returned as an explicit ``missing``
entry; it never becomes a synthetic pass. ``fail-closed`` gates consume that.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from .config import ROOT, signing_key
from .evidence.store import EvidenceStore
from .sandbox import Sandbox, SandboxError, tree_hash

PROFILES = ("basic", "standard", "full")
KIND_ORDER = ("compile", "unit", "sast", "contract_test", "api_test", "secret_scan")


@dataclass(frozen=True)
class CheckSpec:
    kind: str
    argv: tuple[str, ...] | None
    reason: str = ""
    required: bool = True


def _python_version() -> str:
    return platform.python_version()


def _module_version(name: str) -> str:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return ""


def _tool_version(sandbox: Sandbox, exe: str) -> str:
    argv = [exe, "--version"]
    try:
        r = sandbox.run(argv)
        text = (r.stdout or r.stderr).strip().splitlines()
        return text[0][:120] if text else ""
    except Exception:
        return ""


def _test_files(root: Path) -> list[Path]:
    tests = root / "tests"
    if not tests.is_dir():
        return []
    return sorted(p for p in tests.rglob("test_*.py") if p.is_file())


def _contract_file(root: Path) -> Path | None:
    for rel in ("contracts/openapi.yaml", "contracts/openapi.yml",
                "contracts/api.yaml", "contracts/api.yml"):
        p = root / rel
        if p.is_file():
            return p
    cands = sorted((root / "contracts").glob("*")) if (root / "contracts").is_dir() else []
    return cands[0] if cands else None


def _semgrep_config(root: Path) -> Path | None:
    for p in (root / "tools" / "semgrep.yml", ROOT / "tools" / "semgrep.yml"):
        if p.is_file():
            return p
    return None


def build_checks(root: Path, profile: str, sandbox: Sandbox,
                 scope: str = "src",
                 files: list[str] | None = None) -> list[CheckSpec]:
    if profile not in PROFILES:
        raise ValueError(f"未知 profile：{profile}")
    checks: list[CheckSpec] = []
    py = sys.executable
    scope_path = root / scope
    py_files = list(files or [])
    if not py_files:
        py_files = [p.relative_to(root).as_posix() for p in scope_path.rglob("*.py")
                    if p.is_file()] if scope_path.is_dir() else []
    py_files = [p for p in py_files if p.endswith(".py")]
    has_src = bool(py_files)
    checks.append(CheckSpec(
        "compile", (py, "-m", "compileall", "-q", *py_files) if has_src else None,
        "" if has_src else f"{scope}/ 下没有 Python 文件"))
    tests = _test_files(root)
    if tests:
        if importlib.util.find_spec("pytest"):
            argv = (py, "-m", "pytest", "-q", "tests")
        else:
            argv = (py, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")
        checks.append(CheckSpec("unit", argv))
    else:
        checks.append(CheckSpec("unit", None, "tests/test_*.py 不存在"))
    if profile in ("standard", "full"):
        semgrep = shutil.which("semgrep")
        cfg = _semgrep_config(root)
        if semgrep and cfg:
            sast_targets = py_files or [scope]
            checks.append(CheckSpec("sast", (semgrep, "--error", "--json",
                                             "--config", str(cfg), *sast_targets)))
        else:
            checks.append(CheckSpec("sast", None, "semgrep 或 tools/semgrep.yml 不可用"))
        contract = _contract_file(root)
        checks.append(CheckSpec(
            "contract_test",
            (py, "-m", "orchestrator.tool_evidence", "--check-contract",
             str(contract)) if contract else None,
            "" if contract else "contracts/ 下没有 OpenAPI 文件"))
    if profile == "full":
        trivy = shutil.which("trivy")
        checks.append(CheckSpec(
            "secret_scan",
            (trivy, "fs", "--scanners", "secret", "--exit-code", "1",
             "--format", "json", "--quiet", ".") if trivy else None,
            "" if trivy else "trivy 不可用（完整扫描见 CI）"))
        base_url = os.environ.get("AGENTTEAM_API_BASE_URL", "").strip()
        contract = _contract_file(root)
        schemathesis = shutil.which("schemathesis")
        if base_url and contract and schemathesis:
            checks.append(CheckSpec(
                "api_test",
                (schemathesis, "run", str(contract), "--url", base_url,
                 "--checks", "all")))
    return checks


def _contract_check(path: Path) -> tuple[int, str, str]:
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return 2, "", f"OpenAPI 无法解析：{exc}"
    if not isinstance(doc, dict):
        return 2, "", "OpenAPI 根节点必须是对象"
    problems = []
    if not str(doc.get("openapi", "")).startswith("3."):
        problems.append("缺少 openapi 3.x")
    paths = doc.get("paths")
    if not isinstance(paths, dict) or not paths:
        problems.append("缺少 paths")
    else:
        for route, item in paths.items():
            if not str(route).startswith("/"):
                problems.append(f"路径必须以 / 开头：{route}")
            if not isinstance(item, dict) or not item:
                problems.append(f"路径没有操作：{route}")
                continue
            for method, op in item.items():
                if method.lower() not in ("get", "post", "put", "patch", "delete",
                                          "head", "options", "trace"):
                    continue
                if not isinstance(op, dict) or not op.get("responses"):
                    problems.append(f"{method.upper()} {route} 缺少 responses")
    if problems:
        return 2, "", "; ".join(problems)
    return 0, f"OpenAPI OK: {len(paths)} paths", ""


def collect(project_dir: str | Path, *, profile: str = "basic",
            code_root: str | Path | None = None, scope: str = "src",
            files: list[str] | None = None,
            ledger_path: str | Path | None = None,
            baseline_fp: str = "", key: bytes | None = None,
            timeout_s: int = 180, ttl_s: int = 7200) -> dict[str, Any]:
    """Run the profile and append signed evidence records to the ledger."""
    project_dir = Path(project_dir).resolve()
    root = Path(code_root).resolve() if code_root else project_dir
    ledger = Path(ledger_path) if ledger_path else project_dir / "evidence" / "tool-ledger.jsonl"
    store = EvidenceStore(ledger, key or signing_key())
    sandbox = Sandbox(root, timeout_s=timeout_s)
    subject = tree_hash(root)
    results: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for spec in build_checks(root, profile, sandbox, scope=scope, files=files):
        if spec.argv is None:
            missing.append({"kind": spec.kind, "reason": spec.reason,
                            "required": spec.required})
            results.append({"kind": spec.kind, "status": "missing",
                            "reason": spec.reason})
            continue
        if spec.kind == "contract_test":
            path = Path(spec.argv[-1])
            code, out, err = _contract_check(path)
            duration = 0
            tool, version = "contract-check", "1"
        else:
            try:
                run = sandbox.run(list(spec.argv))
            except SandboxError as exc:
                missing.append({"kind": spec.kind, "reason": str(exc),
                                "required": spec.required})
                results.append({"kind": spec.kind, "status": "blocked",
                                "reason": str(exc)})
                continue
            code, out, err = run.exit_code, run.stdout, run.stderr
            duration = run.duration_ms
            tool = Path(spec.argv[0]).name.replace(".exe", "")
            if spec.kind == "unit":
                tool = "pytest" if "pytest" in spec.argv else "unittest"
            version = _tool_version(sandbox, spec.argv[0]) if tool in ("semgrep", "trivy", "schemathesis") \
                else (_python_version() if tool in ("python", "pytest", "unittest") else "")

        if spec.kind == "unit" and code == 0 and "Ran 0 tests" in (out + err):
            code = 1
            err = (err + "\n没有收集到测试").strip()
        result = "pass" if code == 0 else "fail"
        payload = {
            "profile": profile, "check": spec.kind, "argv": list(spec.argv),
            "exit_code": code, "duration_ms": duration,
            "stdout_tail": out[-1200:], "stderr_tail": err[-1200:],
            "subject_hash": subject,
        }
        rec = store.add(
            kind=spec.kind, subject_hash=subject, tool=tool,
            tool_version=version, result=result, payload=payload,
            signed_by=f"tool:{tool}", baseline_fp=baseline_fp or "project", ttl_s=ttl_s)
        evidence.append(rec)
        results.append({"kind": spec.kind, "status": result,
                        "exit_code": code, "duration_ms": duration,
                        "evidence_id": rec["evidence_id"], "tool": tool,
                        "reason": (err or out)[-300:] if result == "fail" else ""})
    return {"subject_hash": subject, "profile": profile,
            "ledger": str(ledger), "evidence": evidence,
            "results": results, "missing": missing,
            "passed": [e["kind"] for e in evidence if e["result"] == "pass"],
            "failed": [e["kind"] for e in evidence if e["result"] == "fail"]}


def required_kinds(profile: str) -> set[str]:
    if profile == "basic":
        return {"compile", "unit"}
    if profile == "standard":
        return {"compile", "unit", "sast", "contract_test"}
    return {"compile", "unit", "sast", "contract_test", "secret_scan"}


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Collect signed tool evidence")
    p.add_argument("--project", default=".")
    p.add_argument("--code-root", default=None)
    p.add_argument("--profile", default="basic", choices=PROFILES)
    p.add_argument("--ledger", default=None)
    p.add_argument("--baseline-fp", default="")
    p.add_argument("--check-contract", default=None, help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    if args.check_contract:
        code, out, err = _contract_check(Path(args.check_contract))
        print(out or err)
        return code
    result = collect(args.project, profile=args.profile, code_root=args.code_root,
                     ledger_path=args.ledger, baseline_fp=args.baseline_fp)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["failed"] and not result["missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
