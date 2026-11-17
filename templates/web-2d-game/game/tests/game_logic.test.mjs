import test from "node:test";
import assert from "node:assert/strict";
import {
  CLASSES, QUALITIES, createRun, generateDungeon, roomCleared,
  rollLoot, mulberry32, encodeSave, decodeSave, snapshot,
} from "../js/core.js";

test("three playable classes with distinct roles", () => {
  assert.deepEqual(Object.keys(CLASSES), ["swordsman", "mage", "ranger"]);
  assert.ok(CLASSES.mage.range > CLASSES.swordsman.range);
  assert.ok(CLASSES.swordsman.hp > CLASSES.mage.hp);
  assert.ok(CLASSES.ranger.speed > CLASSES.mage.speed);
});

test("dungeon has 4 rooms and ends with a locked boss room", () => {
  const rooms = generateDungeon(1234);
  assert.equal(rooms.length, 4);
  assert.equal(rooms[0].type, "combat");
  assert.equal(rooms[1].type, "platform");
  assert.equal(rooms[2].type, "elite");
  assert.equal(rooms[3].type, "boss");
  assert.equal(rooms[3].enemies.length, 1);
  assert.equal(rooms[3].enemies[0].boss, true);
  assert.ok(rooms.every((room) => room.door.locked));
  assert.ok(rooms[1].platforms.length >= 2);
});

test("room clear requires every enemy id", () => {
  const room = generateDungeon(9)[0];
  assert.equal(roomCleared(room, []), false);
  const ids = room.enemies.map((enemy) => enemy.id);
  assert.equal(roomCleared(room, ids.slice(0, -1)), false);
  assert.equal(roomCleared(room, ids), true);
});

test("loot uses the 40/30/20/8/2 quality table", () => {
  const rand = mulberry32(42);
  const seen = new Set();
  let total = 0;
  for (let i = 0; i < 2000; i += 1) {
    const item = rollLoot(rand);
    seen.add(item.quality);
    total += item.gold;
  }
  assert.deepEqual([...seen].sort(), QUALITIES.map((q) => q.id).sort());
  assert.ok(total > 0);
});

test("single player and local co-op runs", () => {
  const solo = createRun("swordsman", false);
  assert.equal(solo.players.length, 1);
  assert.equal(solo.players[0].classId, "swordsman");
  const coop = createRun("ranger", true);
  assert.equal(coop.players.length, 2);
  assert.equal(coop.players[1].classId, "mage");
});

test("save round-trip and tamper detection", () => {
  const run = createRun("mage", true, 77);
  run.gold = 123;
  run.roomIndex = 2;
  const encoded = encodeSave(snapshot(run));
  const decoded = decodeSave(encoded);
  assert.equal(decoded.gold, 123);
  assert.equal(decoded.roomIndex, 2);
  assert.equal(decoded.players.length, 2);
  const outer = JSON.parse(encoded);
  const body = JSON.parse(outer.body);
  body.gold = 999;
  const tampered = JSON.stringify({ ...outer, body: JSON.stringify(body) });
  assert.equal(decodeSave(tampered), null);
});
