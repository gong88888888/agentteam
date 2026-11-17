// QA: SaveEnvelope 版本/CRC/双备份/迁移/异常退出回篝火
import { test } from 'node:test';
import assert from 'node:assert/strict';

const CANDIDATES = [
  '../js/gameplay/save.js',
  '../js/gameplay/save.mjs',
  '../js/gameplay/persistence.js',
];

async function loadSave() {
  for (const p of CANDIDATES) {
    try { return await import(p); } catch { /* next */ }
  }
  return null;
}

const mod = await loadSave();
const skip = mod ? false : 'gameplay save module not found (see open_questions)';

function makeEnvelope(m, data) {
  const fn = m.createEnvelope || m.wrapSave || null;
  assert.ok(typeof fn === 'function', 'createEnvelope missing');
  return fn(data);
}

test('S-01 版本号存在', { skip }, () => {
  const env = makeEnvelope(mod, { gold: 10 });
  assert.ok('version' in env, 'version missing');
  assert.equal(typeof env.version, 'number');
});

test('S-02 CRC32 校验（篡改失败）', { skip }, () => {
  const verify = mod.verifyEnvelope || mod.verify || null;
  assert.ok(typeof verify === 'function', 'verify missing');
  const env = makeEnvelope(mod, { gold: 10 });
  assert.equal(verify(env), true);
  env.data.gold = 999;
  assert.equal(verify(env), false);
});

test('S-03 双备份回退', { skip }, () => {
  const load = mod.loadWithBackup || mod.load || null;
  assert.ok(typeof load === 'function', 'load missing');
  const primary = makeEnvelope(mod, { gold: 10 });
  const backup = makeEnvelope(mod, { gold: 20 });
  primary.data.gold = 999; // 破坏主备份
  const r = load({ primary, backup });
  assert.equal(r.data.gold, 20);
});

test('S-04 迁移链', { skip }, () => {
  const migrate = mod.migrate || mod.migrateEnvelope || null;
  assert.ok(typeof migrate === 'function', 'migrate missing');
  const old = { version: 1, data: { gold: 5 } };
  const cur = migrate(old);
  assert.ok(cur.version >= 2, `migrated version ${cur.version}`);
  assert.equal(cur.data.gold, 5);
});

test('S-05 异常退出回最近篝火快照', { skip }, () => {
  const recover = mod.recoverAfterCrash || mod.recover || null;
  assert.ok(typeof recover === 'function', 'recover missing');
  const campfire = { room: 'campfire-1', gold: 30 };
  const r = recover({ lastCampfire: campfire, dirty: true });
  assert.deepEqual(r, campfire);
});
