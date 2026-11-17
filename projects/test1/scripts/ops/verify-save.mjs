#!/usr/bin/env node
// 校验备份目录内 SaveEnvelope 的 CRC32（仅结构校验，不解析业务 payload）。
// 用法：node scripts/ops/verify-save.mjs --dir <backupDir>
import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const args = process.argv.slice(2);
const dirIdx = args.indexOf('--dir');
if (dirIdx < 0) {
  console.error('用法: node scripts/ops/verify-save.mjs --dir <backupDir>');
  process.exit(2);
}
const dir = resolve(args[dirIdx + 1]);
if (!existsSync(dir)) {
  console.error(`目录不存在: ${dir}`);
  process.exit(2);
}

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    c ^= buf[i];
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return (c ^ 0xffffffff) >>> 0;
}

let failed = false;
for (const name of readdirSync(dir)) {
  const p = join(dir, name);
  if (!statSync(p).isFile() || !name.endsWith('.json')) continue;
  try {
    const env = JSON.parse(readFileSync(p, 'utf8'));
    if (typeof env.version !== 'number' || typeof env.crc32 !== 'number' || typeof env.payload !== 'object') {
      console.error(`[FAIL] ${name} 结构不符 SaveEnvelope`);
      failed = true;
      continue;
    }
    const actual = crc32(Buffer.from(JSON.stringify(env.payload)));
    if (actual !== env.crc32) {
      console.error(`[FAIL] ${name} CRC 不匹配 expected=${env.crc32} actual=${actual}`);
      failed = true;
    } else {
      console.log(`[OK] ${name} version=${env.version}`);
    }
  } catch (e) {
    console.error(`[FAIL] ${name} 解析失败: ${e.message}`);
    failed = true;
  }
}

if (failed) {
  console.error('verify-save: BLOCKED');
  process.exit(1);
}
console.log('verify-save: PASS');
