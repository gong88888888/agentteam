#!/usr/bin/env bash
# 本地启动静态服务器（ESM 需 http 协议）
set -euo pipefail
PORT="${1:-8080}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "[ops] serving $ROOT at http://localhost:${PORT}/game/index.html"
cd "$ROOT"
exec python3 -m http.server "$PORT"
