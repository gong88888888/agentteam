#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the W3 dashboard, W4 decision inbox and W5 role monitor.

  python dashboard/serve.py --port 8765
  open http://localhost:8765/
  open http://localhost:8765/decisions.html
  open http://localhost:8765/projects.html
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.decisions import DecisionStore  # noqa: E402
from orchestrator.config import load_config, signing_key  # noqa: E402
from orchestrator.evidence.store import EvidenceStore  # noqa: E402
from orchestrator.project_runner import ProjectRunner, ROLE_MAP, ROLE_SPECS  # noqa: E402
from orchestrator.quality import role_trend  # noqa: E402

STORE = DecisionStore(ROOT / "data" / "decisions.db")
STORE.seed_demo()
PROJECTS = ROOT / "projects"
CFG = load_config()
PROJECT_LOCK = threading.Lock()


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _project_dir(name: str) -> Path | None:
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        return None
    p = PROJECTS / name
    return p if p.is_dir() else None


def _project_summary(p: Path) -> dict:
    project = _read_json(p / "project.json", {})
    state = _read_json(p / "state" / "roles.json", {})
    progress = _read_json(p / "state" / "progress.json", {})
    roles = []
    for spec in ROLE_SPECS:
        meta = state.get(spec.role)
        if not meta:
            continue
        gate = meta.get("gate") or {}
        quality = meta.get("quality") or {}
        tools = meta.get("tools") or {}
        roles.append({
            "role": spec.role, "title": spec.title,
            "status": meta.get("status", "—"),
            "model": meta.get("model", "—"),
            "prompt": meta.get("prompt", {}),
            "latency_ms": meta.get("latency_ms", 0),
            "tokens": meta.get("tokens", 0),
            "files": meta.get("files", []),
            "code_pass": meta.get("code_pass", False),
            "adjustment": meta.get("adjustment", ""),
            "gate": {"status": gate.get("status", "off"),
                     "gate_id": gate.get("gate_id", ""),
                     "decision_id": gate.get("decision_id")},
            "quality": {"score": quality.get("score"),
                        "grade": quality.get("grade")},
            "tools": {"profile": tools.get("profile"),
                      "passed": tools.get("passed", []),
                      "failed": tools.get("failed", []),
                      "missing": tools.get("missing", []),
                      "subject_hash": tools.get("subject_hash", "")},
            "sandbox": meta.get("sandbox", "direct"),
            "started_at": meta.get("started_at"),
            "started_clock": meta.get("started_clock", ""),
            "finished_at": meta.get("finished_at", ""),
        })
    return {"name": p.name, "status": project.get("status", "unknown"),
            "requirement": project.get("requirement", "requirements/input.md"),
            "offline": project.get("offline"), "created_at": project.get("created_at"),
            "updated_at": project.get("updated_at", ""),
            "current_role": project.get("current_role", ""),
            "current_index": project.get("current_index", 0),
            "total_roles": project.get("total_roles", len(roles)),
            "progress": progress,
            "project_type": project.get("project_type", "web"),
            "acceptance": project.get("acceptance"),
            "dod": project.get("dod"),
            "stages": project.get("stages", []),
            "preflight": project.get("preflight"),
            "process_metrics": project.get("process_metrics", {}),
            "template": project.get("template", "none"),
            "template_hash": project.get("template_hash", ""),
            "tool_profile": project.get("tool_profile", "basic"),
            "gates": project.get("gates", {}),
            "quality_avg": project.get("quality_avg"),
            "run_id": project.get("run_id", ""),
            "roles": roles}


def _project_detail(p: Path) -> dict:
    data = _project_summary(p)
    req = p / "requirements" / "input.md"
    data["requirement_text"] = req.read_text(encoding="utf-8")[:5000] if req.exists() else ""
    trends = {r["role"]: role_trend(p, r["role"]) for r in data["roles"]}
    for r in data["roles"]:
        summary = p / "artifacts" / r["role"] / "summary.md"
        r["summary_text"] = summary.read_text(encoding="utf-8")[:2500] if summary.exists() else ""
        r["trend"] = trends.get(r["role"])
    return data


def _role_detail(p: Path, role: str) -> dict | None:
    if role not in ROLE_MAP:
        return None
    base = p / "artifacts" / role
    if not base.exists():
        return None
    meta = _read_json(base / "meta.json", {})
    return {
        "role": role, "title": ROLE_MAP[role].title,
        "prompt": (base / "prompt.md").read_text(encoding="utf-8")
        if (base / "prompt.md").exists() else "",
        "request": (base / "request.md").read_text(encoding="utf-8")
        if (base / "request.md").exists() else "",
        "summary": (base / "summary.md").read_text(encoding="utf-8")
        if (base / "summary.md").exists() else "",
        "meta": meta,
        "output": _read_json(base / "output.json", {}),
        "quality_history": role_trend(p, role),
        "template": _read_json(p / ".agentteam" / "template.json", {}),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "AgentTeamDashboard/1.0"

    def _send(self, status: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _static(self, path: str) -> None:
        rel = unquote(path.lstrip("/")) or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        target = (HERE / rel).resolve()
        if not str(target).startswith(str(HERE.resolve())) or not target.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",
                                                  "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if u.path == "/api/health":
            return self._json(200, {"ok": True, "stats": STORE.stats()})
        if u.path == "/api/decisions/stats":
            return self._json(200, STORE.stats())
        if u.path == "/api/decisions":
            status = (parse_qs(u.query).get("status") or [None])[0]
            return self._json(200, {"decisions": STORE.list(status),
                                    "stats": STORE.stats()})
        if len(parts) == 3 and parts[:2] == ["api", "decisions"]:
            item = STORE.get(parts[2])
            if not item:
                return self._json(404, {"error": "decision not found"})
            return self._json(200, item)
        if u.path == "/api/projects":
            items = [_project_summary(p) for p in sorted(PROJECTS.iterdir())
                     if p.is_dir() and not p.name.startswith(("_", "."))] if PROJECTS.exists() else []
            return self._json(200, {"projects": items})
        if len(parts) == 3 and parts[:2] == ["api", "projects"]:
            p = _project_dir(parts[2])
            if not p:
                return self._json(404, {"error": "project not found"})
            return self._json(200, _project_detail(p))
        if len(parts) == 5 and parts[:2] == ["api", "projects"]                 and parts[3] == "roles":
            p = _project_dir(parts[2])
            if not p:
                return self._json(404, {"error": "project not found"})
            item = _role_detail(p, parts[4])
            return self._json(200, item) if item else self._json(404, {"error": "role not found"})
        if len(parts) == 4 and parts[:2] == ["api", "projects"]                 and parts[3] == "file":
            p = _project_dir(parts[2])
            if not p:
                return self._json(404, {"error": "project not found"})
            rel = (parse_qs(u.query).get("path") or [""])[0].replace("\\", "/").lstrip("/")
            if not rel or ".." in Path(rel).parts:
                return self._json(400, {"error": "invalid path"})
            target = (p / rel).resolve()
            root = str(p)
            sandboxed = False
            if not (str(target) == root or str(target).startswith(root + os.sep))                     or not target.is_file():
                for cand in sorted((p / "artifacts").glob(f"*/sandbox/{rel}")):
                    c = cand.resolve()
                    if str(c).startswith(str((p / "artifacts").resolve()) + os.sep)                             and c.is_file():
                        target, sandboxed = c, True
                        break
            if not target.is_file():
                return self._json(404, {"error": "file not found"})
            content = target.read_text(encoding="utf-8", errors="replace")
            return self._json(200, {"path": rel, "sandboxed": sandboxed,
                                    "content": content[:200000]})
        if len(parts) >= 2 and parts[0] == "game":
            project = _project_dir(parts[1])
            if not project:
                return self._send(404, b"project not found", "text/plain; charset=utf-8")
            base = (project / "game").resolve()
            rel = unquote("/".join(parts[2:])) or "index.html"
            target = (base / rel).resolve()
            if not str(target).startswith(str(base) + os.sep) or not target.is_file():
                return self._send(404, b"game file not found", "text/plain; charset=utf-8")
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            return self._send(200, target.read_bytes(), ctype)
        if len(parts) == 4 and parts[:2] == ["api", "projects"]                 and parts[3] == "evidence":
            p = _project_dir(parts[2])
            if not p:
                return self._json(404, {"error": "project not found"})
            ledger = p / "evidence" / "tool-ledger.jsonl"
            if not ledger.exists():
                return self._json(200, {"records": [], "chain_ok": True})
            try:
                store = EvidenceStore(ledger, signing_key())
                rows = [{"evidence_id": r.get("evidence_id"), "kind": r.get("kind"),
                         "tool": r.get("tool"), "tool_version": r.get("tool_version"),
                         "result": r.get("result"), "signed_by": r.get("signed_by"),
                         "subject_hash": r.get("subject_hash"),
                         "created_at": r.get("created_at"),
                         "expires_at": r.get("expires_at")}
                        for r in store.all() if r.get("type") == "evidence"]
                return self._json(200, {"records": rows[-200:],
                                        "chain_ok": store.verify_chain()})
            except Exception as exc:
                return self._json(200, {"records": [], "chain_ok": False,
                                        "error": str(exc)[:500]})
        return self._static(u.path)

    def do_POST(self) -> None:
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if len(parts) == 4 and parts[:2] == ["api", "decisions"] \
                and parts[3] == "decision":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) or b"{}"
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("gbk", errors="replace")
                body = json.loads(text)
                item = STORE.decide(parts[2], str(body.get("action", "")),
                                    str(body.get("reason", "")),
                                    str(body.get("actor", "policy-owner")))
                return self._json(200, item)
            except KeyError as exc:
                return self._json(404, {"error": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                return self._json(400, {"error": str(exc)})
        if len(parts) == 6 and parts[:2] == ["api", "projects"]                 and parts[3] == "roles" and parts[5] == "rerun":
            p = _project_dir(parts[2])
            role = parts[4]
            if not p:
                return self._json(404, {"error": "project not found"})
            if role not in ROLE_MAP:
                return self._json(404, {"error": "role not found"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) or b"{}"
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("gbk", errors="replace")
                body = json.loads(text)
                req = p / "requirements" / "input.md"
                if not req.exists():
                    return self._json(400, {"error": "requirements/input.md missing"})
                project = _read_json(p / "project.json", {})
                template = str(_read_json(p / ".agentteam" / "template.json", {})
                               .get("template") or project.get("template") or "none")
                profile = str(body.get("profile") or project.get("tool_profile") or "basic")
                with PROJECT_LOCK:
                    runner = ProjectRunner(
                        requirements=req, project_dir=p, cfg=CFG,
                        offline=bool(body.get("offline", True)),
                        roles=[role], merge_state=True,
                        extra_note=str(body.get("note", "")),
                        template=template, tool_profile=profile,
                        sandbox=bool(body.get("sandbox", False)),
                        stop_on_gate=bool(body.get("stop_on_gate", False)))
                    result = runner.run()
                return self._json(200, {"result": result,
                                        "project": _project_summary(p),
                                        "role": _role_detail(p, role)})
            except Exception as exc:
                return self._json(500, {"error": str(exc)[:1000]})
        return self._json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        # Keep the console quiet; errors still surface as HTTP responses.
        if args and str(args[1]).startswith("5"):
            print(fmt % args)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"dashboard -> http://localhost:{args.port}/")
        print(f"decisions -> http://localhost:{args.port}/decisions.html")
        print(f"api       -> http://localhost:{args.port}/api/decisions")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
