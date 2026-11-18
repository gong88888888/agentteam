// Integration harness: prove an increment is loaded, invoked and asserted.
//
// Run from the game directory or via `node tests/integration.mjs`. The
// manifest is written by the project runner (or an integration task); a module
// that is not in the manifest is not integrated even if its own unit test
// passes.

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const gameDir = path.resolve(here, "..");
const manifestPath = path.join(gameDir, "js", "extensions", "manifest.json");
const result = { loaded: 0, invoked: 0, asserted: 0, extensions: [],
                 failures: [], manifest: manifestPath, skipped: false };

const resultPath = path.join(here, ".integration-result.json");

function finish(code) {
  try {
    fs.writeFileSync(resultPath, JSON.stringify(result));
  } catch (err) {
    result.failures.push({ id: "", message: `cannot write result: ${err}` });
  }
  console.log("INTEGRATION_RESULT " + JSON.stringify(result));
  process.exit(code);
}

function fail(message, id = "") {
  result.failures.push({ id, message: String(message) });
}

if (!fs.existsSync(manifestPath)) {
  result.skipped = true;
  finish(0);
}

const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
const entries = Array.isArray(manifest) ? manifest : (manifest.extensions || []);
if (entries.length === 0) {
  result.skipped = true;
  finish(0);
}

const registry = await import(pathToFileURL(
  path.join(gameDir, "js", "extensions", "registry.js")).href);

for (const entry of entries) {
  const id = String(entry.id || "");
  const moduleRel = String(entry.module || "");
  if (!id) { fail("manifest entry missing id"); continue; }
  if (!moduleRel) { fail("manifest entry missing module", id); continue; }
  const modulePath = path.resolve(gameDir, moduleRel);
  if (!modulePath.startsWith(gameDir + path.sep)) {
    fail(`module escapes game directory: ${moduleRel}`, id); continue;
  }
  if (!fs.existsSync(modulePath)) {
    fail(`module missing: ${moduleRel}`, id); continue;
  }
  let mod;
  try {
    mod = await import(pathToFileURL(modulePath).href);
  } catch (err) {
    fail(`module import failed: ${err}`, id); continue;
  }
  const def = mod.extension || mod.default || null;
  if (!def) { fail(`module has no extension export: ${moduleRel}`, id); continue; }
  if (String(def.id || "") !== id) {
    fail(`export id ${def.id} != manifest id ${id}`, id); continue;
  }
  try {
    registry.registerExtension({ ...entry, ...def, moduleExports: mod });
    result.loaded += 1;
  } catch (err) {
    fail(`register failed: ${err}`, id); continue;
  }
  const actions = Array.isArray(def.actions) ? def.actions
    : Object.keys(def.actions || {});
  if (actions.length === 0) {
    fail("extension declares no actions", id); continue;
  }
  const smoke = def.smoke || entry.smoke;
  const action = smoke?.action || actions[0];
  const args = Array.isArray(smoke?.args) ? smoke.args : [];
  let value;
  try {
    value = registry.invokeExtension(id, action, ...args);
    result.invoked += 1;
  } catch (err) {
    fail(`invoke ${action} failed: ${err}`, id); continue;
  }
  const expectedType = smoke?.expectType;
  if (expectedType && typeof value !== expectedType) {
    fail(`action ${action} returned ${typeof value}, expected ${expectedType}`, id);
    continue;
  }
  if (value === undefined && expectedType !== "undefined") {
    fail(`action ${action} returned undefined`, id);
    continue;
  }
  result.asserted += 1;
  result.extensions.push({ id, module: moduleRel, action,
                           valueType: typeof value });
}

finish(result.failures.length === 0 ? 0 : 1);
