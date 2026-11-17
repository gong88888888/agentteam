#!/usr/bin/env bash
# 校验快照完整性：逐文件比对 manifest.sha256
set -euo pipefail
DIR="${1:?usage: verify.sh <release-dir>}"
cd "$DIR"
if [ ! -f manifest.sha256 ]; then echo "[ops] missing manifest.sha256"; exit 1; fi
sha256sum -c manifest.sha256
echo "[ops] verify ok"
