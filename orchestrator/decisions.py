"""Decision inbox for escalated / audit / L3 policy-owner decisions."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS decisions (
  id TEXT PRIMARY KEY,
  gate_id TEXT NOT NULL,
  title TEXT NOT NULL,
  scope TEXT NOT NULL,
  risk TEXT NOT NULL,
  status TEXT NOT NULL,
  options TEXT NOT NULL,
  packet TEXT NOT NULL,
  verdicts TEXT NOT NULL,
  evidence TEXT NOT NULL,
  recommendation TEXT NOT NULL,
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL,
  decided_at REAL,
  decision TEXT,
  reason TEXT,
  actor TEXT
);
CREATE TABLE IF NOT EXISTS decision_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  decision_id TEXT NOT NULL,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  reason TEXT NOT NULL,
  at REAL NOT NULL
);
"""

ACTIONS = {
    "approve": "approved",
    "approve_with_conditions": "approved_with_conditions",
    "reject": "rejected",
    "defer": "deferred",
    "request_evidence": "evidence_requested",
}


class DecisionStore:
    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def create(self, *, decision_id: str, gate_id: str, title: str,
               scope: dict[str, Any], risk: str, options: list[dict[str, Any]],
               packet: dict[str, Any], verdicts: list[dict[str, Any]],
               evidence: list[dict[str, Any]], recommendation: str,
               ttl_s: int = 24 * 3600, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        with self._conn() as con:
            if con.execute("SELECT 1 FROM decisions WHERE id=?", (decision_id,)).fetchone():
                return self.get(decision_id) or {}
            con.execute(
                "INSERT INTO decisions(id,gate_id,title,scope,risk,status,options,packet,"
                "verdicts,evidence,recommendation,created_at,expires_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (decision_id, gate_id, title, json.dumps(scope, ensure_ascii=False),
                 risk, "pending", json.dumps(options, ensure_ascii=False),
                 json.dumps(packet, ensure_ascii=False),
                 json.dumps(verdicts, ensure_ascii=False),
                 json.dumps(evidence, ensure_ascii=False),
                 recommendation, now, now + ttl_s))
        return self.get(decision_id) or {}

    def _row(self, row: sqlite3.Row, *, full: bool = False) -> dict[str, Any]:
        out = {
            "id": row["id"], "gate_id": row["gate_id"], "title": row["title"],
            "scope": json.loads(row["scope"]), "risk": row["risk"],
            "status": row["status"],
            "recommendation": row["recommendation"],
            "created_at": row["created_at"], "expires_at": row["expires_at"],
            "decided_at": row["decided_at"], "decision": row["decision"],
            "reason": row["reason"], "actor": row["actor"],
        }
        options = json.loads(row["options"])
        out["option_count"] = len(options)
        out["options"] = options if full else []
        verdicts = json.loads(row["verdicts"])
        out["verdict_summary"] = [{"tier": v.get("tier"),
                                    "decision": v.get("decision"),
                                    "confidence": v.get("confidence")}
                                   for v in verdicts]
        if full:
            out["packet"] = json.loads(row["packet"])
            out["verdicts"] = verdicts
            out["evidence"] = json.loads(row["evidence"])
            out["audit"] = self.audit(row["id"])
        return out

    def list(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM decisions"
        params: list[Any] = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        with self._conn() as con:
            return [self._row(r) for r in con.execute(sql, params)]

    def get(self, decision_id: str) -> dict[str, Any] | None:
        with self._conn() as con:
            row = con.execute("SELECT * FROM decisions WHERE id=?", (decision_id,)).fetchone()
            return self._row(row, full=True) if row else None

    def decide(self, decision_id: str, action: str, reason: str = "",
               actor: str = "policy-owner") -> dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError(f"未知动作：{action}")
        if action in ("reject", "defer", "request_evidence",
                      "approve_with_conditions") and not reason.strip():
            raise ValueError(f"{action} 必须填写理由")
        row = self.get(decision_id)
        if not row:
            raise KeyError(f"决策不存在：{decision_id}")
        if row["status"] != "pending":
            raise ValueError(f"决策 {decision_id} 已处理：{row['status']}")
        now = time.time()
        if row["expires_at"] <= now and action == "approve":
            raise ValueError("决策已过期，不能直接批准")
        with self._conn() as con:
            con.execute(
                "UPDATE decisions SET status=?, decided_at=?, decision=?, reason=?, actor=? "
                "WHERE id=?",
                (ACTIONS[action], now, action, reason, actor, decision_id))
            con.execute(
                "INSERT INTO decision_audit(decision_id,action,actor,reason,at) "
                "VALUES(?,?,?,?,?)", (decision_id, action, actor, reason, now))
        return self.get(decision_id) or {}

    def audit(self, decision_id: str) -> list[dict[str, Any]]:
        with self._conn() as con:
            rows = con.execute(
                "SELECT action,actor,reason,at FROM decision_audit "
                "WHERE decision_id=? ORDER BY at ASC", (decision_id,)).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        now = time.time()
        with self._conn() as con:
            total = con.execute("SELECT COUNT(*) n FROM decisions").fetchone()["n"]
            pending = con.execute("SELECT COUNT(*) n FROM decisions WHERE status='pending'").fetchone()["n"]
            high = con.execute("SELECT COUNT(*) n FROM decisions WHERE status='pending' "
                               "AND risk IN ('high','critical')").fetchone()["n"]
            expiring = con.execute("SELECT COUNT(*) n FROM decisions WHERE status='pending' "
                                   "AND expires_at <= ?", (now + 24 * 3600,)).fetchone()["n"]
            decided = con.execute("SELECT COUNT(*) n FROM decisions "
                                  "WHERE status != 'pending'").fetchone()["n"]
        return {"total": total, "pending": pending, "high_risk": high,
                "expiring_24h": expiring, "decided": decided}

    def seed_demo(self) -> int:
        if self.list():
            return 0
        now = time.time()
        base_evidence = [
            {"evidence_id": "EV-000101", "kind": "unit", "result": "pass",
             "tool": "pytest", "signed_by": "tool:pytest"},
            {"evidence_id": "EV-000102", "kind": "contract_test", "result": "pass",
             "tool": "schemathesis", "signed_by": "tool:schemathesis"},
            {"evidence_id": "EV-000103", "kind": "sast", "result": "pass",
             "tool": "semgrep", "signed_by": "tool:semgrep"},
            {"evidence_id": "EV-000104", "kind": "rollback_rehearsal",
             "result": "pass", "tool": "ops-tool", "signed_by": "tool:ops-tool"},
        ]
        packet = {
            "gate_id": "G-ARCH-X1",
            "scope": {"project": "MiniLedger", "slice": "X0", "risk": "high"},
            "baseline_versions": {"product": "v1.1", "arch": "v1.1"},
            "subject_hash": "subj-x1-v11",
            "deterministic_checks": [
                {"evidence_id": e["evidence_id"], "kind": e["kind"],
                 "result": e["result"], "tool": e["tool"],
                 "tool_version": "test@1", "signed_by": e["signed_by"]}
                for e in base_evidence[:3]],
            "missing_evidence": [],
            "diff": {"out_of_scope_writes": 0},
            "content_isolation": {"sanitized": True, "instruction_like_blocks": 0},
        }
        self.create(
            decision_id="DEC-X1-001", gate_id="G-ARCH-X1",
            title="X1 认证契约升级 v1.1（owner check）",
            scope=packet["scope"], risk="high",
            options=[
                {"id": "A", "summary": "沿用 v1.0，新增兼容字段", "cost": "低",
                 "risk": "中", "reversible": True},
                {"id": "B", "summary": "升级 v1.1，迁移 3 个切片", "cost": "中",
                 "risk": "低", "reversible": False},
                {"id": "C", "summary": "推迟到 v1.1 版本", "cost": "无",
                 "risk": "低", "reversible": True},
            ],
            packet=packet,
            verdicts=[
                {"tier": "J1", "decision": "approve", "confidence": 0.91,
                 "model": "deepseek-chat", "reason": "契约测试与 SAST 通过"},
                {"tier": "J2", "decision": "approve", "confidence": 0.87,
                 "model": "qwen3.6", "reason": "兼容字段风险可控"},
                {"tier": "J3", "decision": "approve", "confidence": 0.9,
                 "model": "deepseek-reasoner", "reason": "建议 A + 兼容测试"},
            ],
            evidence=base_evidence,
            recommendation="建议 A：沿用 v1.0 + 兼容字段；合并前补一条契约兼容测试。",
            ttl_s=24 * 3600, now=now)
        self.create(
            decision_id="DEC-REL-001", gate_id="G-RELEASE",
            title="生产发布 v1.0.0（10% 灰度）",
            scope={"project": "MiniLedger", "slice": "X0", "risk": "high"},
            risk="high",
            options=[
                {"id": "A", "summary": "批准 10% 灰度发布", "cost": "低",
                 "risk": "中", "reversible": True},
                {"id": "B", "summary": "延迟发布，补回滚演练", "cost": "低",
                 "risk": "低", "reversible": True},
            ],
            packet={**packet, "gate_id": "G-RELEASE",
                    "subject_hash": "subj-release-v100",
                    "deterministic_checks": [
                        {"evidence_id": e["evidence_id"], "kind": e["kind"],
                         "result": e["result"], "tool": e["tool"],
                         "tool_version": "test@1", "signed_by": e["signed_by"]}
                        for e in base_evidence]},
            verdicts=[
                {"tier": "J2", "decision": "approve", "confidence": 0.88,
                 "model": "qwen3.6", "reason": "回滚演练有证据"},
                {"tier": "J3", "decision": "approve", "confidence": 0.92,
                 "model": "deepseek-reasoner", "reason": "灰度与监控达标"},
            ],
            evidence=base_evidence,
            recommendation="建议 A：10% 灰度；异常立即回滚并保留现场。",
            ttl_s=12 * 3600, now=now)
        self.create(
            decision_id="DEC-L3-001", gate_id="G-POLICY-L3",
            title="启用等价重构快速路径（L3 策略变更）",
            scope={"project": "AgentTeam", "slice": "X0", "risk": "critical"},
            risk="critical",
            options=[
                {"id": "A", "summary": "保持关闭（默认）", "cost": "无",
                 "risk": "低", "reversible": True},
                {"id": "B", "summary": "启用，需双裁判一致 + 10% 抽样",
                 "cost": "中", "risk": "中", "reversible": True},
                {"id": "C", "summary": "先做 3 个月影子评估", "cost": "低",
                 "risk": "低", "reversible": True},
            ],
            packet={**packet, "gate_id": "G-POLICY-L3",
                    "subject_hash": "subj-policy-refactor",
                    "missing_evidence": ["shadow_eval_3m"]},
            verdicts=[
                {"tier": "J3", "decision": "need_evidence", "confidence": 0.8,
                 "model": "deepseek-reasoner",
                 "reason": "缺少 3 个月影子评估，无法证明可缩小复核范围"},
            ],
            evidence=base_evidence[:3],
            recommendation="建议 C：保持关闭，先跑影子评估；不满足 L3 条件。",
            ttl_s=72 * 3600, now=now)
        return 3


if __name__ == "__main__":
    import sys
    store = DecisionStore(sys.argv[1] if len(sys.argv) > 1 else "data/decisions.db")
    print(json.dumps({"seeded": store.seed_demo(), "stats": store.stats()},
                     ensure_ascii=False, indent=2))
