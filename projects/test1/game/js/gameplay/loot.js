import { mulberry32 } from "../core.js";
// Loot contract used by gameplay and QA.
export const WEIGHTS = { white: 40, green: 30, blue: 20, purple: 8, orange: 2 };
export const ORDER = ["white", "green", "blue", "purple", "orange"];

export function rollRarity(rng = Math.random) {
  if (typeof rng !== "function") rng = Math.random;
  let roll = rng() * 100;
  for (const id of ORDER) {
    roll -= WEIGHTS[id];
    if (roll <= 0) return id;
  }
  return "white";
}

export function rollBossDrop(input = Math.random) {
  const rng = typeof input === "function" ? input
    : typeof input?.rng === "function" ? input.rng
      : typeof input?.seed === "number" ? mulberry32(input.seed) : Math.random;
  if (rng() < 0.05) return "orange";
  if (rng() < 0.2) return "purple";
  return "blue";
}

export function rollQuality(input = Math.random) {
  const rng = typeof input === "function" ? input
    : typeof input?.rng === "function" ? input.rng
      : typeof input?.seed === "number" ? mulberry32(input.seed) : Math.random;
  return rollRarity(rng);
}

export function rollDrop({ boss = false, rng = Math.random } = {}) {
  return boss ? rollBossDrop(rng) : rollQuality(rng);
}
