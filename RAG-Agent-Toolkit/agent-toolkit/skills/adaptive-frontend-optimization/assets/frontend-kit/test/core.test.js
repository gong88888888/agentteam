import test from 'node:test';
import assert from 'node:assert/strict';
import { createLatestTask, createObjectUrlPool, inspectOverflow } from '../index.js';

test('latest result wins even if old transport ignores cancellation', async () => {
  const task = createLatestTask();
  let finish, signal;
  const old = task.run(s => { signal = s; return new Promise(r => { finish = r; }); });
  assert.deepEqual(await task.run(async () => 'new'), { status: 'success', value: 'new' });
  assert.equal(signal.aborted, true);
  finish('old');
  assert.deepEqual(await old, { status: 'discarded' });
});
test('current errors propagate and later tasks still work', async () => {
  const task = createLatestTask();
  await assert.rejects(task.run(() => { throw Error('network'); }), /network/);
  assert.equal((await task.run(() => 42)).value, 42);
});
test('cancel suppresses stale rejection', async () => {
  const task = createLatestTask();
  let fail;
  const pending = task.run(() => new Promise((_, reject) => { fail = reject; }));
  task.cancel();
  fail(Error('obsolete'));
  assert.deepEqual(await pending, { status: 'discarded' });
});
test('dispose blocks new work and discards unfinished work', async () => {
  const task = createLatestTask();
  let finish;
  const pending = task.run(() => new Promise(r => { finish = r; }));
  task.dispose();
  finish(1);
  assert.equal((await pending).status, 'discarded');
  await assert.rejects(task.run(() => 2), /disposed/);
});
test('URL ownership, duplicate release and disposal', () => {
  let id = 0;
  const revoked = [];
  const pool = createObjectUrlPool({ createObjectURL: () => `blob:${++id}`, revokeObjectURL: u => revoked.push(u) });
  const first = pool.create({});
  pool.create({});
  pool.release(first); pool.release(first); pool.release('foreign');
  pool.dispose(); pool.dispose();
  assert.deepEqual(revoked, ['blob:1', 'blob:2']);
  assert.equal(pool.size, 0);
  assert.throws(() => pool.create({}), /disposed/);
});
test('URL pool clear allows reuse', () => {
  const pool = createObjectUrlPool({ createObjectURL: () => 'blob:1', revokeObjectURL() {} });
  pool.create({}); pool.clear(); pool.create({});
  assert.equal(pool.size, 1);
});
test('overflow probe distinguishes clipping and explicitly intentional scrolling', () => {
  const make = (overflowX, reason, visible = true) => ({
    id: '', tagName: 'DIV', clientWidth: 100, scrollWidth: 200,
    getClientRects: () => visible ? [{}] : [],
    getAttribute: () => reason,
    ownerDocument: { defaultView: { getComputedStyle: () => ({ overflowX }) } }
  });
  const root = make('hidden', 'not an exemption');
  root.querySelectorAll = () => [make('auto', 'Thumbnails'), make('auto', null), make('hidden', null, false)];
  assert.deepEqual(inspectOverflow(root).map(r => r.expected), [false, true, false]);
});
