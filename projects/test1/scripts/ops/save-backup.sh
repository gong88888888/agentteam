#!/usr/bin/env bash
# 存档备份占位：存储介质待确认（localStorage/IndexedDB/文件），见 open_questions
set -euo pipefail
TS="$(date +%Y%m%d-%H%M%S)"
DEST="${1:-artifacts/ops/save-backup-$TS}"
mkdir -p "$DEST"
echo "[ops] save backup target: $DEST"
echo "[ops] BLOCKED: storage backend unknown; wire to save.js before use"
exit 2
