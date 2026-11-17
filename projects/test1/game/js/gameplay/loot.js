// 掉落系统：品质权重、Boss 保底、装备独立分桶（纯逻辑）
export const QUALITY = ['white', 'green', 'blue', 'purple', 'orange'];
export const QUALITY_WEIGHT = { white: 40, green: 30, blue: 20, purple: 8, orange: 2 };
export const BOSS_GUARANTEE = { minQuality: 'blue', purpleChance: 0.2, orangeChance: 0.05 };

function weightedPick(rng) {
  const total = Object.values(QUALITY_WEIGHT).reduce((a, b) => a + b, 0);
  let r = rng() * total;
  for (const q of QUALITY) {
    r -= QUALITY_WEIGHT[q];
    if (r < 0) return q;
  }
  return 'white';
}

// 普通掉落
export function rollQuality(rng = Math.random) {
  if (rng && typeof rng === "object") {
    if (rng.boss) return rollBossQuality(rng.rng || Math.random);
    rng = Math.random;
  }
  if (typeof rng !== "function") rng = Math.random;
  return weightedPick(rng);
}

// Boss 掉落：保底蓝，紫/橙按概率覆盖
export function rollBossQuality(rng = Math.random) {
  if (typeof rng !== "function") rng = Math.random;
  if (rng() < BOSS_GUARANTEE.orangeChance) return 'orange';
  if (rng() < BOSS_GUARANTEE.purpleChance) return 'purple';
  return BOSS_GUARANTEE.minQuality;
}

// 装备独立分桶：按玩家 id 稳定哈希，保证每人只看到自己的光柱
export function bucketForPlayer(playerId) {
  const s = String(playerId);
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) % 1000;
}

// 生成一次掉落事件；shared=true 表示金币/材料共享
export function rollDrop({ playerId, isBoss = false, rng = Math.random }) {
  const quality = isBoss ? rollBossQuality(rng) : rollQuality(rng);
  return {
    playerId,
    bucket: bucketForPlayer(playerId),
    quality,
    shared: false,
  };
}

export function rollSharedDrop({ gold = 0, material = 0 }) {
  return { gold, material, shared: true };
}

// QA/public API aliases.
export function roll({ boss = false, rng = Math.random } = {}) {
  return boss ? rollBossQuality(rng) : rollQuality(rng);
}
export function isSharedDrop(kind) {
  return kind === "gold" || kind === "material";
}
