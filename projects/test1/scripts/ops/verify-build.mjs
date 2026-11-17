#!/usr/bin/env node
// 校验发布目录完整性：入口、关键模块、基座文件哈希。
// 用法：node scripts/ops/verify-build.mjs [--root <dir>]
import { readFileSync, existsSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join, resolve } from 'node:path';

const args = process.argv.slice(2);
const rootIdx = args.indexOf('--root');
const root = rootIdx >= 0 ? resolve(args[rootIdx + 1]) : resolve('game');

const required = [
  'index.html',
  'js/core.js',
  'js/main.js',
  'tests/game_logic.test.mjs',
  'tests/smoke.mjs',
];

const optional = [
  'js/gameplay/events.js',
  'js/gameplay/maze.js',
  'js/gameplay/rooms.js',
  'js/gameplay/actors.js',
  'js/gameplay/skills.js',
  'js/gameplay/combat.js',
  'js/gameplay/loot.js',
  'js/gameplay/inventory.js',
  'js/gameplay/save.js',
  'js/gameplay/coop.js',
  'js/ui/theme.js',
  'js/ui/hud.js',
  'js/ui/menu.js',
  'js/ui/inventory-ui.js',
  'js/ui/minimap.js',
  'js/ui/overlay.js',
];

let failed = false;
for (const rel of required) {
  const p = join(root, rel);
  if (!existsSync(p) || !statSync(p).isFile()) {
    console.error(`[FAIL] 缺少必需文件: ${rel}`);
    failed = true;
  } else {
    const h = createHash('sha256').update(readFileSync(p)).digest('hex');
    console.log(`[OK] ${rel} sha256=${h}`);
  }
}

for (const rel of optional) {
  const p = join(root, rel);
  if (existsSync(p)) {
    const h = createHash('sha256').update(readFileSync(p)).digest('hex');
    console.log(`[OK] ${rel} sha256=${h}`);
  } else {
    console.log(`[SKIP] 可选文件缺失: ${rel}`);
  }
}

if (failed) {
  console.error('verify-build: BLOCKED');
  process.exit(1);
}
console.log('verify-build: PASS');
