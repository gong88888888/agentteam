// player.js - 玩家状态与输入意图→动作（纯逻辑，无副作用）
import { getClass } from './classes.js';
import { createCooldowns, tickCooldowns, canUseSkill, startCooldown, applyDodge, isInvulnerable } from './combat.js';

export function createPlayer({ id = 'p1', classId = 'warrior', x = 0, y = 0 } = {}) {
  const c = getClass(classId);
  return {
    id, classId,
    x, y, vx: 0, vy: 0, facing: 1,
    hp: c.base.hp, maxHp: c.base.hp,
    mp: c.base.mp, maxMp: c.base.mp,
    atk: c.base.atk, def: c.base.def, crit: c.base.crit, moveSpeed: c.base.moveSpeed,
    cooldowns: createCooldowns(),
    invulnUntil: 0,
    state: 'idle',
    potions: 3
  };
}

export function stepPlayer(p, intent, dtMs, nowMs) {
  tickCooldowns(p.cooldowns, dtMs);
  const dt = dtMs / 1000;
  if (intent.left) { p.vx = -p.moveSpeed; p.facing = -1; }
  else if (intent.right) { p.vx = p.moveSpeed; p.facing = 1; }
  else p.vx = 0;
  p.x += p.vx * dt;
  if (intent.jump && p.state !== 'air') { p.vy = -420; p.state = 'air'; }
  if (p.state === 'air') { p.vy += 1200 * dt; p.y += p.vy * dt; if (p.y >= 0) { p.y = 0; p.vy = 0; p.state = 'idle'; } }
  if (intent.dodge) applyDodge(p, nowMs);
  if (intent.potion && p.potions > 0) { p.potions--; p.hp = Math.min(p.maxHp, p.hp + Math.round(p.maxHp * 0.3)); }
  if (intent.skill) {
    const sk = getClass(p.classId).skills.find(s => s.id === intent.skill);
    if (sk && canUseSkill(p.cooldowns, sk.id) && p.mp >= sk.mp) {
      p.mp -= sk.mp;
      startCooldown(p.cooldowns, sk.id, sk.cd * 1000);
      p.state = 'skill';
    }
  }
  return p;
}

export function takeDamage(p, dmg, nowMs) {
  if (isInvulnerable(p, nowMs)) return { applied: 0, dead: false };
  p.hp = Math.max(0, p.hp - dmg);
  return { applied: dmg, dead: p.hp <= 0 };
}
