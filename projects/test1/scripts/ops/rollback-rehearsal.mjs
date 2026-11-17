#!/usr/bin/env node
// 回滚演练：在临时目录模拟发布与回滚，验证指针切换与入口存在，不触碰真实 releases/ 与存档。
// 用法：node scripts/ops/rollback-rehearsal.mjs
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const tmp = mkdtempSync(join(tmpdir(), 'maze-rehearsal-'));
const vA = join(tmp, 'releases', 'vA');
const vB = join(tmp, 'releases', 'vB');
mkdirSync(vA, { recursive: true });
mkdirSync(vB, { recursive: true });
writeFileSync(join(vA, 'index.html'), '<html>A</html>');
writeFileSync(join(vB, 'index.html'), '<html>B</html>');

const currentFile = join(tmp, 'current');
writeFileSync(currentFile, vA + '\n');

// 发布到 vB
writeFileSync(currentFile, vB + '\n');
if (readFileSync(currentFile, 'utf8').trim() !== vB) {
  console.error('[FAIL] 发布后指针错误');
  rmSync(tmp, { recursive: true, force: true });
  process.exit(1);
}

// 回滚到 vA
writeFileSync(currentFile, vA + '\n');
const cur = readFileSync(currentFile, 'utf8').trim();
if (cur !== vA) {
  console.error('[FAIL] 回滚后指针错误');
  rmSync(tmp, { recursive: true, force: true });
  process.exit(1);
}
if (!existsSync(join(cur, 'index.html'))) {
  console.error('[FAIL] 回滚后入口缺失');
  rmSync(tmp, { recursive: true, force: true });
  process.exit(1);
}

rmSync(tmp, { recursive: true, force: true });
console.log('rollback-rehearsal: PASS');
