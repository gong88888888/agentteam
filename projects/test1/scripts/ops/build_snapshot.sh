#!/usr/bin/env bash
# ops 构建快照脚本：无打包，生成带版本号的静态目录快照 + sha256 清单
# 用法: bash scripts/ops/build_snapshot.sh v1.0.0
set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "[build] 用法: bash scripts/ops/build_snapshot.sh <version>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

OUT="artifacts/ops/releases/$VERSION"

# 1) 入口与关键目录存在性
for p in game/index.html game/js/core.js game/js/main.js game/js/gameplay game/js/ui; do
  if [[ ! -e "$p" ]]; then
    echo "[build] 缺少必需路径: $p" >&2
    exit 1
  fi
done

# 2) 路径合规检查：game/js 下不得出现越界产物
if find game/js -type f -path '*src/frontend*' | grep -q .; then
  echo "[build] 路径违规：game/js 下存在 src/frontend 产物，请先迁移到 game/js/ui/" >&2
  find game/js -type f -path '*src/frontend*' >&2
  exit 1
fi

# 3) 生成快照
rm -rf "$OUT"
mkdir -p "$OUT"
cp -R game "$OUT/game"

# 4) sha256 清单
( cd "$OUT" && find game -type f -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )

# 5) 发布元数据
cat > "$OUT/RELEASE.json" <<EOF
{
  "version": "$VERSION",
  "built_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "gate_checks": {},
  "known_issues": [],
  "rollback_target": null
}
EOF

echo "[build] 快照完成: $OUT"
echo "[build] 清单: $OUT/MANIFEST.sha256"
