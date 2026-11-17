// QA: 掉落品质权重、Boss 保底、独立分桶
import { test } from 'node:test';
import assert from 'node:assert/strict';

const CANDIDATES = [
  '../js/gameplay/loot.js',
  '../js/gameplay/loot.mjs',
  '../js/gameplay/drop.js',
];

async function loadLoot() {
  for (const p of CANDIDATES) {
    try { return await import(p); } catch { /* next */ }
  }
  return null;
}

const mod = await loadLoot();
const skip = mod ? false : 'gameplay loot module not found (see open_questions)';

const WEIGHTS = { white: 40, green: 30, blue: 20, purple: 8, orange: 2 };

function rollFn(m) {
  return m.rollQuality || m.rollDrop || m.rollLoot || null;
}

test('L-01 品质权重分布（大样本容差）', { skip }, () => {
  const roll = rollFn(mod);
  assert.ok(typeof roll === 'function', 'roll function missing');
  const N = 20000;
  const cnt = { white: 0, green: 0, blue: 0, purple: 0, orange: 0 };
  for (let i = 0; i < N; i++) cnt[roll({ boss: false })]++;
  for (const k of Object.keys(WEIGHTS)) {
    const p = cnt[k] / N;
    const e = WEIGHTS[k] / 100;
    assert.ok(Math.abs(p - e) < 0.02, `${k} got ${p.toFixed(3)} expect ${e}`);
  }
});

test('L-02 Boss 保底蓝', { skip }, () => {
  const roll = rollFn(mod);
  const order = ['white', 'green', 'blue', 'purple', 'orange'];
  for (let i = 0; i < 2000; i++) {
    const q = roll({ boss: true });
    assert.ok(order.indexOf(q) >= order.indexOf('blue'), `boss dropped ${q}`);
  }
});

test('L-03 Boss 紫/橙概率', { skip }, () => {
  const roll = rollFn(mod);
  const N = 20000;
  let purple = 0, orange = 0;
  for (let i = 0; i < N; i++) {
    const q = roll({ boss: true });
    if (q === 'purple') purple++;
    if (q === 'orange') orange++;
  }
  assert.ok(Math.abs(purple / N - 0.20) < 0.03, `purple ${purple / N}`);
  assert.ok(Math.abs(orange / N - 0.05) < 0.02, `orange ${orange / N}`);
});

test('L-04 装备独立分桶（按玩家 id 哈希）', { skip }, () => {
  const fn = mod.bucketForPlayer || mod.playerBucket || null;
  assert.ok(typeof fn === 'function', 'bucket function missing');
  const a = fn('p1');
  const b = fn('p2');
  assert.notEqual(a, b);
  assert.equal(fn('p1'), a, 'bucket must be deterministic');
});

test('L-05 金币材料共享', { skip }, () => {
  const fn = mod.isSharedDrop || mod.sharedDrop || null;
  assert.ok(typeof fn === 'function', 'shared drop fn missing');
  assert.equal(fn('gold'), true);
  assert.equal(fn('material'), true);
  assert.equal(fn('equipment'), false);
});
