"""Minimal stdlib service scaffold. Roles may extend it within src/backend/**."""
from __future__ import annotations

import csv
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable

FIELDS = ("date", "amount", "category", "note")


def health_payload() -> dict[str, str]:
    return {"status": "ok"}


def monthly_csv(records: Iterable[dict[str, Any]], month: str) -> str:
    rows = [r for r in records if str(r.get("month", "")) == month]
    rows.sort(key=lambda r: str(r.get("date", "")))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, extrasaction="ignore",
                            lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in FIELDS})
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            body = json.dumps(health_payload()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        return


def serve(port: int = 8080) -> None:
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    serve()
