// inventory.js - 背包60/仓库200/分解/对比（纯逻辑）
export const BAG_SIZE = 60;
export const STASH_SIZE = 200;

export function createInventory() {
  return { bag: [], stash: [], materials: 0, gold: 0 };
}

export function addItem(inv, item) {
  if (inv.bag.length >= BAG_SIZE) return { ok: false, reason: 'bag_full' };
  inv.bag.push(item);
  return { ok: true };
}

export function moveToStash(inv, itemId) {
  const idx = inv.bag.findIndex(i => i.id === itemId);
  if (idx < 0) return { ok: false, reason: 'not_found' };
  if (inv.stash.length >= STASH_SIZE) return { ok: false, reason: 'stash_full' };
  const [it] = inv.bag.splice(idx, 1);
  inv.stash.push(it);
  return { ok: true };
}

export function dismantle(inv, itemId) {
  const idx = inv.bag.findIndex(i => i.id === itemId);
  if (idx < 0) return { ok: false, reason: 'not_found' };
  const [it] = inv.bag.splice(idx, 1);
  const gain = { white: 1, green: 2, blue: 4, purple: 8, orange: 16 }[it.quality] || 1;
  inv.materials += gain;
  return { ok: true, materials: gain };
}

export function dismantleWhiteGreen(inv) {
  let n = 0;
  inv.bag = inv.bag.filter(it => {
    if (it.quality === 'white' || it.quality === 'green') { n++; inv.materials += it.quality === 'white' ? 1 : 2; return false; }
    return true;
  });
  return { count: n };
}

export function compare(a, b) {
  const score = it => it.affixes.reduce((s, af) => s + af.value, 0) + it.enhanceLevel * 2;
  return { better: score(b) > score(a), delta: score(b) - score(a) };
}

// Integration metadata: loaded and exercised by tests/integration.mjs.
export const extension = { id: "gameplay-inventory", version: 1, actions: ["createInventory"], smoke: { action: "createInventory", args: [], expectType: "object" } };
