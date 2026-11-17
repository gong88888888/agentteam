// 轻量事件总线适配层：优先复用基座 bus，缺失时降级为本地实现。
// 仅做转发，不持有游戏状态。
const local = new Map();

function localOn(evt, fn) {
  if (!local.has(evt)) local.set(evt, new Set());
  local.get(evt).add(fn);
  return () => local.get(evt) && local.get(evt).delete(fn);
}
function localEmit(evt, payload) {
  const set = local.get(evt);
  if (set) for (const fn of set) { try { fn(payload); } catch (e) { console.error('[ui-bus]', evt, e); } }
}

export function createBusAdapter(baseBus) {
  const hasBase = baseBus && typeof baseBus.on === 'function' && typeof baseBus.emit === 'function';
  return {
    on: (evt, fn) => (hasBase ? baseBus.on(evt, fn) : localOn(evt, fn)),
    emit: (evt, payload) => (hasBase ? baseBus.emit(evt, payload) : localEmit(evt, payload)),
    getSnapshot: () => (baseBus && typeof baseBus.getSnapshot === 'function' ? baseBus.getSnapshot() : {})
  };
}
