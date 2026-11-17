#!/usr/bin/env bash
# ops 回滚脚本：切换到指定版本快照，不触碰玩家存档
# 用法: bash scripts/ops/rollback.sh <version> | --rehearsal
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "[rollback] 用法: bash scripts/ops/rollback.sh <version> | --rehearsal" >&2
  exit 2
fi

if [[ "$TARGET" == "--rehearsal" ]]; then
  echo "[rollback] 演练：检查可用快照"
  ls -1 artifacts/ops/releases/ 2>/dev/null || { echo "[rollback] 无可用快照" >&2; exit 1; }
  echo "[rollback] 演练通过（未切换）"
  exit 0
fi

SNAP="artifacts/ops/releases/$TARGET"
if [[ ! -d "$SNAP/game" || ! -f "$SNAP/MANIFEST.sha256" ]]; then
  echo "[rollback] 快照不完整: $SNAP" >&2
  exit 1
fi

# 校验快照完整性
( cd "$SNAP" && sha256sum -c MANIFEST.sha256 --quiet ) || { echo "[rollback] 快照校验失败" >&2; exit 1; }

# 切换：将当前 game 备份后替换为快照内容（不触碰存档，存档在浏览器侧）
CUR_BACKUP="artifacts/ops/releases/_pre_rollback_$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$CUR_BACKUP"
cp -R game "$CUR_BACKUP/game"
rm -rf game
cp -R "$SNAP/game" game

echo "[rollback] 已回滚到 $TARGET"
echo "[rollback] 回滚前代码备份: $CUR_BACKUP"
echo "[rollback] 请重跑 H1/H2/H4 并记录输出"
