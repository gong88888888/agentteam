// QA: 双人/多人缩放契约测试（S5）。
import test from 'node:test';
import assert from 'node:assert/strict';

let coop = null;
try { coop = await import('../js/gameplay/coop.js'); } catch { coop = null; }
const hasCoop = coop && typeof coop.getScaling === 'function';

test('coop 模块存在且导出 getScaling', () => {
  assert.ok(hasCoop, 'game/js/gameplay/coop.js 缺失或未导出 getScaling');
});

test('2/3/4 人缩放系数符合产品口径', { skip: !hasCoop }, () => {
  const s2 = coop.getScaling(2);
  assert.equal(s2.hp, 1.6); assert.equal(s2.dmg, 1.15); assert.equal(s2.gold, 1.25);
  const s3 = coop.getScaling(3);
  assert.equal(s3.hp, 2.1); assert.equal(s3.dmg, 1.25); assert.equal(s3.gold, 1.45);
  const s4 = coop.getScaling(4);
  assert.equal(s4.hp, 2.6); assert.equal(s4.dmg, 1.35); assert.equal(s4.gold, 1.65);
});

test('Boss 额外 +10% 血量', { skip: !hasCoop || typeof coop.getBossScaling !== 'function' }, () => {
  const b = coop.getBossScaling(2);
  assert.ok(Math.abs(b.hp - 1.6 * 1.1) < 1e-6);
});

test('扶起 3 秒', { skip: !hasCoop || typeof coop.reviveTime !== 'number' }, () => {
  assert.equal(coop.reviveTime, 3);
});

test('掉队 3 秒传送', { skip: !hasCoop || typeof coop.teleportDelay !== 'number' }, () => {
  assert.equal(coop.teleportDelay, 3);
});
