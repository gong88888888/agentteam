#!/usr/bin/env bash
# 存档备份：导出 + 双份 + CRC 校验（占位，键名待集成确认）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/artifacts/ops/saves"
TS="$(date +%Y%m%d-%H%M%S)"
SLOT="${1:-slot1}"

mkdir -p "$OUT"
SRC="$OUT/$SLOT-$TS.json"

# 占位：实际导出需从浏览器 localStorage/IndexedDB 读取 SaveEnvelope。
# 集成后替换为真实导出命令；此处不伪造存档内容。
if [ ! -f "$SRC" ]; then
  echo "[ops] WARN: 未找到导出源 $SRC，请先由集成层导出存档" >&2
  echo "[ops] 备份流程已就绪，等待真实存档文件" >&2
  exit 0
fi

cp "$SRC" "$SRC.bak"
if command -v cksum >/dev/null 2>&1; then
  cksum "$SRC" > "$SRC.crc"
  cksum "$SRC.bak" >> "$SRC.crc"
  echo "[ops] 双备份完成: $SRC / $SRC.bak"
else
  echo "[ops] WARN: 无 cksum，跳过 CRC" >&2
fi
