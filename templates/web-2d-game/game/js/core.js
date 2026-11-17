// Pure game rules shared by the browser game and Node tests.
// No DOM or canvas access here.

export const CLASSES = {
  swordsman: {
    id: "swordsman", name: "剑士", hp: 120, speed: 260, jump: 620,
    damage: 22, range: 72, color: "#3b82f6",
    skill: "旋风斩：短距离高伤害",
  },
  mage: {
    id: "mage", name: "法师", hp: 86, speed: 225, jump: 600,
    damage: 30, range: 120, color: "#a855f7",
    skill: "火墙：远程范围伤害",
  },
  ranger: {
    id: "ranger", name: "游侠", hp: 96, speed: 285, jump: 650,
    damage: 18, range: 165, color: "#22c55e",
    skill: "箭雨：远距离穿透",
  },
};

export const QUALITIES = [
  { id: "white", name: "白", weight: 40, color: "#e5e7eb", multiplier: 1 },
  { id: "green", name: "绿", weight: 30, color: "#22c55e", multiplier: 1.2 },
  { id: "blue", name: "蓝", weight: 20, color: "#3b82f6", multiplier: 1.5 },
  { id: "purple", name: "紫", weight: 8, color: "#a855f7", multiplier: 2.2 },
  { id: "orange", name: "橙", weight: 2, color: "#f97316", multiplier: 3.5 },
];

const ITEM_NAMES = [
  "蘑菇林短剑", "矿洞护符", "遗迹戒指", "旧城头盔", "篝火披风",
  "藤蔓战靴", "Boss 徽记", "探险家手套",
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

const ROOM_TYPES = ["combat", "platform", "elite", "boss"];
const ROOM_NAMES = ["蘑菇林入口", "藤蔓跳台", "精英守卫", "蘑菇王巢穴"];

export function generateDungeon(seed, roomCount = 4) {
  const rand = mulberry32(seed);
  const rooms = [];
  for (let i = 0; i < roomCount; i += 1) {
    const boss = i === roomCount - 1;
    const type = boss ? "boss" : ROOM_TYPES[i % 3];
    const count = boss ? 1 : 2 + (i % 2);
    const enemies = [];
    for (let j = 0; j < count; j += 1) {
      const elite = type === "elite";
      enemies.push({
        id: `r${i}-e${j}`,
        kind: boss ? "boss" : elite ? "elite" : j === 0 ? "walker" : "flyer",
        hp: boss ? 220 : elite ? 78 : 42,
        speed: boss ? 70 : elite ? 88 : 58 + Math.floor(rand() * 20),
        damage: boss ? 16 : elite ? 11 : 7,
        x: 380 + j * 220 + Math.floor(rand() * 30),
        y: 540,
        boss,
      });
    }
    rooms.push({
      index: i,
      name: ROOM_NAMES[i % ROOM_NAMES.length],
      type,
      boss,
      platforms: type === "platform" || i === 1
        ? [{ x: 600, y: 430, w: 260, h: 26 }, { x: 980, y: 330, w: 180, h: 24 }]
        : i === 2 ? [{ x: 760, y: 420, w: 220, h: 26 }] : [],
      enemies,
      door: { x: 1180, y: 470, w: 54, h: 130, locked: true },
    });
  }
  return rooms;
}

export function rollLoot(rand) {
  const total = QUALITIES.reduce((sum, q) => sum + q.weight, 0);
  let roll = rand() * total;
  let picked = QUALITIES[0];
  for (const quality of QUALITIES) {
    roll -= quality.weight;
    if (roll <= 0) { picked = quality; break; }
  }
  const name = ITEM_NAMES[Math.floor(rand() * ITEM_NAMES.length)];
  return {
    quality: picked.id,
    name: `${picked.name}·${name}`,
    color: picked.color,
    gold: Math.round((5 + rand() * 15) * picked.multiplier),
    power: Math.round((2 + rand() * 6) * picked.multiplier),
  };
}

export function createPlayer(classId, index) {
  const spec = CLASSES[classId] || CLASSES.swordsman;
  return {
    id: index + 1, classId: spec.id, name: spec.name,
    x: 90 + index * 70, y: 500, w: 34, h: 52,
    vx: 0, vy: 0, onGround: false, hp: spec.hp, maxHp: spec.hp,
    speed: spec.speed, jump: spec.jump, damage: spec.damage,
    range: spec.range, color: spec.color, cooldown: 0, hitTimer: 0,
  };
}

export function createRun(classId = "swordsman", coop = false, seed = 20261116) {
  const p2Class = classId === "mage" ? "swordsman" : "mage";
  return {
    version: 1,
    seed,
    roomIndex: 0,
    dungeon: generateDungeon(seed),
    players: coop
      ? [createPlayer(classId, 0), createPlayer(p2Class, 1)]
      : [createPlayer(classId, 0)],
    gold: 0,
    lootLog: [],
    defeated: [],
    victory: false,
    startedAt: 0,
  };
}

export function roomCleared(room, defeated) {
  return room.enemies.every((enemy) => defeated.includes(enemy.id));
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
  return JSON.stringify({ format: "agentteam-game-save", v: 1, body, crc: checksum(body) });
}

export function decodeSave(text) {
  if (typeof text !== "string" || !text.trim()) return null;
  try {
    const outer = JSON.parse(text);
    if (outer.format !== "agentteam-game-save" || outer.v !== 1) return null;
    if (typeof outer.body !== "string" || checksum(outer.body) !== outer.crc) return null;
    return JSON.parse(outer.body);
  } catch {
    return null;
  }
}

export function snapshot(run) {
  return {
    version: 1,
    seed: run.seed,
    roomIndex: run.roomIndex,
    gold: run.gold,
    players: run.players.map((p) => ({
      classId: p.classId, x: p.x, y: p.y, hp: Math.max(1, p.hp),
    })),
    lootLog: run.lootLog.slice(-20),
    defeated: run.defeated.slice(),
    victory: run.victory,
  };
}
