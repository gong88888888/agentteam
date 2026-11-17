// 确定性战斗 tick 与伤害管线（纯逻辑，无 DOM）
// 契约来源：docs/architecture/architecture.md 战斗契约
export const TICK_HZ = 60;
export const TICK_MS = 1000 / TICK_HZ;

// 多人缩放查表（单人基准=1.0）
export const MULTIPLAYER_SCALE = {
  1: { hp: 1.0, dmg: 1.0, gold: 1.0 },
  2: { hp: 1.6, dmg: 1.15, gold: 1.25 },
  3: { hp: 2.1, dmg: 1.25, gold: 1.45 },
  4: { hp: 2.6, dmg: 1.35, gold: 1.65 },
};
export const BOSS_EXTRA_HP = 0.1;

export function getScale(playerCount, isBoss = false) {
  const n = Math.max(1, Math.min(4, playerCount | 0));
  const base = MULTIPLAYER_SCALE[n];
  return {
    hp: base.hp * (isBoss ? 1 + BOSS_EXTRA_HP : 1),
    dmg: base.dmg,
    gold: base.gold,
  };
}

// 固定步长累加器：把真实 dt 切成整数 tick，保证确定性
export class FixedStepClock {
  constructor(hz = TICK_HZ) {
    this.stepMs = 1000 / hz;
    this.acc = 0;
    this.tick = 0;
  }
  // 返回本次应执行的 tick 数
  advance(dtMs) {
    if (!Number.isFinite(dtMs) || dtMs < 0) throw new Error('dtMs must be >= 0');
    this.acc += dtMs;
    let n = 0;
    while (this.acc >= this.stepMs) {
      this.acc -= this.stepMs;
      this.tick++;
      n++;
    }
    return n;
  }
}

// 伤害管线：顺序固定，便于复现与测试
// 1 基础攻击 2 词条加成 3 暴击 4 防御减免 5 多人缩放
export function computeDamageDetailed({
  baseAttack,
  flatBonus = 0,
  percentBonus = 0,
  critChance = 0,
  critMultiplier = 1.5,
  defense = 0,
  playerCount = 1,
  isBoss = false,
  rng = Math.random,
}) {
  if (!Number.isFinite(baseAttack) || baseAttack < 0) throw new Error('baseAttack invalid');
  let dmg = baseAttack + flatBonus;
  dmg *= 1 + percentBonus;
  const crit = rng() < critChance;
  if (crit) dmg *= critMultiplier;
  // 防御减免：递减公式，防御>=100 时最多减 50%
  const reduction = defense / (defense + 100);
  dmg *= 1 - reduction;
  dmg *= getScale(playerCount, isBoss).dmg;
  return { damage: Math.max(1, Math.round(dmg)), crit };
}

// 受击顿帧与闪白时长（毫秒），供表现层读取
export const HIT_FEEL = { hitStopMs: 80, flashMs: 120, shakeMs: 100 };

// QA/public API aliases: keep the pure functions above and expose stable names.
export const scaleForPlayers = (n) => getScale(n, false);
export const bossHpMultiplier = (n) => getScale(n, true).hp;

export function tick(input) {
  const actions = (input && input.actions) || [];
  return {
    dt: input && input.dt ? input.dt : 0,
    events: actions.map((a, i) => ({ seq: i, type: a.type, power: a.power })),
  };
}

// Flat damage pipeline used by QA and gameplay: base + affix, crit, defense, co-op scale.
export function computeDamage({ base = 0, affix = 0, crit = false, critMul = 2, defense = 0, players = 1 } = {}) {
  const before = (Number(base) + Number(affix)) * (crit ? Number(critMul) : 1);
  return before * (1 - Number(defense)) * getScale(players, false).dmg;
}
