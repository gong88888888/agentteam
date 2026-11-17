import assert from "node:assert/strict";
import {
  CLASSES, createRun, generateChapter, multiplayerScale, rollLoot,
  makeItem, encodeSave, decodeSave, snapshot, chapterProgress, mulberry32,
} from "../js/core.js";

const chapter = generateChapter(20261117);
assert.equal(chapter.floors.length, 5);
assert.ok(chapter.floors.every((f) => f.rooms.at(-1).type === "boss"));
assert.equal(Object.keys(CLASSES).length, 3);

const run = createRun("swordsman", true, 2);
assert.equal(run.players.length, 2);
run.gold = 42;
run.cleared["1-0"] = true;
assert.equal(chapterProgress(run).done, 1);
assert.equal(multiplayerScale(2).hp, 1.6);

const item = makeItem(mulberry32(5), 2, "blue");
assert.ok(item.affixes.length >= 2);
const loot = rollLoot(mulberry32(6), 1, true);
assert.ok(loot.item);
const save = encodeSave(snapshot(run));
assert.equal(decodeSave(save).gold, 42);

console.log("GAME SMOKE PASS", JSON.stringify({
  floors: chapter.floors.length,
  classes: Object.keys(CLASSES).length,
  coopPlayers: run.players.length,
  loot: loot.item.name,
}));
