#!/usr/bin/env bash
# 构建：基座哈希基线校验 + 基线测试门禁 + 打包。任一失败即 BLOCKED。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ART="$ROOT/artifacts/ops"
BASE="$ART/baseline.sha256"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$ART/build-$TS"
LOG="$ART/logs/build-$TS.log"

mkdir -p "$ART/logs"
exec > >(tee -a "$LOG") 2>&1

echo "[ops] build start $TS"

# 1. 基座文件哈希基线
BASEFILES=(
  "game/js/core.js"
  "game/js/main.js"
  "game/index.html"
  "game/tests/game_logic.test.mjs"
  "game/tests/smoke.mjs"
)
if [ ! -f "$BASE" ]; then
  echo "[ops] 生成基座哈希基线"
  ( cd "$ROOT" && sha256sum "${BASEFILES[@]}" ) > "$BASE"
fi
if ! ( cd "$ROOT" && sha256sum -c "$BASE" ); then
  echo "[ops] BLOCKED: 基座文件被修改" >&2
  exit 2
fi

# 2. 基线测试门禁
if ! ( cd "$ROOT" && node --test game/tests/game_logic.test.mjs ); then
  echo "[ops] BLOCKED: game_logic 测试失败" >&2
  exit 3
fi
if ! ( cd "$ROOT" && node game/tests/smoke.mjs ); then
  echo "[ops] BLOCKED: smoke 失败" >&2
  exit 4
fi

# 3. 打包
mkdir -p "$OUT"
cp -R "$ROOT/game" "$OUT/game"
( cd "$OUT" && find game -type f -print0 | sort -z | xargs -0 sha256sum ) > "$OUT/manifest.sha256"
echo "[ops] build ok -> $OUT"
echo "[ops] 注意：生产发布仍需裁判凭证，脚本不绕过。"
