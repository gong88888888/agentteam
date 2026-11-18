// Deterministic floor generator contract used by gameplay and QA.
export const FLOOR_TYPES = ["combat", "platform", "treasure", "shop", "campfire", "event", "elite", "boss"];

export function makeRng(seed) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function generateFloor(seed, { rooms = 10 } = {}) {
  if (!Number.isInteger(seed) || seed < 0) throw new Error("seed must be a non-negative integer");
  const count = Math.max(8, Math.min(12, Number(rooms) || 10));
  const rng = makeRng(seed);
  const list = [];
  for (let i = 0; i < count; i += 1) {
    list.push({ id: i, type: "combat", doors: [] });
  }
  list[1].type = "campfire";
  list[2].type = "shop";
  const treasureCount = 2 + Math.floor(rng() * 3); // 2-4
  let placed = 0;
  for (let i = 3; i < count - 1 && placed < treasureCount; i += 1) {
    if (list[i].type === "combat") { list[i].type = "treasure"; placed += 1; }
  }
  if (rng() < 0.6) {
    const elite = list.find((r) => r.type === "combat" && r.id > 2);
    if (elite) elite.type = "elite";
  }
  list[count - 1].type = "boss";
  const edges = [];
  for (let i = 0; i < count - 1; i += 1) {
    edges.push([i, i + 1]);
    list[i].doors.push(i + 1);
    list[i + 1].doors.push(i);
  }
  return {
    seed, rooms: list, edges, entryRoomId: 0, bossRoomId: count - 1,
    keyDoor: null,
  };
}

export function validateFloor(floor) {
  const types = floor.rooms.map((r) => r.type);
  if (types.filter((t) => t === "campfire").length !== 1) throw new Error("campfire count");
  if (types.filter((t) => t === "shop").length !== 1) throw new Error("shop count");
  if (types.filter((t) => t === "boss").length !== 1) throw new Error("boss count");
  return true;
}

// Integration metadata: loaded and exercised by tests/integration.mjs.
export const extension = { id: "gameplay-maze", version: 1, actions: ["generateFloor"], smoke: { action: "generateFloor", args: [1], expectType: "object" } };
