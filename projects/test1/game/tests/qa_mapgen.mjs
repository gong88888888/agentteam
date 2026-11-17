// QA: 房间生成契约测试（S1）。断言 arch ADR-003 不变量。
// 若 game/js/gameplay/mapgen.js 未落盘，测试显式失败以暴露缺口，不掩盖。
import test from 'node:test';
import assert from 'node:assert/strict';

let mapgen = null;
try {
  mapgen = await import('../js/gameplay/mapgen.js');
} catch (e) {
  mapgen = null;
}

const hasGen = mapgen && typeof mapgen.generateFloor === 'function';

test('mapgen 模块存在且导出 generateFloor', () => {
  assert.ok(hasGen, 'game/js/gameplay/mapgen.js 缺失或未导出 generateFloor（集成缺口）');
});

test('同 seed + 同层号 → 房间图确定性一致', { skip: !hasGen }, () => {
  const a = mapgen.generateFloor({ seed: 12345, floorIndex: 1, chapter: 1 });
  const b = mapgen.generateFloor({ seed: 12345, floorIndex: 1, chapter: 1 });
  assert.deepEqual(a, b);
});

test('房间数 ∈ [8,12] 且存在 1 个 Boss 房', { skip: !hasGen }, () => {
  for (const seed of [1, 2, 3, 99, 12345]) {
    const f = mapgen.generateFloor({ seed, floorIndex: 1, chapter: 1 });
    const nonBoss = f.rooms.filter((r) => r.type !== 'boss');
    assert.ok(nonBoss.length >= 8 && nonBoss.length <= 12, `seed=${seed} 房间数=${nonBoss.length}`);
    assert.equal(f.rooms.filter((r) => r.type === 'boss').length, 1);
    assert.ok(f.bossRoomId);
  }
});

test('入口到 Boss 主路径连通', { skip: !hasGen }, () => {
  const f = mapgen.generateFloor({ seed: 7, floorIndex: 1, chapter: 1 });
  assert.ok(Array.isArray(f.mainPath) && f.mainPath.length >= 2);
  assert.equal(f.mainPath[f.mainPath.length - 1], f.bossRoomId);
  const ids = new Set(f.rooms.map((r) => r.id));
  for (const id of f.mainPath) assert.ok(ids.has(id), `主路径含未知房间 ${id}`);
});

test('每层恰好 1 篝火、1 商店', { skip: !hasGen }, () => {
  for (const seed of [1, 2, 3, 99, 12345]) {
    const f = mapgen.generateFloor({ seed, floorIndex: 1, chapter: 1 });
    assert.equal(f.rooms.filter((r) => r.type === 'campfire').length, 1, `seed=${seed}`);
    assert.equal(f.rooms.filter((r) => r.type === 'shop').length, 1, `seed=${seed}`);
  }
});

test('宝箱房 ∈ [2,4]', { skip: !hasGen }, () => {
  for (const seed of [1, 2, 3, 99, 12345]) {
    const f = mapgen.generateFloor({ seed, floorIndex: 1, chapter: 1 });
    const n = f.rooms.filter((r) => r.type === 'treasure').length;
    assert.ok(n >= 2 && n <= 4, `seed=${seed} 宝箱房=${n}`);
  }
});

test('钥匙门 ≤1 且无钥匙时主路径仍可达 Boss', { skip: !hasGen }, () => {
  for (const seed of [1, 2, 3, 99, 12345]) {
    const f = mapgen.generateFloor({ seed, floorIndex: 1, chapter: 1 });
    const keyDoors = f.rooms.filter((r) => r.locked).length;
    assert.ok(keyDoors <= 1, `seed=${seed} 钥匙门=${keyDoors}`);
    if (f.keyDoor) {
      assert.ok(!f.mainPath.includes(f.keyDoor.roomId), '钥匙门不应锁主路径');
    }
  }
});
