#!/usr/bin/env bash
# 发布快照：复制 game/docs/contracts 到 artifacts/ops/release-<version> 并生成 manifest.sha256
set -euo pipefail
VERSION="${1:?usage: snapshot.sh <version>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/artifacts/ops/release-$VERSION"
mkdir -p "$OUT"
for d in game docs contracts; do
  if [ -d "$ROOT/$d" ]; then cp -R "$ROOT/$d" "$OUT/"; fi
done
cd "$OUT"
find . -type f ! -name manifest.sha256 -print0 | sort -z | xargs -0 sha256sum > manifest.sha256
echo "[ops] snapshot -> $OUT"
