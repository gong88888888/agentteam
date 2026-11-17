// QA: 存档契约测试（S4）。版本号、CRC、双备份、异常回退篝火。
import test from 'node:test';
import assert from 'node:assert/strict';

let save = null;
try { save = await import('../js/gameplay/save.js'); } catch { save = null; }
const hasSave = save && typeof save.serialize === 'function';

test('save 模块存在且导出 serialize/deserialize', () => {
  assert.ok(hasSave, 'game/js/gameplay/save.js 缺失或未导出 serialize');
  assert.ok(typeof save.deserialize === 'function');
});

test('序列化含版本号与 CRC', { skip: !hasSave }, () => {
  const data = { version: 1, worldSlot: 1, seed: 42, floorIndex: 1, player: { level: 1 }, inventory: [], gold: 0 };
  const s = save.serialize(data);
  assert.ok(s.version >= 1);
  assert.ok(typeof s.crc === 'string' || typeof s.crc === 'number');
});

test('往返序列化一致', { skip: !hasSave }, () => {
  const data = { version: 1, worldSlot: 1, seed: 42, floorIndex: 2, player: { level: 3 }, inventory: [{ id: 'x' }], gold: 100 };
  const s = save.serialize(data);
  const back = save.deserialize(s);
  assert.equal(back.seed, 42);
  assert.equal(back.gold, 100);
});

test('CRC 校验失败时回退到最近篝火', { skip: !hasSave || typeof save.loadWithFallback !== 'function' }, () => {
  const corrupted = { version: 1, seed: 42, crc: 'bad', lastCampfire: { floorIndex: 1, roomId: 'r1' } };
  const r = save.loadWithFallback(corrupted, { backup: null });
  assert.ok(r.fallback === true || r.roomId === 'r1');
});
