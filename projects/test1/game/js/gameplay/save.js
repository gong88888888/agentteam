// Save contract: CRC32, primary + backup, version migration.
export const SAVE_VERSION = 2;

export function crc32(text) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < text.length; i += 1) {
    crc ^= text.charCodeAt(i);
    for (let j = 0; j < 8; j += 1) crc = (crc >>> 1) ^ (0xEDB88320 & -(crc & 1));
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

export function writeSave(store, key, payload) {
  const body = JSON.stringify({ version: SAVE_VERSION, payload });
  const envelope = JSON.stringify({ body, crc: crc32(body) });
  store.setItem(key, envelope);
  store.setItem(`${key}.bak`, envelope);
  return envelope;
}

export function readSave(store, key) {
  for (const candidate of [key, `${key}.bak`]) {
    const raw = store.getItem(candidate);
    if (!raw) continue;
    try {
      const outer = JSON.parse(raw);
      if (crc32(outer.body) !== outer.crc) continue;
      const data = JSON.parse(outer.body);
      const version = Number(data.version) || 1;
      return { version: Math.max(version, SAVE_VERSION), payload: data.payload || data };
    } catch { /* try backup */ }
  }
  return null;
}


// QA-facing envelope API used by tests and the browser game.
export function serialize(state) {
  const version = Number(state.version) || SAVE_VERSION;
  const body = { ...state, version };
  const json = JSON.stringify(body);
  return { version, json, crc: crc32(json) };
}

export function deserialize(input, expectedCrc) {
  const json = typeof input === "string" ? input : input?.json;
  const crc = expectedCrc ?? input?.crc;
  if (typeof json !== "string" || crc32(json) !== crc) return null;
  return JSON.parse(json);
}

export function loadWithFallback(corrupted, { backup = null } = {}) {
  const recovered = deserialize(corrupted);
  if (recovered) return recovered;
  const fallback = backup ? deserialize(backup) : null;
  if (fallback) return fallback;
  if (corrupted?.lastCampfire) return { ...corrupted.lastCampfire, fallback: true };
  return null;
}

// Integration metadata: loaded and exercised by tests/integration.mjs.
export const extension = { id: "gameplay-save", version: 1, actions: ["crc32"], smoke: { action: "crc32", args: ["abc"], expectType: "number" } };
