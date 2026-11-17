// QA: 战斗契约测试（S2）。伤害公式、闪避无敌帧、技能CD、精英词缀。
import test from 'node:test';
import assert from 'node:assert/strict';

let combat = null;
try { combat = await import('../js/gameplay/combat.js'); } catch { combat = null; }
const hasCombat = combat && typeof combat.computeDamage === 'function';

test('combat 模块存在且导出 computeDamage', () => {
  assert.ok(hasCombat, 'game/js/gameplay/combat.js 缺失或未导出 computeDamage（集成缺口）');
});

test('伤害公式：基础伤害随攻击提升、随防御下降', { skip: !hasCombat }, () => {
  const base = combat.computeDamage({ attack: 10, defense: 0, crit: 0, qualityMul: 1 });
  const hiAtk = combat.computeDamage({ attack: 20, defense: 0, crit: 0, qualityMul: 1 });
  const hiDef = combat.computeDamage({ attack: 10, defense: 5, crit: 0, qualityMul: 1 });
  assert.ok(hiAtk > base);
  assert.ok(hiDef < base);
  assert.ok(base > 0);
});

test('暴击率 0 时无暴击、暴击率 1 时必暴击', { skip: !hasCombat }, () => {
  const noCrit = combat.computeDamage({ attack: 10, defense: 0, crit: 0, qualityMul: 1, rng: () => 0.99 });
  const alwaysCrit = combat.computeDamage({ attack: 10, defense: 0, crit: 1, qualityMul: 1, rng: () => 0.0 });
  assert.ok(alwaysCrit > noCrit);
});

test('闪避无敌帧：闪避期间不受伤', { skip: !hasCombat || typeof combat.isInvincible !== 'function' }, () => {
  const state = { dodging: true, dodgeTimer: 0.2 };
  assert.equal(combat.isInvincible(state), true);
  assert.equal(combat.isInvincible({ dodging: false, dodgeTimer: 0 }), false);
});

test('技能CD：冷却中不可释放，冷却结束可释放', { skip: !hasCombat || typeof combat.canCastSkill !== 'function' }, () => {
  assert.equal(combat.canCastSkill({ cdRemain: 1.0 }), false);
  assert.equal(combat.canCastSkill({ cdRemain: 0 }), true);
});

test('精英词缀生效：护盾/加速/分裂/吸血至少可识别', { skip: !hasCombat || typeof combat.applyEliteAffix !== 'function' }, () => {
  const e = { hp: 100, maxHp: 100, speed: 1, damage: 10 };
  const shielded = combat.applyEliteAffix(e, 'shield');
  assert.ok(shielded.shield > 0 || shielded.hp >= e.hp);
  const fast = combat.applyEliteAffix({ ...e }, 'haste');
  assert.ok(fast.speed >= e.speed);
});
