// Pure game rules shared by the browser game and Node tests.
// Covers the MVP systems: chapter/floor/room generation, classes, skills,
// equipment/affixes, loot, scaling, inventory and save envelopes.

export const CLASSES = {
  swordsman: {
    id: "swordsman", name: "剑士", hp: 140, mp: 40, speed: 250, jump: 620,
    attack: 22, range: 76, color: "#3b82f6",
    skill: { id: "whirlwind", name: "旋风斩", mp: 18, cooldown: 5, damage: 34, radius: 120 },
    skill2: { id: "shieldrush", name: "盾冲", mp: 12, cooldown: 4, damage: 24, radius: 100 },
    passive: "受击减伤 10%",
  },
  mage: {
    id: "mage", name: "法师", hp: 90, mp: 90, speed: 220, jump: 600,
    attack: 26, range: 145, color: "#a855f7",
    skill: { id: "firewall", name: "火墙", mp: 30, cooldown: 7, damage: 42, radius: 230 },
    skill2: { id: "icering", name: "冰环", mp: 20, cooldown: 8, damage: 26, radius: 180 },
    passive: "技能伤害 +15%",
  },
  ranger: {
    id: "ranger", name: "游侠", hp: 105, mp: 60, speed: 285, jump: 660,
    attack: 18, range: 190, color: "#22c55e",
    skill: { id: "arrowrain", name: "箭雨", mp: 24, cooldown: 6, damage: 26, radius: 260 },
    skill2: { id: "backshot", name: "后跳射击", mp: 14, cooldown: 4, damage: 22, radius: 220 },
    passive: "移速 +8%",
  },
};

export const DIFFICULTIES = [
  { id: 1, name: "休闲", hp: 0.8, damage: 0.7, gold: 1.2, note: "更适合先体验完整流程" },
  { id: 2, name: "标准", hp: 1.0, damage: 1.0, gold: 1.0, note: "设计基准" },
  { id: 3, name: "挑战", hp: 1.35, damage: 1.3, gold: 0.9, note: "精英与 Boss 更凶" },
];

export const QUALITIES = [
  { id: "white", name: "白", weight: 40, color: "#e5e7eb", multiplier: 1 },
  { id: "green", name: "绿", weight: 30, color: "#22c55e", multiplier: 1.2 },
  { id: "blue", name: "蓝", weight: 20, color: "#3b82f6", multiplier: 1.5 },
  { id: "purple", name: "紫", weight: 8, color: "#a855f7", multiplier: 2.2 },
  { id: "orange", name: "橙", weight: 2, color: "#f97316", multiplier: 3.5 },
];

export const SLOTS = [
  { id: "weapon", name: "武器" },
  { id: "helmet", name: "头盔" },
  { id: "armor", name: "衣服" },
  { id: "boots", name: "鞋子" },
  { id: "accessory", name: "饰品" },
];

export const AFFIXES = [
  { id: "attack", name: "攻击", min: 2, max: 9 },
  { id: "hp", name: "生命", min: 8, max: 28 },
  { id: "defense", name: "防御", min: 1, max: 6 },
  { id: "speed", name: "移速", min: 3, max: 12 },
  { id: "crit", name: "暴击", min: 1, max: 5 },
];

export const ROOM_TYPES = [
  "combat", "platform", "treasure", "shop", "campfire", "event", "elite", "boss",
];
export const ROOM_LABEL = {
  combat: "战斗房", platform: "跳台房", treasure: "宝箱房", shop: "商店房",
  campfire: "篝火房", event: "事件房", elite: "精英房", boss: "Boss 房",
};
export const FLOOR_NAMES = ["蘑菇林", "废弃矿洞", "古代遗迹", "藤蔓深井", "蘑菇王庭"];

const ENEMY_ARCHETYPES = [
  { id: "melee", name: "蘑菇怪", hp: 42, damage: 7, speed: 58, color: "#ef4444" },
  { id: "archer", name: "投掷怪", hp: 34, damage: 6, speed: 46, color: "#f97316" },
  { id: "bomber", name: "自爆怪", hp: 28, damage: 14, speed: 72, color: "#eab308" },
  { id: "flyer", name: "飞行怪", hp: 30, damage: 6, speed: 78, color: "#38bdf8" },
];
const ELITE_AFFIXES = [
  { id: "shield", name: "护盾", defense: 0.25 },
  { id: "haste", name: "加速", speed: 1.3 },
  { id: "vampiric", name: "吸血", lifesteal: 0.15 },
  { id: "split", name: "分裂", split: true },
];

const MONSTER_NAMES = [
  "蘑菇怪", "藤蔓怪", "矿洞蝙蝠", "遗迹守卫", "孢子射手", "岩石投手",
  "爆裂菇", "自爆甲虫", "风灵", "毒翼", "矿工幽灵", "刺壳兽",
  "腐化树精", "水晶蜘蛛", "火元素", "冰元素", "沙虫", "暗影刺客",
  "铁甲卫士", "古代傀儡",
];

const ITEM_NAMES = [
  "蘑菇短剑", "藤蔓护符", "矿洞头盔", "遗迹胸甲", "篝火披风", "探险家手套",
  "Boss 徽记", "精灵长弓", "法师法典", "旧城战靴", "苔藓戒指", "守卫者项链",
];

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function chapterSeed(value) {
  return (Number(value) >>> 0) || 20261117;
}

export function pick(rand, list) {
  return list[Math.floor(rand() * list.length) % list.length];
}

export function multiplayerScale(players, boss = false) {
  const n = Math.max(1, Math.min(4, Number(players) | 0));
  const table = {
    1: { hp: 1, damage: 1, gold: 1 },
    2: { hp: 1.6, damage: 1.15, gold: 1.25 },
    3: { hp: 2.1, damage: 1.25, gold: 1.45 },
    4: { hp: 2.6, damage: 1.35, gold: 1.65 },
  };
  const base = table[n];
  return {
    hp: base.hp * (boss ? 1.1 : 1),
    damage: base.damage,
    gold: base.gold,
  };
}

export function rollQuality(rand, boss = false) {
  if (boss) {
    if (rand() < 0.05) return "orange";
    if (rand() < 0.2) return "purple";
    return "blue";
  }
  const total = QUALITIES.reduce((sum, q) => sum + q.weight, 0);
  let roll = rand() * total;
  for (const q of QUALITIES) {
    roll -= q.weight;
    if (roll <= 0) return q.id;
  }
  return "white";
}

export function qualityOf(id) {
  return QUALITIES.find((q) => q.id === id) || QUALITIES[0];
}

export function makeItem(rand, floor = 1, qualityId = null, boss = false) {
  const quality = qualityId || rollQuality(rand, boss);
  const slot = pick(rand, SLOTS);
  const affixCount = 2 + Math.floor(rand() * 3); // 2-4
  const pool = [...AFFIXES];
  const affixes = [];
  for (let i = 0; i < affixCount && pool.length; i += 1) {
    const idx = Math.floor(rand() * pool.length);
    const [affix] = pool.splice(idx, 1);
    const roll = 0.55 + rand() * 0.45;
    affixes.push({
      id: affix.id, name: affix.name,
      value: Math.max(1, Math.round((affix.min + rand() * (affix.max - affix.min))
        * qualityOf(quality).multiplier * roll * (1 + floor * 0.08))),
    });
  }
  return {
    id: `it-${Math.floor(rand() * 1e9).toString(36)}`,
    name: `${qualityOf(quality).name}·${pick(rand, ITEM_NAMES)}`,
    slot: slot.id, slotName: slot.name, quality, floor,
    upgrade: 0, affixes,
  };
}

export function itemScore(item) {
  return item.affixes.reduce((sum, a) => sum + a.value, 0) + item.upgrade * 5
    + qualityOf(item.quality).multiplier * 10;
}

export function rollLoot(rand, floor = 1, boss = false) {
  const quality = rollQuality(rand, boss);
  const gold = Math.round((6 + rand() * 14 + floor * 2) * qualityOf(quality).multiplier
    * (boss ? 2.5 : 1));
  const item = rand() < (boss ? 1 : 0.55) ? makeItem(rand, floor, quality, boss) : null;
  return { gold, item, quality };
}

export function makeEnemy(rand, floor, type, count = 0) {
  const archetype = ENEMY_ARCHETYPES[Math.floor(rand() * ENEMY_ARCHETYPES.length)];
  const name = MONSTER_NAMES[Math.min(MONSTER_NAMES.length - 1, floor * 3 + count)];
  const scale = 1 + (floor - 1) * 0.22;
  const elite = type === "elite" || (type === "boss" && false);
  const affix = elite ? ELITE_AFFIXES[Math.floor(rand() * ELITE_AFFIXES.length)] : null;
  const boss = type === "boss";
  return {
    id: `f${floor}-${type}-${count}-${Math.floor(rand() * 1e6)}`,
    name: boss ? "蘑菇王" : elite ? `精英·${name}` : name,
    kind: boss ? "boss" : archetype.id,
    elite, boss, floor,
    maxHp: Math.round((boss ? 260 : elite ? 82 : archetype.hp) * scale),
    hp: Math.round((boss ? 260 : elite ? 82 : archetype.hp) * scale),
    damage: Math.round((boss ? 16 : elite ? 11 : archetype.damage) * (1 + (floor - 1) * 0.18)),
    speed: Math.round(archetype.speed * (affix?.speed || 1) * (boss ? 0.9 : 1)),
    color: boss ? "#f97316" : affix ? "#a855f7" : archetype.color,
    affix: affix?.id || null,
    defense: affix?.defense || 0,
  };
}

export function generateChapter(seed, floorCount = 5) {
  const rand = mulberry32(chapterSeed(seed));
  const floors = [];
  for (let f = 1; f <= floorCount; f += 1) {
    const normalCount = 8 + Math.floor(rand() * 5); // 8-12
    const rooms = [];
    for (let i = 0; i < normalCount; i += 1) {
      let type = "combat";
      if (i === 0) type = "combat";
      else if (i === 1) type = "campfire";
      else if (i === 2) type = "shop";
      else if (i === 3) type = "treasure";
      else if (i === 4 && rand() < 0.6) type = "elite";
      else if (rand() < 0.12) type = "event";
      else if (rand() < 0.22) type = "platform";
      rooms.push({
        index: i, type,
        label: ROOM_LABEL[type],
        name: `${FLOOR_NAMES[f - 1]} ${i + 1}`,
        platforms: type === "platform" || i % 3 === 0
          ? [{ x: 600, y: 430, w: 260, h: 26 }, { x: 980, y: 330, w: 180, h: 24 }]
          : [],
        enemies: [],
        interactable: type === "treasure" ? "chest"
          : type === "shop" ? "merchant"
            : type === "campfire" ? "campfire"
              : type === "event" ? "event" : null,
        door: { x: 1180, y: 470, w: 54, h: 130, locked: true },
      });
    }
    // Boss room is separate from 8-12 normal rooms.
    rooms.push({
      index: normalCount, type: "boss", label: ROOM_LABEL.boss,
      name: `${FLOOR_NAMES[f - 1]} · 王座`, platforms: [],
      enemies: [], interactable: null,
      door: { x: 1180, y: 470, w: 54, h: 130, locked: true },
    });
    // Populate enemies after types are known.
    rooms.forEach((room) => {
      if (["campfire", "shop", "event"].includes(room.type)) return;
      const count = room.type === "boss" ? 1
        : room.type === "elite" ? 2
          : room.type === "treasure" ? 1 : 2 + (room.index % 2);
      for (let i = 0; i < count; i += 1) {
        room.enemies.push(makeEnemy(rand, f, room.type, i));
      }
    });
    floors.push({ index: f, name: FLOOR_NAMES[f - 1], rooms, bossRoom: normalCount });
  }
  return { seed: chapterSeed(seed), floors };
}

export function createPlayer(classId, index = 0) {
  const spec = CLASSES[classId] || CLASSES.swordsman;
  return {
    id: index + 1, classId: spec.id, name: spec.name, color: spec.color,
    x: 90 + index * 64, y: 500, w: 34, h: 52, vx: 0, vy: 0,
    onGround: false, facing: 1, hp: spec.hp, maxHp: spec.hp,
    mp: spec.mp, maxMp: spec.mp, gold: 0, potions: 2,
    baseAttack: spec.attack, baseRange: spec.range, baseSpeed: spec.speed,
    equipment: Object.fromEntries(SLOTS.map((s) => [s.id, null])),
    inventory: [],
    skillCooldown: 0, skill2Cooldown: 0, attackCooldown: 0, dodgeCooldown: 0,
    invuln: 0, cooldown: 0, hitTimer: 0, downed: false, level: 1, xp: 0,
  };
}

export function createRun(classId = "swordsman", coop = false, difficulty = 2, seed = 20261117) {
  const p2Class = classId === "mage" ? "swordsman" : "mage";
  const run = {
    version: 2,
    seed: chapterSeed(seed),
    difficulty,
    floorIndex: 0,
    roomIndex: 0,
    gold: 0,
    potions: 2,
    inventory: [],
    cleared: {},
    chapter: generateChapter(seed, 5),
    players: coop
      ? [createPlayer(classId, 0), createPlayer(p2Class, 1)]
      : [createPlayer(classId, 0)],
    quests: [
      { id: "q-kill", title: "清理蘑菇林", desc: "击败 10 个敌人", target: 10, progress: 0, reward: 40, done: false },
      { id: "q-room", title: "探索迷宫", desc: "完成 3 个房间", target: 3, progress: 0, reward: 60, done: false },
      { id: "q-boss", title: "蘑菇王", desc: "击败第一章 Boss", target: 1, progress: 0, reward: 120, done: false },
    ],
    messages: [],
    startedAt: 0,
  };
  run.currentRoom = currentRoom(run);
  return run;
}

export function currentRoom(run) {
  const floor = run.chapter.floors[run.floorIndex];
  return floor.rooms[run.roomIndex];
}

export function currentFloor(run) {
  return run.chapter.floors[run.floorIndex];
}

export function roomKey(run) {
  return `${run.floorIndex + 1}-${run.roomIndex}`;
}

export function equipmentBonus(player) {
  const bonus = { attack: 0, hp: 0, defense: 0, speed: 0, crit: 0 };
  Object.values(player.equipment).forEach((item) => {
    if (!item) return;
    item.affixes.forEach((a) => { bonus[a.id] = (bonus[a.id] || 0) + a.value; });
    bonus.attack += item.upgrade * 2;
  });
  return bonus;
}

export function derivedStats(player) {
  const bonus = equipmentBonus(player);
  const spec = CLASSES[player.classId];
  return {
    attack: player.baseAttack + bonus.attack,
    maxHp: spec.hp + bonus.hp,
    maxMp: spec.mp,
    speed: player.baseSpeed + bonus.speed,
    defense: bonus.defense,
    crit: Math.min(0.5, bonus.crit / 100),
    range: player.baseRange,
  };
}

export function equipItem(player, item) {
  if (!item || !SLOTS.some((s) => s.id === item.slot)) return null;
  const previous = player.equipment[item.slot];
  player.equipment[item.slot] = item;
  const stats = derivedStats(player);
  player.maxHp = stats.maxHp;
  player.hp = Math.min(player.hp, player.maxHp);
  return previous;
}

export function addInventory(player, item, capacity = 60) {
  if (!item) return false;
  if (player.inventory.length >= capacity) return false;
  player.inventory.push(item);
  return true;
}

export function decomposeValue(item) {
  return Math.round(itemScore(item) * 0.6);
}

export function reforgeItem(item, rand) {
  const affixCount = 2 + Math.floor(rand() * 3);
  const pool = [...AFFIXES];
  item.affixes = [];
  for (let i = 0; i < affixCount && pool.length; i += 1) {
    const idx = Math.floor(rand() * pool.length);
    const [affix] = pool.splice(idx, 1);
    item.affixes.push({
      id: affix.id, name: affix.name,
      value: Math.max(1, Math.round((affix.min + rand() * (affix.max - affix.min))
        * qualityOf(item.quality).multiplier)),
    });
  }
  return item;
}

export function upgradeCost(item) {
  return 20 + item.upgrade * 15 + item.floor * 5;
}

export function tryUpgrade(item, gold) {
  if (item.upgrade >= 9) return { ok: false, reason: "已 +9" };
  const cost = upgradeCost(item);
  if (gold < cost) return { ok: false, reason: `金币不足（需要 ${cost}）` };
  item.upgrade += 1;
  return { ok: true, cost };
}

export function shopStock(rand, floor) {
  return {
    potion: { price: 10, name: "治疗药水" },
    items: [makeItem(rand, floor), makeItem(rand, floor), makeItem(rand, floor)],
    reforge: 30,
  };
}

export function eventChoice(rand, floor) {
  const events = [
    { id: "bless", title: "古老祭坛", text: "献上 10 金币，获得永久攻击 +2。", cost: 10, effect: "attack" },
    { id: "heal", title: "发光蘑菇", text: "恢复 35% 生命，但最大生命 -5。", cost: 0, effect: "heal" },
    { id: "gold", title: "冒险者遗物", text: "获得 40 金币。", cost: 0, effect: "gold" },
    { id: "curse", title: "诅咒宝箱", text: "获得一件紫装，但受到 20 伤害。", cost: 0, effect: "curse" },
  ];
  return pick(rand, events);
}

export function addXp(player, amount) {
  player.xp = (player.xp || 0) + Math.max(0, amount);
  let levels = 0;
  while (player.level < 30) {
    const need = 30 + player.level * 18;
    if (player.xp < need) break;
    player.xp -= need;
    player.level += 1;
    player.baseAttack += 2;
    const spec = CLASSES[player.classId];
    player.maxHp = spec.hp + (player.level - 1) * 6 + equipmentBonus(player).hp;
    player.hp = Math.min(player.maxHp, player.hp + 12);
    levels += 1;
  }
  return levels;
}

export function questProgress(run, kind, amount = 1) {
  run.quests.forEach((q) => {
    if (q.done) return;
    if (kind === "kill" && q.id === "q-kill") q.progress = Math.min(q.target, q.progress + amount);
    if (kind === "room" && q.id === "q-room") q.progress = Math.min(q.target, q.progress + amount);
    if (kind === "boss" && q.id === "q-boss") q.progress = Math.min(q.target, q.progress + amount);
    if (q.progress >= q.target) q.done = true;
  });
}

export function claimQuest(run, questId) {
  const q = run.quests.find((item) => item.id === questId);
  if (!q || !q.done || q.claimed) return 0;
  q.claimed = true;
  run.gold += q.reward;
  return q.reward;
}

export function chapterProgress(run) {
  const total = run.chapter.floors.reduce((sum, f) => sum + f.rooms.length, 0);
  let done = 0;
  for (let f = 0; f < run.chapter.floors.length; f += 1) {
    for (let r = 0; r < run.chapter.floors[f].rooms.length; r += 1) {
      if (run.cleared[`${f + 1}-${r}`]) done += 1;
    }
  }
  return { done, total, percent: total ? Math.round(done / total * 100) : 0 };
}

export function checksum(text) {
  let hash = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16);
}

export function encodeSave(data) {
  const body = JSON.stringify(data);
  return JSON.stringify({ format: "maze-adventurer-save", version: 2, body, crc: checksum(body) });
}

export function decodeSave(text) {
  if (typeof text !== "string" || !text.trim()) return null;
  try {
    const outer = JSON.parse(text);
    if (outer.format !== "maze-adventurer-save" || ![1, 2].includes(outer.version)) return null;
    if (typeof outer.body !== "string" || checksum(outer.body) !== outer.crc) return null;
    const data = JSON.parse(outer.body);
    // Migration: v1 saves have no equipment/inventory; defaults fill them.
    data.inventory = data.inventory || [];
    data.difficulty = data.difficulty || 2;
    (data.players || []).forEach((p) => {
      p.equipment = p.equipment || Object.fromEntries(SLOTS.map((s) => [s.id, null]));
      p.inventory = p.inventory || [];
    });
    data.version = 2;
    return data;
  } catch {
    return null;
  }
}

export function snapshot(run, slot = 1) {
  return {
    slot,
    version: 2,
    seed: run.seed,
    difficulty: run.difficulty,
    floorIndex: run.floorIndex,
    roomIndex: run.roomIndex,
    gold: run.gold,
    potions: run.potions,
    cleared: run.cleared,
    inventory: run.inventory,
    quests: run.quests,
    maxFloorReached: run.floorIndex + 1,
    players: run.players.map((p) => ({
      classId: p.classId, hp: Math.max(1, p.hp), mp: p.mp,
      x: p.x, y: p.y, equipment: p.equipment, inventory: p.inventory,
      level: p.level, xp: p.xp,
    })),
  };
}

export function restoreRun(data) {
  const run = createRun(data.players?.[0]?.classId || "swordsman",
    (data.players || []).length > 1, data.difficulty || 2, data.seed);
  run.floorIndex = Math.min(data.floorIndex || 0, run.chapter.floors.length - 1);
  run.roomIndex = Math.min(data.roomIndex || 0, currentFloor(run).rooms.length - 1);
  run.gold = data.gold || 0;
  run.potions = data.potions || 0;
  run.cleared = data.cleared || {};
  run.inventory = data.inventory || [];
  run.quests = data.quests || run.quests;
  run.players.forEach((p, i) => {
    const saved = data.players?.[i];
    if (!saved) return;
    p.hp = saved.hp || p.hp;
    p.mp = saved.mp || p.mp;
    p.x = saved.x || p.x;
    p.y = saved.y || p.y;
    p.level = saved.level || 1;
    p.xp = saved.xp || 0;
    p.equipment = saved.equipment || p.equipment;
    p.inventory = saved.inventory || [];
    equipItem(p, p.equipment?.weapon || null);
  });
  run.currentRoom = currentRoom(run);
  return run;
}
