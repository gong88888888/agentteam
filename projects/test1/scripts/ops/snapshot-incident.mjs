#!/usr/bin/env node
// 保留现场：复制 current 指向的版本目录与日志到 incident 目录。
// 用法：node scripts/ops/snapshot-incident.mjs --out <dir>
import { existsSync, readFileSync, mkdirSync, cpSync } from 'node:fs';
import { resolve, join } from 'node:path';

const args = process.argv.slice(2);
const outIdx = args.indexOf('--out');
const outRoot = outIdx >= 0 ? resolve(args[outIdx + 1]) : resolve('artifacts/ops/incident');
const currentFile = resolve('current');

if (!existsSync(currentFile)) {
  console.error('current 指针不存在，无法保留现场');
  process.exit(2);
}
const current = readFileSync(currentFile, 'utf8').trim();
if (!existsSync(current)) {
  console.error(`current 指向的目录不存在: ${current}`);
  process.exit(2);
}

const ts = new Date().toISOString().replace(/[:.]/g, '-');
const dest = join(outRoot, ts);
mkdirSync(dest, { recursive: true });
cpSync(current, join(dest, 'version'), { recursive: true });
console.log(`现场已保留: ${dest}`);
