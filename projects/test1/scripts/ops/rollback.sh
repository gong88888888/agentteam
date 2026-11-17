#!/usr/bin/env bash
# 回滚：按构建清单恢复 game/，校验 sha256，保留现场。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ART="$ROOT/artifacts/ops"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="$ART/logs/rollback-$TS.log"
TARGET="${1:-}"
DRY="${2:-}"

mkdir -p "$ART/logs"
exec > >(tee -a "$LOG") 2>&1

if [ -z "$TARGET" ]; then
  echo "[ops] 可用构建:" >&2
  ls -1 "$ART" | grep '^build-' || true
  echo "[ops] 用法: rollback.sh <build-dir> [--dry-run]" >&2
  exit 1
fi

SRC="$ART/$TARGET"
if [ ! -d "$SRC/game" ] || [ ! -f "$SRC/manifest.sha256" ]; then
  echo "[ops] BLOCKED: 目标构建不完整 $SRC" >&2
  exit 2
fi

if [ "$DRY" = "--dry-run" ]; then
  echo "[ops] DRY-RUN: 将恢复 $SRC/game -> $ROOT/game"
  ( cd "$SRC" && sha256sum -c manifest.sha256 ) || { echo "[ops] BLOCKED: 清单校验失败" >&2; exit 3; }
  echo "[ops] DRY-RUN ok"
  exit 0
fi

( cd "$SRC" && sha256sum -c manifest.sha256 ) || { echo "[ops] BLOCKED: 清单校验失败" >&2; exit 3; }
rm -rf "$ROOT/game"
cp -R "$SRC/game" "$ROOT/game"
echo "[ops] 回滚完成，重跑基线测试"
if ! ( cd "$ROOT" && node --test game/tests/game_logic.test.mjs && node game/tests/smoke.mjs ); then
  echo "[ops] BLOCKED: 回滚后基线测试失败，保留现场" >&2
  exit 4
fi
echo "[ops] 回滚 ok"
