#!/usr/bin/env node
// 发布：切换 current 指针到新版本目录。
// 用法：node scripts/ops/promote.mjs --to <versionDir>
import { existsSync, writeFileSync, readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';

const args = process.argv.slice(2);
const toIdx = args.indexOf('--to');
if (toIdx < 0) {
  console.error('用法: node scripts/ops/promote.mjs --to <versionDir>');
  process.exit(2);
}
const target = resolve(args[toIdx + 1]);
if (!existsSync(join(target, 'index.html'))) {
  console.error(`目标版本缺少 index.html: ${target}`);
  process.exit(2);
}

const currentFile = resolve('current');
const prev = existsSync(currentFile) ? readFileSync(currentFile, 'utf8').trim() : '(none)';
writeFileSync(currentFile, target + '\n');
console.log(`发布: ${prev} -> ${target}`);
