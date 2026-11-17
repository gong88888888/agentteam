#!/usr/bin/env bash
# 本地启动：静态服务 + 入口提示。不修改任何 game/ 文件。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${PORT:-8080}"

if [ ! -f "$ROOT/game/index.html" ]; then
  echo "[ops] ERROR: game/index.html 不存在" >&2
  exit 1
fi

echo "[ops] 启动静态服务: http://localhost:${PORT}/game/index.html"
echo "[ops] 按 Ctrl+C 停止"
cd "$ROOT"
if command -v python3 >/dev/null 2>&1; then
  exec python3 -m http.server "$PORT"
else
  echo "[ops] ERROR: 未找到 python3，请安装或改用 npx serve" >&2
  exit 1
fi
