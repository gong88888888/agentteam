"""Minimal tool registry for the execution loop.

The model requests tools; the program validates name, arguments, path, write
scope and budget before executing. Tool failures are returned as observations,
never as success. ``run_check`` only accepts registered check IDs and records
signed tool evidence through the existing evidence pipeline.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..tool_evidence import collect


class ToolError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]

    def openai_spec(self) -> dict[str, Any]:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": self.parameters}}


TOOL_SPECS = [
    ToolSpec("read_file", "Read a file inside the project workspace.",
             {"type": "object", "required": ["path"], "properties": {
                 "path": {"type": "string"},
                 "max_chars": {"type": "integer", "minimum": 1}}}),
    ToolSpec("list_files", "List files under a project-relative directory.",
             {"type": "object", "properties": {
                 "path": {"type": "string"},
                 "pattern": {"type": "string"}}}),
    ToolSpec("search_text", "Search text in project files.",
             {"type": "object", "required": ["query"], "properties": {
                 "query": {"type": "string"},
                 "path": {"type": "string"},
                 "glob": {"type": "string"},
                 "max_results": {"type": "integer"}}}),
    ToolSpec("apply_patch", "Replace an exact anchor in a writable file.",
             {"type": "object", "required": ["path", "expected_hash", "old", "new"],
              "properties": {
                  "path": {"type": "string"},
                  "expected_hash": {"type": "string"},
                  "old": {"type": "string"},
                  "new": {"type": "string"}}}),
    ToolSpec("run_check", "Run a registered check (compile, unit, sast, contract_test).",
             {"type": "object", "required": ["check_id"], "properties": {
                 "check_id": {"type": "string"},
                 "scope": {"type": "string"}}}),
    ToolSpec("submit_result", "Submit the attempt result for independent verification.",
             {"type": "object", "required": ["status", "summary"], "properties": {
                 "status": {"type": "string",
                            "enum": ["ready_for_verification", "blocked"]},
                 "summary": {"type": "string"},
                 "artifact_refs": {"type": "array",
                                   "items": {"type": "string"}}}}),
]

CHECK_IDS = ("compile", "unit", "sast", "contract_test")


class ToolRegistry:
    def __init__(self, project_dir: str | Path, *,
                 write_scope: tuple[str, ...] = ("src/",),
                 ledger_path: str | Path | None = None,
                 baseline_fp: str = "",
                 max_read_chars: int = 6000,
                 check_runner: Callable[[str, str], dict[str, Any]] | None = None
                 ) -> None:
        self.root = Path(project_dir).resolve()
        self.write_scope = tuple(write_scope)
        self.ledger_path = Path(ledger_path) if ledger_path else \
            self.root / "evidence" / "tool-ledger.jsonl"
        self.baseline_fp = baseline_fp
        self.max_read_chars = max_read_chars
        self.check_runner = check_runner

    # ---------- path safety ----------
    def _path(self, raw: str, *, write: bool = False) -> Path:
        if not raw:
            raise ToolError("invalid_path", "path 不能为空")
        rel = Path(str(raw).replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ToolError("invalid_path", f"非法路径：{raw}")
        path = (self.root / rel).resolve()
        if path != self.root and not str(path).startswith(str(self.root) + os.sep):
            raise ToolError("invalid_path", f"路径越界：{raw}")
        if write and not any(rel.as_posix().startswith(prefix)
                             for prefix in self.write_scope):
            raise ToolError("write_scope", f"{rel.as_posix()} 不在写入范围 "
                                          f"{self.write_scope}")
        return path

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    # ---------- tools ----------
    def read_file(self, path: str, max_chars: int | None = None) -> dict[str, Any]:
        target = self._path(path)
        if not target.is_file():
            raise ToolError("not_found", f"文件不存在：{path}", retryable=True)
        raw = target.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        limit = int(max_chars or self.max_read_chars)
        truncated = len(text) > limit
        return {"path": path, "content": text[:limit], "truncated": truncated,
                "sha256": self._hash(raw), "chars": len(text)}

    def list_files(self, path: str = ".", pattern: str = "**/*") -> dict[str, Any]:
        base = self._path(path) if path not in (".", "") else self.root
        if not base.exists():
            raise ToolError("not_found", f"目录不存在：{path}", retryable=True)
        files = sorted(p.relative_to(self.root).as_posix()
                       for p in (base.rglob(pattern) if base.is_dir() else [base])
                       if p.is_file())[:300]
        return {"path": path, "files": files, "count": len(files)}

    def search_text(self, query: str, path: str = ".",
                    glob: str = "**/*", max_results: int = 50) -> dict[str, Any]:
        if not query:
            raise ToolError("invalid_args", "query 不能为空")
        base = self._path(path) if path not in (".", "") else self.root
        pattern = re.compile(re.escape(query), re.I)
        hits: list[dict[str, Any]] = []
        for file in (base.rglob(glob) if base.is_dir() else [base]):
            if not file.is_file() or "__pycache__" in file.parts:
                continue
            try:
                text = file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append({"path": file.relative_to(self.root).as_posix(),
                                 "line": line_no, "text": line.strip()[:300]})
                    if len(hits) >= int(max_results):
                        return {"query": query, "hits": hits,
                                "truncated": True, "count": len(hits)}
        return {"query": query, "hits": hits, "truncated": False,
                "count": len(hits)}

    def apply_patch(self, path: str, expected_hash: str, old: str,
                    new: str) -> dict[str, Any]:
        target = self._path(path, write=True)
        if not target.is_file():
            raise ToolError("not_found", f"文件不存在：{path}", retryable=True)
        raw = target.read_bytes()
        actual = self._hash(raw)
        if expected_hash and actual != expected_hash:
            raise ToolError("hash_mismatch",
                            f"{path} 已变化（期望 {expected_hash[:12]}，"
                            f"实际 {actual[:12]}）；请重新读取", retryable=True)
        text = raw.decode("utf-8")
        if old not in text:
            raise ToolError("anchor_not_found", f"{path} 中找不到替换锚点",
                            retryable=True)
        updated = text.replace(old, new, 1)
        target.write_text(updated, encoding="utf-8")
        return {"path": path, "old_hash": actual,
                "sha256": self._hash(updated.encode("utf-8")),
                "bytes": len(updated.encode("utf-8"))}

    def run_check(self, check_id: str, scope: str = "src") -> dict[str, Any]:
        if check_id not in CHECK_IDS:
            raise ToolError("unknown_check", f"未注册的检查：{check_id}")
        if self.check_runner is not None:
            result = self.check_runner(check_id, scope)
        else:
            profile = "basic" if check_id in ("compile", "unit") else "standard"
            collected = collect(self.root, profile=profile, scope=scope,
                                ledger_path=self.ledger_path,
                                baseline_fp=self.baseline_fp)
            rows = [r for r in collected.get("results", [])
                    if r.get("kind") == check_id]
            if not rows:
                raise ToolError("check_unavailable",
                                f"{check_id} 在当前环境不可用")
            result = rows[-1]
            result["evidence_id"] = next(
                (e["evidence_id"] for e in collected.get("evidence", [])
                 if e.get("kind") == check_id), "")
        status = str(result.get("status", "fail"))
        return {"check_id": check_id, "status": status,
                "success": status == "pass",
                "evidence_id": result.get("evidence_id", ""),
                "reason": result.get("reason", "")[:500]}

    def submit_result(self, status: str, summary: str,
                      artifact_refs: list[str] | None = None) -> dict[str, Any]:
        if status not in ("ready_for_verification", "blocked"):
            raise ToolError("invalid_args",
                            "submit status 只能是 ready_for_verification 或 blocked")
        if not str(summary).strip():
            raise ToolError("invalid_args", "submit summary 不能为空")
        return {"submitted": True, "status": status, "summary": str(summary)[:2000],
                "artifact_refs": list(artifact_refs or [])}

    # ---------- dispatch ----------
    def specs(self) -> list[dict[str, Any]]:
        return [spec.openai_spec() for spec in TOOL_SPECS]

    def execute(self, name: str, args: dict[str, Any] | None) -> dict[str, Any]:
        started = time.perf_counter()
        args = args or {}
        try:
            if name == "read_file":
                data = self.read_file(str(args.get("path", "")),
                                      args.get("max_chars"))
            elif name == "list_files":
                data = self.list_files(str(args.get("path", ".")),
                                       str(args.get("pattern", "**/*")))
            elif name == "search_text":
                data = self.search_text(str(args.get("query", "")),
                                        str(args.get("path", ".")),
                                        str(args.get("glob", "**/*")),
                                        int(args.get("max_results", 50)))
            elif name == "apply_patch":
                data = self.apply_patch(str(args.get("path", "")),
                                        str(args.get("expected_hash", "")),
                                        str(args.get("old", "")),
                                        str(args.get("new", "")))
            elif name == "run_check":
                data = self.run_check(str(args.get("check_id", "")),
                                      str(args.get("scope", "src")))
            elif name == "submit_result":
                data = self.submit_result(str(args.get("status", "")),
                                          str(args.get("summary", "")),
                                          args.get("artifact_refs") or [])
            else:
                raise ToolError("unknown_tool", f"未知工具：{name}")
        except ToolError as exc:
            return {"success": False, "error_type": exc.code,
                    "observations": str(exc), "retryable": exc.retryable,
                    "duration_ms": int((time.perf_counter() - started) * 1000)}
        except Exception as exc:
            return {"success": False, "error_type": "tool_error",
                    "observations": str(exc)[:500], "retryable": False,
                    "duration_ms": int((time.perf_counter() - started) * 1000)}
        return {"success": True, "error_type": "", "retryable": False,
                "data": data, "observations": json.dumps(data, ensure_ascii=False)[:1500],
                "evidence_ref": data.get("evidence_id", ""),
                "duration_ms": int((time.perf_counter() - started) * 1000)}
