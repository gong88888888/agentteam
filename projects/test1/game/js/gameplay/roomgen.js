// 房间生成与不变量校验（纯逻辑，种子可复现）
export const ROOM_TYPES = ['combat', 'platform', 'treasure', 'shop', 'campfire', 'event', 'elite', 'boss'];

// 简单可复现 PRNG（mulberry32）
export function makeRng(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 生成一层房间图：8-12 房间 + 1 Boss 房
export function generateFloor(seedOrOptions) {
  const options = typeof seedOrOptions === "object" && seedOrOptions !== null
    ? seedOrOptions : { seed: seedOrOptions };
  const seed = options.seed;
  if (!Number.isInteger(seed) || seed < 0) throw new Error("seed must be a non-negative integer");
  const rng = makeRng(seed);
  const count = 8 + Math.floor(rng() * 5); // 8..12
  const rooms = [];
  for (let i = 0; i < count; i++) {
    rooms.push({ id: i, type: 'combat', doors: [] });
  }
  // 主路径：0..count-1 线性连通
  for (let i = 0; i < count - 1; i++) {
    rooms[i].doors.push(i + 1);
    rooms[i + 1].doors.push(i);
  }
  // 固定 1 篝火 1 商店
  rooms[1].type = 'campfire';
  rooms[2].type = 'shop';
  // 宝箱房 2-4
  const treasureCount = 2 + Math.floor(rng() * 3);
  let placed = 0;
  for (let i = 3; i < count - 1 && placed < treasureCount; i++) {
    if (rooms[i].type === 'combat') { rooms[i].type = 'treasure'; placed++; }
  }
  // 精英房概率 60%
  if (rng() < 0.6) {
    for (let i = 3; i < count - 1; i++) {
      if (rooms[i].type === 'combat') { rooms[i].type = 'elite'; break; }
    }
  }
  // Boss 房
  rooms.push({ id: count, type: 'boss', doors: [count - 1] });
  rooms[count - 1].doors.push(count);
  const floor = { seed, rooms, entrance: 0, boss: count, bossId: count };
  validateFloor(floor);
  return floor;
}

export function restoreFloor({ seed, explored = [] } = {}) {
  const floor = generateFloor({ seed });
  return { ...floor, explored: [...explored] };
}

// 不变量校验：主路径连通、1 篝火 1 商店、钥匙门<=1、Boss 可达
export function validateFloor(floor) {
  const { rooms, bossId } = floor;
  const campfires = rooms.filter(r => r.type === 'campfire').length;
  const shops = rooms.filter(r => r.type === 'shop').length;
  if (campfires !== 1) throw new Error('floor must have exactly 1 campfire');
  if (shops !== 1) throw new Error('floor must have exactly 1 shop');
  // BFS 从入口 0 到 boss
  const seen = new Set([0]);
  const q = [0];
  while (q.length) {
    const cur = q.shift();
    for (const d of rooms[cur].doors) {
      if (!seen.has(d)) { seen.add(d); q.push(d); }
    }
  }
  if (!seen.has(bossId)) throw new Error('boss unreachable from entrance');
  return true;
}
