import test from "node:test";
import assert from "node:assert/strict";
import {
  CLASSES, DIFFICULTIES, SLOTS, createRun, generateChapter, multiplayerScale,
  rollQuality, makeItem, rollLoot, equipItem, addInventory, derivedStats,
  encodeSave, decodeSave, snapshot, restoreRun, upgradeCost, tryUpgrade,
  reforgeItem, chapterProgress, mulberry32, shopStock, eventChoice, checksum, addXp, questProgress, claimQuest,
} from "../js/core.js";

test("three classes expose distinct skills and stats", () => {
  assert.deepEqual(Object.keys(CLASSES), ["swordsman", "mage", "ranger"]);
  assert.ok(CLASSES.mage.mp > CLASSES.swordsman.mp);
  assert.ok(CLASSES.swordsman.hp > CLASSES.mage.hp);
  assert.ok(CLASSES.ranger.speed > CLASSES.mage.speed);
  for (const spec of Object.values(CLASSES)) {
    assert.ok(spec.skill.name && spec.skill.mp > 0 && spec.skill.cooldown > 0);
  }
});

test("chapter has 5 floors, 8-12 normal rooms, a boss and required room types", () => {
  const chapter = generateChapter(20261117);
  assert.equal(chapter.floors.length, 5);
  for (const floor of chapter.floors) {
    const normal = floor.rooms.filter((r) => r.type !== "boss");
    assert.ok(normal.length >= 8 && normal.length <= 12, `floor ${floor.index} rooms ${normal.length}`);
    assert.equal(floor.rooms.at(-1).type, "boss");
    assert.equal(floor.rooms.at(-1).enemies.length, 1);
    assert.ok(floor.rooms.some((r) => r.type === "campfire"));
    assert.ok(floor.rooms.some((r) => r.type === "shop"));
    assert.ok(floor.rooms.some((r) => r.type === "treasure"));
    assert.ok(floor.rooms.every((r) => r.door.locked));
  }
  const again = generateChapter(20261117);
  assert.deepEqual(again, chapter);
});

test("multiplayer scaling follows the product table", () => {
  const table = {
    1: { hp: 1, damage: 1, gold: 1 },
    2: { hp: 1.6, damage: 1.15, gold: 1.25 },
    3: { hp: 2.1, damage: 1.25, gold: 1.45 },
    4: { hp: 2.6, damage: 1.35, gold: 1.65 },
  };
  for (const n of [1, 2, 3, 4]) {
    const scale = multiplayerScale(n);
    assert.deepEqual(scale, table[n]);
    assert.ok(Math.abs(multiplayerScale(n, true).hp - table[n].hp * 1.1) < 1e-9);
  }
});

test("loot uses the 5-quality table, boss guarantee, and 2-4 affixes", () => {
  const rand = mulberry32(42);
  const seen = new Set();
  for (let i = 0; i < 4000; i += 1) seen.add(rollQuality(rand));
  assert.deepEqual([...seen].sort(), ["blue", "green", "orange", "purple", "white"]);
  for (let i = 0; i < 20; i += 1) {
    const q = rollQuality(rand, true);
    assert.ok(["blue", "purple", "orange"].includes(q), q);
    const item = makeItem(rand, 3, q, true);
    assert.ok(item.affixes.length >= 2 && item.affixes.length <= 4);
    assert.ok(SLOTS.some((s) => s.id === item.slot));
  }
  const loot = rollLoot(rand, 1, true);
  assert.ok(loot.gold > 0);
  assert.ok(loot.item);
});

test("equipment changes derived stats and inventory caps at 60", () => {
  const p = createRun("swordsman", false).players[0];
  const rand = mulberry32(7);
  const item = makeItem(rand, 2, "purple");
  const before = derivedStats(p).attack;
  equipItem(p, item);
  assert.ok(derivedStats(p).attack >= before);
  for (let i = 0; i < 60; i += 1) assert.equal(addInventory(p, makeItem(rand, 1)), true);
  assert.equal(addInventory(p, makeItem(rand, 1)), false);
});

test("upgrade and reforge work and respect gold", () => {
  const rand = mulberry32(11);
  const item = makeItem(rand, 2, "blue");
  const cost = upgradeCost(item);
  assert.equal(tryUpgrade(item, 0).ok, false);
  assert.equal(tryUpgrade(item, cost).ok, true);
  assert.equal(item.upgrade, 1);
  const old = item.affixes.map((a) => `${a.id}:${a.value}`).join("|");
  reforgeItem(item, rand);
  assert.notEqual(item.affixes.map((a) => `${a.id}:${a.value}`).join("|"), old);
});

test("save envelope round-trips, detects tampering and migrates v1", () => {
  const run = createRun("ranger", true, 3, 99);
  run.gold = 123;
  run.floorIndex = 2;
  run.roomIndex = 1;
  const encoded = encodeSave(snapshot(run));
  const decoded = decodeSave(encoded);
  assert.equal(decoded.gold, 123);
  assert.equal(decoded.players.length, 2);
  assert.equal(decoded.difficulty, 3);

  const outer = JSON.parse(encoded);
  const body = JSON.parse(outer.body);
  body.gold = 999;
  assert.equal(decodeSave(JSON.stringify({ ...outer, body: JSON.stringify(body) })), null);

  // v1 with a valid CRC is migrated with defaults.
  const bodyV1 = JSON.stringify({ seed: 1, players: [{ classId: "mage", hp: 10 }] });
  const crc = checksum(bodyV1);
  const migrated = decodeSave(JSON.stringify({
    format: "maze-adventurer-save", version: 1, body: bodyV1, crc,
  }));
  assert.equal(migrated.version, 2);
  assert.deepEqual(migrated.players[0].equipment, {
    weapon: null, helmet: null, armor: null, boots: null, accessory: null,
  });
});

test("shop/event and chapter progress are deterministic", () => {
  const run = createRun("swordsman", false, 2, 5);
  const stock = shopStock(mulberry32(3), 1);
  assert.equal(stock.items.length, 3);
  assert.ok(stock.potion.price > 0);
  const event = eventChoice(mulberry32(4), 1);
  assert.ok(event.title && event.effect);
  assert.equal(chapterProgress(run).done, 0);
  run.cleared["1-0"] = true;
  assert.equal(chapterProgress(run).done, 1);
});


test("leveling and quest rewards work", () => {
  const run = createRun("swordsman", false);
  const p = run.players[0];
  const levels = addXp(p, 500);
  assert.ok(levels > 0);
  assert.ok(p.level > 1);
  questProgress(run, "kill", 10);
  assert.equal(run.quests.find((q) => q.id === "q-kill").done, true);
  const before = run.gold;
  const reward = claimQuest(run, "q-kill");
  assert.ok(reward > 0);
  assert.equal(run.gold, before + reward);
  assert.equal(claimQuest(run, "q-kill"), 0);
});
