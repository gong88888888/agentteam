#!/usr/bin/env bash
# ops 存档备份脚本（骨架）：归档玩家导出的存档 JSON，校验 version/crc 字段
# 用法: bash scripts/ops/backup_save.sh [--dry-run] [存档JSON路径]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

DRY_RUN=0
SRC=""
for a in "$@"; do
  case "$a" in
    --dry-run) DRY_RUN=1 ;;
    *) SRC="$a" ;;
  esac
done

TS="$(date -u +%Y%m%dT%H%M%SZ)"
DEST_DIR="artifacts/ops/save-backups/$TS"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "[backup] dry-run: 目标目录 $DEST_DIR"
  echo "[backup] dry-run: 请先在游戏内 设置 -> 导出存档 得到 JSON"
  exit 0
fi

if [[ -z "$SRC" || ! -f "$SRC" ]]; then
  echo "[backup] 需要提供存档 JSON 路径" >&2
  exit 2
fi

# 校验 JSON 含 version 与 crc 字段（不打印内容，避免泄露）
if ! grep -q '"version"' "$SRC" || ! grep -q '"crc"' "$SRC"; then
  echo "[backup] 存档缺少 version 或 crc 字段，拒绝归档" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST_DIR/save.json"
sha256sum "$DEST_DIR/save.json" > "$DEST_DIR/save.sha256"
echo "[backup] 已归档到 $DEST_DIR"
