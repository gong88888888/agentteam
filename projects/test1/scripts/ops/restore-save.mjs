#!/usr/bin/env node
// 存档恢复：从备份目录恢复存档，恢复前再次备份当前存档。
// 用法：node scripts/ops/restore-save.mjs --from <backupDir>
import { existsSync, cpSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const args = process.argv.slice(2);
const fromIdx = args.indexOf('--from');
if (fromIdx < 0) {
  console.error('用法: node scripts/ops/restore-save.mjs --from <backupDir>');
  process.exit(2);
}
const from = resolve(args[fromIdx + 1]);
const saveRoot = process.env.MAZE_SAVE_ROOT ? resolve(process.env.MAZE_SAVE_ROOT) : null;

if (!saveRoot) {
  console.error('未设置 MAZE_SAVE_ROOT，拒绝猜测存档路径');
  process.exit(2);
}
if (!existsSync(from)) {
  console.error(`备份目录不存在: ${from}`);
  process.exit(2);
}

// 恢复前再次备份当前存档
if (existsSync(saveRoot)) {
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  const pre = join('artifacts/ops/backup', `pre-restore-${ts}`);
  mkdirSync(pre, { recursive: true });
  cpSync(saveRoot, pre, { recursive: true });
  console.log(`恢复前备份: ${pre}`);
}

mkdirSync(saveRoot, { recursive: true });
cpSync(from, saveRoot, { recursive: true });
console.log(`恢复完成: ${from} -> ${saveRoot}`);
