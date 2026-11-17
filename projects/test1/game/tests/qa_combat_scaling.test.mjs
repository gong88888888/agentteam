// QA: 战斗缩放与确定性 tick 不变量
// 不修改基座测试；模块未就绪时显式 skip。
import { test } from 'node:test';
import assert from 'node:assert/strict';

const CANDIDATES = [
  '../js/gameplay/combat.js',
  '../js/gameplay/combat.mjs',
  '../js/gameplay/battle.js',
];

async function loadCombat() {
  for (const p of CANDIDATES) {
    try { return await import(p); } catch { /* try next */ }
  }
  return null;
}

const mod = await loadCombat();
const skip = mod ? false : 'gameplay combat module not found (see open_questions)';

// 期望缩放表（产品基准）
const TABLE = {
  1: { hp: 1.0, dmg: 1.0, gold: 1.0 },
  2: { hp: 1.6, dmg: 1.15, gold: 1.25 },
  3: { hp: 2.1, dmg: 1.25, gold: 1.45 },
  4: { hp: 2.6, dmg: 1.35, gold: 1.65 },
};

function pickScaleFn(m) {
  return m.scaleForPlayers || m.getMultiplayerScale || m.multiplayerScale || null;
}

for (const n of [1, 2, 3, 4]) {
  test(`C-0${n} ${n}人缩放查表`, { skip }, () => {
    const fn = pickScaleFn(mod);
    assert.ok(typeof fn === 'function', 'scale function missing');
    const s = fn(n);
    const e = TABLE[n];
    assert.equal(s.hp, e.hp);
    assert.equal(s.dmg, e.dmg);
    assert.equal(s.gold, e.gold);
  });
}

test('C-05 Boss 额外 +10% 血量', { skip }, () => {
  const fn = mod.bossHpMultiplier || mod.getBossHpMultiplier;
  assert.ok(typeof fn === 'function', 'boss hp multiplier missing');
  assert.equal(fn(1), 1.1);
  assert.equal(fn(2), 1.6 * 1.1);
});

test('C-06 固定步长确定性', { skip }, () => {
  const tick = mod.tick || mod.step;
  assert.ok(typeof tick === 'function', 'tick missing');
  const input = { dt: 1, actions: [{ type: 'attack', power: 10 }] };
  const a = tick(structuredClone(input));
  const b = tick(structuredClone(input));
  assert.deepEqual(a, b);
});

test('C-07 伤害管线顺序', { skip }, () => {
  const fn = mod.computeDamage || mod.damagePipeline;
  assert.ok(typeof fn === 'function', 'damage pipeline missing');
  // 基础10, 词条+5, 暴击x2, 防御减免50%, 2人缩放1.15
  const d = fn({ base: 10, affix: 5, crit: true, critMul: 2, defense: 0.5, players: 2 });
  // (10+5)*2*0.5*1.15 = 17.25
  assert.ok(Math.abs(d - 17.25) < 1e-6, `got ${d}`);
});
