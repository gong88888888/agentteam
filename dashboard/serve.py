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
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.decisions import DecisionStore  # noqa: E402

STORE = DecisionStore(ROOT / "data" / "decisions.db")
STORE.seed_demo()


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
