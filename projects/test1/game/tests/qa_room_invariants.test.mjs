// QA: 房间生成不变量
import { test } from 'node:test';
import assert from 'node:assert/strict';

const CANDIDATES = [
  '../js/gameplay/roomgen.js',
  '../js/gameplay/room.js',
  '../js/gameplay/maze.js',
];

async function loadRoom() {
  for (const p of CANDIDATES) {
    try { return await import(p); } catch { /* next */ }
  }
  return null;
}

const mod = await loadRoom();
const skip = mod ? false : 'gameplay roomgen module not found (see open_questions)';

function genFn(m) {
  return m.generateFloor || m.generateRoom || m.generate || null;
}

function reachable(rooms, from, to) {
  const seen = new Set([from]);
  const q = [from];
  while (q.length) {
    const cur = q.shift();
    if (cur === to) return true;
    for (const nb of rooms[cur]?.doors || []) {
      if (!seen.has(nb)) { seen.add(nb); q.push(nb); }
    }
  }
  return false;
}

test('R-01 主路径连通（入口→Boss）', { skip }, () => {
  const gen = genFn(mod);
  assert.ok(typeof gen === 'function', 'generate fn missing');
  for (let s = 1; s <= 20; s++) {
    const f = gen({ seed: s });
    assert.ok(reachable(f.rooms, f.entrance, f.boss), `seed ${s} not connected`);
  }
});

test('R-02 每层恰 1 篝火 1 商店', { skip }, () => {
  const gen = genFn(mod);
  for (let s = 1; s <= 20; s++) {
    const f = gen({ seed: s });
    const types = Object.values(f.rooms).map(r => r.type);
    assert.equal(types.filter(t => t === 'campfire').length, 1, `seed ${s} campfire`);
    assert.equal(types.filter(t => t === 'shop').length, 1, `seed ${s} shop`);
  }
});

test('R-03 钥匙门 ≤1 且钥匙可达', { skip }, () => {
  const gen = genFn(mod);
  for (let s = 1; s <= 20; s++) {
    const f = gen({ seed: s });
    const locked = Object.values(f.rooms).filter(r => r.locked);
    assert.ok(locked.length <= 1, `seed ${s} locked doors ${locked.length}`);
    if (locked.length === 1) {
      const keyRoom = Object.entries(f.rooms).find(([, r]) => r.hasKey)?.[0];
      assert.ok(keyRoom, `seed ${s} key missing`);
      assert.ok(reachable(f.rooms, f.entrance, keyRoom), `seed ${s} key unreachable`);
    }
  }
});

test('R-04 种子可复现', { skip }, () => {
  const gen = genFn(mod);
  const a = gen({ seed: 42 });
  const b = gen({ seed: 42 });
  assert.deepEqual(a.rooms, b.rooms);
});

test('R-05 种子+已探索可恢复', { skip }, () => {
  const gen = genFn(mod);
  const restore = mod.restoreFloor || mod.restore || null;
  assert.ok(typeof restore === 'function', 'restore fn missing');
  const f = gen({ seed: 7 });
  const explored = Object.keys(f.rooms).slice(0, 3);
  const r = restore({ seed: 7, explored });
  assert.deepEqual(r.rooms, f.rooms);
  assert.deepEqual(r.explored.sort(), explored.sort());
});

test('R-06 非法参数抛错', { skip }, () => {
  const gen = genFn(mod);
  assert.throws(() => gen({ seed: -1 }));
});
