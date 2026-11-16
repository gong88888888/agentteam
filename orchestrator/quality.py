"""Deterministic role quality scoring and per-project quality history."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .role_gates import GateResult


def score_role(role: str, obj: dict[str, Any], *,
               files: list[dict[str, Any]], gate: GateResult,
               tool_result: dict[str, Any] | None,
               latency_ms: int = 0, tokens: int = 0) -> dict[str, Any]:
    issues: list[str] = []
    summary = str(obj.get("summary", "")).strip()
    claims = obj.get("claims") or []
    questions = obj.get("open_questions") or []

    completeness = 0
    if obj.get("role") == role:
        completeness += 6
    else:
        issues.append("role 不匹配")
    if summary:
        completeness += 6
    else:
        issues.append("summary 为空")
    if claims:
        completeness += 8
    else:
        issues.append("没有 claims")
    if obj.get("status") == "done":
        completeness += 5
    else:
        issues.append(f"status={obj.get('status')}")
    authored = [f for f in files if f.get("source", "role") == "role"]
    if authored:
        completeness += 5
    else:
        issues.append("没有模型-authored 交付物")
    if any(f.get("source") == "runner-summary" for f in files):
        issues.append("存在 runner-summary 补写的文档")
    completeness = min(30, completeness)

    gate_score = 30 if gate.status == "pass" else (15 if gate.status == "need_evidence" else 0)
    if gate.status != "pass":
        issues += [f"{c.name}: {c.detail}" for c in gate.checks if not c.ok][:4]

    evidence = 0
    if tool_result:
        kinds = {e.get("kind") for e in tool_result.get("evidence", [])
                 if e.get("result") == "pass"}
        required = {"compile", "unit"} if tool_result.get("profile") == "basic" else set()
        if required:
            evidence = int(20 * len(kinds & required) / len(required))
        else:
            evidence = 12 if gate.status == "pass" else 6
        if any(e.get("result") == "fail" for e in tool_result.get("evidence", [])):
            issues.append("存在失败工具证据")
    else:
        evidence = 20 if gate.status == "pass" and role not in ("backend", "frontend") else 0

    def band(value: int, points: tuple[int, int, int, int]) -> int:
        if value <= 15_000:
            return points[0]
        if value <= 30_000:
            return points[1]
        if value <= 60_000:
            return points[2]
        return points[3]

    efficiency = (band(latency_ms, (5, 4, 2, 1)) +
                  band(tokens, (5, 4, 2, 1))) if (latency_ms or tokens) else 6
    if latency_ms > 60_000:
        issues.append("耗时超过 60s")

    clarity = 0
    if 20 <= len(summary) <= 800:
        clarity += 5
    if 1 <= len(claims) <= 6:
        clarity += 3
    if len(questions) <= 3:
        clarity += 2
    else:
        issues.append(f"{len(questions)} 个未决问题")

    total = max(0, min(100, completeness + gate_score + evidence + efficiency + clarity))
    grade = "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 55 else "D"
    return {
        "score": total, "grade": grade,
        "components": {"completeness": completeness, "gate": gate_score,
                       "evidence": evidence, "efficiency": efficiency,
                       "clarity": clarity},
        "issues": issues[:8],
    }


def append_history(project_dir: str | Path, *, role: str, quality: dict[str, Any],
                   gate: GateResult, obj: dict[str, Any], meta: dict[str, Any],
                   run_id: str = "") -> dict[str, Any]:
    path = Path(project_dir) / "quality" / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id,
        "role": role,
        "score": quality["score"],
        "grade": quality["grade"],
        "components": quality["components"],
        "gate": gate.status,
        "gate_checks": len(gate.checks),
        "failed_checks": [c.name for c in gate.checks if not c.ok],
        "model": meta.get("model", ""),
        "backend": meta.get("backend", ""),
        "latency_ms": meta.get("latency_ms", 0),
        "tokens": meta.get("tokens", 0),
        "files": len(meta.get("files", [])),
        "status": obj.get("status", ""),
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_history(project_dir: str | Path, role: str | None = None) -> list[dict[str, Any]]:
    path = Path(project_dir) / "quality" / "history.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if role and rec.get("role") != role:
            continue
        rows.append(rec)
    return rows


def role_trend(project_dir: str | Path, role: str) -> dict[str, Any]:
    rows = load_history(project_dir, role)
    if not rows:
        return {"role": role, "latest": None, "average": None, "runs": 0, "points": []}
    scores = [r["score"] for r in rows]
    return {
        "role": role,
        "latest": scores[-1],
        "average": round(sum(scores) / len(scores), 1),
        "runs": len(scores),
        "points": [{"at": r.get("at", ""), "score": r["score"],
                    "gate": r.get("gate", ""), "run_id": r.get("run_id", "")}
                   for r in rows[-12:]],
    }
