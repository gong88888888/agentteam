// Object-style floor contract; keeps maze.js as the implementation.
import { generateFloor as makeFloor } from "./maze.js";

export function generateFloor({ seed = 1, floorIndex = 1, chapter = 1, rooms = 10 } = {}) {
  const floor = makeFloor(seed + floorIndex * 7919 + chapter * 104729, { rooms });
  floor.mainPath = floor.rooms.map((r) => r.id);
  floor.floorIndex = floorIndex;
  floor.chapter = chapter;
  return floor;
}
