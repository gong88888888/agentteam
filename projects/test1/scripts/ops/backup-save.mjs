#!/usr/bin/env node
// 存档备份：复制存档目录到 artifacts/ops/backup/<timestamp>/，并生成清单。
// 用法：node scripts/ops/backup-save.mjs --out <dir> | --list
import { readdirSync, mkdirSync, cpSync, existsSync, statSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const args = process.argv.slice(2);
const outIdx = args.indexOf('--out');
const listMode = args.includes('--list');
const outRoot = outIdx >= 0 ? resolve(args[outIdx + 1]) : resolve('artifacts/ops/backup');
const saveRoot = process.env.MAZE_SAVE_ROOT ? resolve(process.env.MAZE_SAVE_ROOT) : null;

if (listMode) {
  if (!existsSync(outRoot)) {
    console.log('无备份目录');
    process.exit(0);
  }
  for (const name of readdirSync(outRoot).sort()) {
    const p = join(outRoot, name);
    if (statSync(p).isDirectory()) console.log(name);
  }
  process.exit(0);
}

if (!saveRoot) {
  console.error('未设置 MAZE_SAVE_ROOT，拒绝猜测存档路径');
  process.exit(2);
}
if (!existsSync(saveRoot)) {
  console.error(`存档目录不存在: ${saveRoot}`);
  process.exit(2);
}

const ts = new Date().toISOString().replace(/[:.]/g, '-');
const dest = join(outRoot, ts);
mkdirSync(dest, { recursive: true });
cpSync(saveRoot, dest, { recursive: true });

const manifest = { timestamp: ts, source: saveRoot, dest, files: [] };
for (const name of readdirSync(dest)) {
  const p = join(dest, name);
  if (statSync(p).isFile()) manifest.files.push(name);
}
writeFileSync(join(dest, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`备份完成: ${dest}`);
