// Tiny event bus contract.
export function createBus() {
  const handlers = new Map();
  return {
    on(event, fn) {
      if (!handlers.has(event)) handlers.set(event, []);
      handlers.get(event).push(fn);
      return () => {
        const list = handlers.get(event) || [];
        handlers.set(event, list.filter((f) => f !== fn));
      };
    },
    emit(event, payload) {
      for (const fn of handlers.get(event) || []) fn(payload);
    },
  };
}

// Integration metadata: loaded and exercised by tests/integration.mjs.
export const extension = { id: "gameplay-events", version: 1, actions: ["createBus"], smoke: { action: "createBus", args: [], expectType: "object" } };
