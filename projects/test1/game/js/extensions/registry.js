// Extension registry for the game baseline.
//
// Generated modules must be registered here (through js/extensions/manifest.json)
// before they can affect the running game. A file that is merely written to
// disk is not integrated.

const entries = new Map();
const manifestState = { loaded: 0, error: "", source: "" };

export function registerExtension(def) {
  if (!def || typeof def !== "object") {
    throw new Error("extension definition must be an object");
  }
  const id = String(def.id || "").trim();
  if (!id) throw new Error("extension.id is required");
  if (entries.has(id)) throw new Error(`duplicate extension id: ${id}`);
  const normal = {
    version: 1,
    actions: [],
    ...def,
    id,
  };
  entries.set(id, normal);
  return normal;
}

export function hasExtension(id) {
  return entries.has(String(id));
}

export function listExtensions() {
  return [...entries.values()].map((def) => ({
    id: def.id,
    version: def.version,
    module: def.module || "",
    actions: Array.isArray(def.actions) ? def.actions : Object.keys(def.actions || {}),
  }));
}

export function invokeExtension(id, action, ...args) {
  const def = entries.get(String(id));
  if (!def) throw new Error(`unknown extension: ${id}`);
  let fn = null;
  if (def.actions && typeof def.actions === "object" && !Array.isArray(def.actions)) {
    fn = def.actions[action];
  }
  if (typeof fn !== "function" && def.moduleExports) {
    fn = def.moduleExports[action];
  }
  if (typeof fn !== "function" && def.api && typeof def.api[action] === "function") {
    fn = def.api[action];
  }
  if (typeof fn !== "function") {
    throw new Error(`extension ${id} has no action ${action}`);
  }
  return fn(...args);
}

export async function loadManifest(url = "./js/extensions/manifest.json") {
  manifestState.source = url;
  try {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
      manifestState.error = `manifest HTTP ${response.status}`;
      return { ...manifestState };
    }
    const data = await response.json();
    const list = Array.isArray(data) ? data : (data.extensions || []);
    for (const entry of list) {
      const moduleUrl = new URL(entry.module, document.baseURI).href;
      const mod = await import(moduleUrl);
      const def = mod.extension || mod.default;
      if (!def) {
        throw new Error(`module ${entry.module} has no extension export`);
      }
      // The module definition owns behavior; the manifest contributes address
      // and metadata only.
      registerExtension({ ...entry, ...def, moduleExports: mod, module: entry.module });
      manifestState.loaded += 1;
    }
  } catch (err) {
    manifestState.error = String(err);
  }
  return { ...manifestState };
}

export function initExtensions(api) {
  const results = [];
  for (const def of entries.values()) {
    try {
      if (typeof def.init === "function") def.init(api);
      results.push({ id: def.id, ok: true, error: "" });
    } catch (err) {
      results.push({ id: def.id, ok: false, error: String(err) });
    }
  }
  return results;
}

export function extensionState() {
  return { loaded: manifestState.loaded, error: manifestState.error,
           source: manifestState.source, extensions: listExtensions() };
}
