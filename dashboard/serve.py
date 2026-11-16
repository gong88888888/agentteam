#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Serve the dashboard at http://localhost:8765 (optional; index.html is offline-capable)."""
from __future__ import annotations

import argparse
import http.server
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    os.chdir(HERE)  # serve only the dashboard directory
    handler = http.server.SimpleHTTPRequestHandler
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"dashboard -> http://localhost:{args.port}/index.html")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
