import assert from "node:assert/strict";
import {
  CLASSES, createRun, generateDungeon, roomCleared, rollLoot,
  mulberry32, encodeSave, decodeSave, snapshot,
} from "../js/core.js";

const rooms = generateDungeon(20261116);
assert.equal(rooms.length, 4);
assert.equal(rooms.at(-1).boss, true);
assert.equal(Object.keys(CLASSES).length, 3);

const run = createRun("swordsman", true);
assert.equal(run.players.length, 2);
run.gold = 42;
run.defeated = rooms[0].enemies.map((e) => e.id);
assert.equal(roomCleared(rooms[0], run.defeated), true);

const item = rollLoot(mulberry32(5));
assert.ok(item.name && item.gold > 0);
const save = encodeSave(snapshot(run));
assert.equal(decodeSave(save).gold, 42);

console.log("GAME SMOKE PASS", JSON.stringify({
  rooms: rooms.length,
  classes: Object.keys(CLASSES).length,
  coopPlayers: run.players.length,
  loot: item.name,
}));
