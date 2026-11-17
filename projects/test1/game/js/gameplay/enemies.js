// enemies.js - 普通怪4类+精英词缀+Boss三阶段骨架+仇恨（纯逻辑）
import { computeDamage } from './combat.js';

export const ENEMY_TYPES = {
  charger: { id: 'charger', hp: 40, atk: 8, def: 2, speed: 120, behavior: 'charge' },
  thrower: { id: 'thrower', hp: 30, atk: 10, def: 1, speed: 80, behavior: 'ranged' },
  flyer: { id: 'flyer', hp: 25, atk: 7, def: 0, speed: 160, behavior: 'fly' },
  bomber: { id: 'bomber', hp: 20, atk: 14, def: 0, speed: 100, behavior: 'explode' }
};

export const ELITE_AFFIXES = ['shield', 'haste', 'split', 'lifesteal'];

export function createEnemy(typeId, { elite = false, affixes = [], x = 0, y = 0 } = {}) {
  const t = ENEMY_TYPES[typeId];
  if (!t) throw new Error('unknown enemy: ' + typeId);
  const hpMult = elite ? 2.2 : 1;
  return {
    id: typeId + '_' + Math.random().toString(36).slice(2, 8),
    type: typeId, elite, affixes: elite ? affixes.slice(0, 2) : [],
    x, y, hp: Math.round(t.hp * hpMult), maxHp: Math.round(t.hp * hpMult),
    atk: t.atk, def: t.def, speed: t.speed, behavior: t.behavior,
    phase: 1, state: 'patrol'
  };
}

export function createBoss({ x = 0, y = 0 } = {}) {
  return {
    id: 'boss', type: 'boss', elite: false, affixes: [],
    x, y, hp: 800, maxHp: 800, atk: 20, def: 10, speed: 90,
    phase: 1, state: 'idle', phases: [1, 2, 3]
  };
}

export function updateBossPhase(boss) {
  const r = boss.hp / boss.maxHp;
  boss.phase = r > 0.66 ? 1 : r > 0.33 ? 2 : 3;
  return boss.phase;
}

export function pickTarget(enemies, players) {
  // 仇恨：最近优先，其次伤害最高（简化：最近）
  let best = null, bestD = Infinity;
  for (const e of enemies) {
    for (const p of players) {
      const d = Math.abs(e.x - p.x) + Math.abs(e.y - p.y);
      if (d < bestD) { bestD = d; best = p; }
    }
  }
  return best;
}

export function enemyAttack(enemy, target, roll = 1) {
  return computeDamage({ atk: enemy.atk, mult: 1, def: target.def || 0, crit: 0, roll });
}
