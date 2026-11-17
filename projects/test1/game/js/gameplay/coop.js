// Local co-op contract.
export function assignDropOwner(drop, playerId) {
  return { ...drop, ownerId: playerId };
}

export function stepRevive(state, dt) {
  if (!state || !state.downed) return state;
  if (state.reviverNear) state.reviveProgress = Math.min(3, (state.reviveProgress || 0) + dt);
  if (state.reviveProgress >= 3) state.downed = false;
  return state;
}

export function allDown(players) {
  return Array.isArray(players) && players.length > 0 && players.every((p) => p.downed);
}

export function removePlayer(world, playerId) {
  const copy = { ...world, players: { ...world.players } };
  delete copy.players[playerId];
  return copy;
}

export const reviveTime = 3;
export const teleportDelay = 3;

export function getScaling(players) {
  const n = Math.max(1, Math.min(4, Number(players) | 0));
  return {
    1: { hp: 1, dmg: 1, gold: 1 },
    2: { hp: 1.6, dmg: 1.15, gold: 1.25 },
    3: { hp: 2.1, dmg: 1.25, gold: 1.45 },
    4: { hp: 2.6, dmg: 1.35, gold: 1.65 },
  }[n];
}

export function getBossScaling(players) {
  const base = getScaling(players);
  return { ...base, hp: base.hp * 1.1 };
}
