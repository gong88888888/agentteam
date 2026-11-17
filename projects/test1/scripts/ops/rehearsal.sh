#!/usr/bin/env bash
# 回滚演练：临时副本上 快照→破坏→回滚→校验
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "[ops] rehearsal in $TMP"
cp -R "$ROOT/game" "$TMP/game"
cd "$TMP"
find game -type f -print0 | sort -z | xargs -0 sha256sum > manifest.sha256
echo "corrupt" >> game/index.html
if sha256sum -c manifest.sha256 >/dev/null 2>&1; then echo "[ops] expected corruption not detected"; exit 1; fi
cp -R "$ROOT/game" "$TMP/game"
sha256sum -c manifest.sha256
echo "[ops] rehearsal ok"
