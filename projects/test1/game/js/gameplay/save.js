// 存档信封：版本号 + CRC32 + 双备份 + 迁移链（纯逻辑）
export const SAVE_VERSION = 2;

export function crc32(str) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < str.length; i++) {
    crc ^= str.charCodeAt(i);
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (0xEDB88320 & -(crc & 1));
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

export function makeEnvelope(payload, version = SAVE_VERSION) {
  return { version, data: payload, crc: crc32(JSON.stringify(payload)) };
}

export function verifyEnvelope(env) {
  if (!env || typeof env.crc !== 'number') return false;
  const payload = env.data !== undefined ? env.data : JSON.parse(env.body || 'null');
  return payload !== null && crc32(JSON.stringify(payload)) === env.crc;
}

// 迁移链：旧版本 -> 新版本
export const MIGRATIONS = {
  1: (p) => p,
};

export function migrate(env) {
  let v;
  let payload;
  if (env && env.data !== undefined) {
    if (env.crc !== undefined && !verifyEnvelope(env)) throw new Error('save corrupted (crc mismatch)');
    v = env.version || 1;
    payload = env.data;
  } else if (env && typeof env.body === 'string') {
    if (!verifyEnvelope(env)) throw new Error('save corrupted (crc mismatch)');
    v = env.version || 1;
    payload = JSON.parse(env.body);
  } else if (env && env.data) {
    v = env.version || 1;
    payload = env.data;
  } else {
    v = 1;
    payload = env || {};
  }
  while (v < SAVE_VERSION) {
    const fn = MIGRATIONS[v];
    if (!fn) throw new Error('no migration from version ' + v);
    payload = fn(payload);
    v++;
  }
  return { version: v, data: payload };
}

// 双备份写入（介质由调用方注入，浏览器用 localStorage）
export function saveDual(storage, key, payload) {
  const env = makeEnvelope(payload);
  const raw = JSON.stringify(env);
  storage.setItem(key + '.a', raw);
  storage.setItem(key + '.b', raw);
  return env;
}

export function loadDual(storage, key) {
  for (const suffix of ['.a', '.b']) {
    const raw = storage.getItem(key + suffix);
    if (!raw) continue;
    try {
      const env = JSON.parse(raw);
      if (verifyEnvelope(env)) return migrate(env).data;
    } catch (e) { /* try next backup */ }
  }
  return null;
}

// QA contract aliases: envelope creation, dual-backup load and crash recovery.
export const createEnvelope = makeEnvelope;

export function loadWithBackup({ primary, backup } = {}) {
  for (const env of [primary, backup]) {
    if (verifyEnvelope(env)) {
      const migrated = migrate(env);
      return { data: migrated.data, version: migrated.version };
    }
  }
  throw new Error('both save copies are corrupted');
}

export function recoverAfterCrash(state) {
  if (!state || !state.dirty) return null;
  return state.lastCampfire || null;
}
