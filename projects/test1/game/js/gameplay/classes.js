// classes.js - 三职业数值与技能表（纯数据+纯函数，无副作用）
export const CLASSES = {
  warrior: {
    id: 'warrior', name: '剑士', role: '近战坦',
    base: { hp: 120, mp: 40, atk: 12, def: 8, crit: 0.05, moveSpeed: 180 },
    attack: { type: 'melee', combo: 3, range: 48, frame: 12 },
    skills: [
      { id: 'whirlwind', name: '旋风斩', mp: 12, cd: 6, mult: 1.8, radius: 72 },
      { id: 'shieldCharge', name: '盾冲', mp: 10, cd: 8, mult: 1.4, dash: 160 }
    ],
    soloFriendly: 'high'
  },
  mage: {
    id: 'mage', name: '法师', role: '远程爆发',
    base: { hp: 80, mp: 100, atk: 16, def: 4, crit: 0.08, moveSpeed: 170 },
    attack: { type: 'projectile', range: 320, speed: 420, frame: 14 },
    skills: [
      { id: 'firewall', name: '火墙', mp: 20, cd: 9, mult: 0.6, duration: 4, tick: 0.5 },
      { id: 'frostRing', name: '冰环', mp: 18, cd: 7, mult: 1.2, radius: 96, slow: 0.4 }
    ],
    soloFriendly: 'medium'
  },
  ranger: {
    id: 'ranger', name: '游侠', role: '灵活持续',
    base: { hp: 95, mp: 60, atk: 13, def: 5, crit: 0.12, moveSpeed: 200 },
    attack: { type: 'projectile', range: 360, speed: 520, frame: 10 },
    skills: [
      { id: 'backstepShot', name: '后跳射击', mp: 8, cd: 5, mult: 1.3, dash: -120 },
      { id: 'arrowRain', name: '箭雨', mp: 22, cd: 10, mult: 0.5, duration: 3, tick: 0.4, radius: 120 }
    ],
    soloFriendly: 'medium'
  }
};

export function getClass(id) {
  const c = CLASSES[id];
  if (!c) throw new Error('unknown class: ' + id);
  return c;
}

export function listClasses() {
  return Object.values(CLASSES).map(c => ({ id: c.id, name: c.name, role: c.role, soloFriendly: c.soloFriendly }));
}

// Integration metadata: loaded and exercised by tests/integration.mjs.
export const extension = { id: "gameplay-classes", version: 1, actions: ["listClasses"], smoke: { action: "listClasses", args: [], expectType: "object" } };
