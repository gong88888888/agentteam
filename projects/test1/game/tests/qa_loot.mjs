// QA: 装备/掉落/强化契约测试（S3）。
import test from 'node:test';
import assert from 'node:assert/strict';

let items = null, loot = null;
try { items = await import('../js/gameplay/items.js'); } catch { items = null; }
try { loot = await import('../js/gameplay/loot.js'); } catch { loot = null; }
const hasItems = items && typeof items.generateItem === 'function';
const hasLoot = loot && typeof loot.rollQuality === 'function';

test('items/loot 模块存在', () => {
  assert.ok(hasItems, 'game/js/gameplay/items.js 缺失或未导出 generateItem');
  assert.ok(hasLoot, 'game/js/gameplay/loot.js 缺失或未导出 rollQuality');
});

test('装备 5 部位、2-4 词条', { skip: !hasItems }, () => {
  const slots = new Set();
  for (let i = 0; i < 200; i++) {
    const it = items.generateItem({ seed: i, slot: null, quality: 'blue' });
    slots.add(it.slot);
    assert.ok(it.affixes.length >= 2 && it.affixes.length <= 4, `词条数=${it.affixes.length}`);
  }
  for (const s of ['weapon', 'helmet', 'armor', 'boots', 'accessory']) {
    assert.ok(slots.has(s), `未生成部位 ${s}`);
  }
});

test('品质权重近似 白40/绿30/蓝20/紫8/橙2', { skip: !hasLoot }, () => {
  const counts = { white: 0, green: 0, blue: 0, purple: 0, orange: 0 };
  const N = 20000;
  for (let i = 0; i < N; i++) {
    const q = loot.rollQuality({ seed: i });
    counts[q] = (counts[q] || 0) + 1;
  }
  const pct = (k) => counts[k] / N;
  assert.ok(Math.abs(pct('white') - 0.40) < 0.03, `white=${pct('white')}`);
  assert.ok(Math.abs(pct('green') - 0.30) < 0.03, `green=${pct('green')}`);
  assert.ok(Math.abs(pct('blue') - 0.20) < 0.03, `blue=${pct('blue')}`);
  assert.ok(Math.abs(pct('purple') - 0.08) < 0.02, `purple=${pct('purple')}`);
  assert.ok(Math.abs(pct('orange') - 0.02) < 0.01, `orange=${pct('orange')}`);
});

test('Boss 保底蓝：Boss 掉落品质不低于 blue', { skip: !hasLoot || typeof loot.rollBossDrop !== 'function' }, () => {
  const order = { white: 0, green: 1, blue: 2, purple: 3, orange: 4 };
  for (let i = 0; i < 500; i++) {
    const q = loot.rollBossDrop({ seed: i });
    assert.ok(order[q] >= order.blue, `Boss 掉落 ${q} 低于蓝`);
  }
});

test('强化 +1~+9 失败不掉级', { skip: !hasItems || typeof items.enhance !== 'function' }, () => {
  let it = { enhanceLevel: 5 };
  for (let i = 0; i < 100; i++) {
    const r = items.enhance(it, { rng: () => 0.99 });
    it = r.item;
    assert.ok(it.enhanceLevel >= 5, '强化失败掉级');
    assert.ok(it.enhanceLevel <= 9);
  }
});
