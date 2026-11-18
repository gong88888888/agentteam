"""Minimal stdlib service scaffold. Roles may extend it within src/backend/**."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

FIELDS = ("date", "amount", "category", "note")
SAMPLE_RECORDS = (
    {"month": "2026-02", "date": "2026-02-01", "amount": "10",
     "category": "food", "note": "lunch"},
    {"month": "2026-02", "date": "2026-02-03", "amount": "25",
     "category": "transport", "note": "metro"},
    {"month": "2026-01", "date": "2026-01-31", "amount": "5",
     "category": "transport", "note": ""},
)


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


def export_csv(month: str) -> str:
    """Deterministic business flow used by runtime acceptance."""
    return monthly_csv(SAMPLE_RECORDS, month)


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, status: int, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, health_payload())
            return
        if parsed.path == "/api/v1/exports/csv":
            month = (parse_qs(parsed.query).get("month") or [""])[0]
            if not month:
                self._json(400, {"error": "month_required",
                                 "message": "查询参数 month=YYYY-MM 必填"})
                return
            self._text(200, export_csv(month), "text/csv; charset=utf-8")
            return
        self._json(404, {"error": "not_found", "path": parsed.path})

    def log_message(self, fmt: str, *args) -> None:
        return


def serve(port: int = 8080) -> None:
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as httpd:
        httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal export API")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("PORT", "8080")))
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
