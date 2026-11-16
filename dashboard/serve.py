#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the W3 dashboard and the W4 decision inbox (static + JSON API).

  python dashboard/serve.py --port 8765
  open http://localhost:8765/
  open http://localhost:8765/decisions.html
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
from orchestrator.config import load_config  # noqa: E402
from orchestrator.project_runner import ProjectRunner, ROLE_MAP, ROLE_SPECS  # noqa: E402

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
    roles = []
    for spec in ROLE_SPECS:
        meta = state.get(spec.role)
        if not meta:
            continue
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
        })
    return {"name": p.name, "status": project.get("status", "unknown"),
            "requirement": project.get("requirement", "requirements/input.md"),
            "offline": project.get("offline"), "created_at": project.get("created_at"),
            "roles": roles}


def _project_detail(p: Path) -> dict:
    data = _project_summary(p)
    req = p / "requirements" / "input.md"
    data["requirement_text"] = req.read_text(encoding="utf-8")[:5000] if req.exists() else ""
    for r in data["roles"]:
        summary = p / "artifacts" / r["role"] / "summary.md"
        r["summary_text"] = summary.read_text(encoding="utf-8")[:2500] if summary.exists() else ""
    return data


def _role_detail(p: Path, role: str) -> dict | None:
    if role not in ROLE_MAP:
        return None
    base = p / "artifacts" / role
    if not base.exists():
        return None
    return {
        "role": role, "title": ROLE_MAP[role].title,
        "prompt": (base / "prompt.md").read_text(encoding="utf-8")
        if (base / "prompt.md").exists() else "",
        "request": (base / "request.md").read_text(encoding="utf-8")
        if (base / "request.md").exists() else "",
        "summary": (base / "summary.md").read_text(encoding="utf-8")
        if (base / "summary.md").exists() else "",
        "meta": _read_json(base / "meta.json", {}),
        "output": _read_json(base / "output.json", {}),
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
                     if p.is_dir()] if PROJECTS.exists() else []
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
            target = (p / rel).resolve()
            root = str(p)
            if not (str(target) == root or str(target).startswith(root + os.sep))                     or not target.is_file():
                return self._json(404, {"error": "file not found"})
            content = target.read_text(encoding="utf-8", errors="replace")
            return self._json(200, {"path": rel, "content": content[:200000]})
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
                with PROJECT_LOCK:
                    runner = ProjectRunner(
                        requirements=req, project_dir=p, cfg=CFG,
                        offline=bool(body.get("offline", True)),
                        roles=[role], merge_state=True,
                        extra_note=str(body.get("note", "")))
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
