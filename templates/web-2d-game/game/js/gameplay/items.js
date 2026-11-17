// Equipment item contract used by QA and gameplay.
import { SLOTS, AFFIXES, QUALITIES } from "../core.js";
import { mulberry32 } from "../core.js";

function rngOf(opts) {
  if (typeof opts?.rng === "function") return opts.rng;
  if (typeof opts?.seed === "number") return mulberry32(opts.seed);
  return Math.random;
}

export function generateItem({ seed = 1, slot = null, quality = null, floor = 1, rng = null } = {}) {
  const rand = rng || mulberry32(seed);
  const q = quality || QUALITIES[Math.floor(rand() * QUALITIES.length)].id;
  const slotSpec = slot ? SLOTS.find((s) => s.id === slot) || SLOTS[0]
    : SLOTS[Math.floor(rand() * SLOTS.length)];
  const count = 2 + Math.floor(rand() * 3);
  const pool = [...AFFIXES];
  const affixes = [];
  for (let i = 0; i < count; i += 1) {
    const idx = Math.floor(rand() * pool.length);
    const [a] = pool.splice(idx, 1);
    affixes.push({ id: a.id, name: a.name, value: Math.max(1, Math.round(a.min + rand() * (a.max - a.min))) });
  }
  return {
    id: `qa-${seed}-${Math.floor(rand() * 1e6)}`,
    name: `${q}·${slotSpec.name}`,
    slot: slotSpec.id, slotName: slotSpec.name, quality: q, floor,
    upgrade: 0, enhanceLevel: 0, affixes,
  };
}

export function enhance(item, { rng = Math.random } = {}) {
  const next = { ...item, enhanceLevel: Number(item.enhanceLevel || item.upgrade || 0) };
  if (next.enhanceLevel >= 9) return { ok: false, item: next, reason: "max" };
  // MVP rule: failure does not downgrade.
  if (rng() < 0.85) next.enhanceLevel += 1;
  next.upgrade = next.enhanceLevel;
  return { ok: true, item: next };
}
