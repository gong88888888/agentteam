// Combat contract used by gameplay and QA.
export function computeDamageBase(attacker = {}, defender = {}, opts = {}) {
  const rng = typeof opts.rng === "function" ? opts.rng : Math.random;
  const attack = Number(attacker.attack ?? attacker.baseAttack ?? 0);
  const defense = Number(defender.defense ?? 0);
  const crit = rng() < Number(attacker.critRate ?? 0);
  const raw = Math.max(1, attack - defense) * (crit ? Number(attacker.critMult ?? 2) : 1);
  return Math.max(1, Math.round(raw));
}

export function isInvincible(state, nowMs = 0) {
  if (!state) return false;
  if (state.dodging) return Number(state.dodgeTimer || 0) > 0;
  return Number(state.dodgeUntil || 0) > Number(nowMs);
}

export function checkDeath(actor, bus) {
  if (actor && actor.hp <= 0 && bus && typeof bus.emit === "function") {
    bus.emit("death", actor);
    return true;
  }
  return false;
}

export function stepRevive(state, dt) {
  if (!state || !state.downed) return state;
  if (state.reviverNear) state.reviveProgress = Math.min(3, (state.reviveProgress || 0) + dt);
  if (state.reviveProgress >= 3) state.downed = false;
  return state;
}

// QA-facing flexible overload and skill/affix helpers.
export function canCastSkill(state = {}) {
  return Number(state.cdRemain ?? state.cooldown ?? 0) <= 0;
}

export function applyEliteAffix(enemy, affix) {
  if (!enemy) return enemy;
  if (affix === "shield") return { ...enemy, shield: Math.round((enemy.maxHp || enemy.hp || 100) * 0.35) };
  if (affix === "haste") return { ...enemy, speed: (enemy.speed || 1) * 1.35 };
  if (affix === "vampiric") return { ...enemy, lifesteal: 0.15 };
  if (affix === "split") return { ...enemy, split: true };
  return { ...enemy };
}

// Accept both the engine signature (attacker, defender, opts) and QA's single object.
const _computeDamage = computeDamageBase;
export function computeDamage(input, defender, opts = {}) {
  if (defender && typeof defender === "object" && input && input.attack !== undefined) {
    return _computeDamage(input, defender, opts);
  }
  if (input && typeof input === "object") {
    const rng = typeof input.rng === "function" ? input.rng : Math.random;
    const attack = Number(input.attack ?? 0);
    const defense = Number(input.defense ?? 0);
    const critRate = Number(input.crit ?? input.critRate ?? 0);
    const crit = rng() < critRate;
    const raw = Math.max(1, attack - defense) * (crit ? 2 : 1) * Number(input.qualityMul || 1);
    return Math.max(1, Math.round(raw));
  }
  return 1;
}

export const isImmune = (state, now = 0) => isInvincible(state, now);
