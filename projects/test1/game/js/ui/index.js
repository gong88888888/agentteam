// UI 入口：init(rootEl, baseBus) 挂载全部增量 UI，返回销毁句柄
import { createBusAdapter } from './ui-bus.js';
import { createHud } from './hud.js';
import { createInventory } from './inventory.js';
import { createMapPanel } from './map-panel.js';
import { createShop } from './shop.js';
import { createCampfire } from './campfire.js';
import { createResults } from './results.js';
import { createMultiplayer } from './multiplayer.js';
import { createSettings } from './settings.js';
import { createTutorial } from './tutorial.js';

export function init(rootEl, baseBus) {
  if (!rootEl) throw new Error('[ui] rootEl required');
  const bus = createBusAdapter(baseBus);
  const parts = [
    createHud(rootEl, bus),
    createInventory(rootEl, bus),
    createMapPanel(rootEl, bus),
    createShop(rootEl, bus),
    createCampfire(rootEl, bus),
    createResults(rootEl, bus),
    createMultiplayer(rootEl, bus),
    createSettings(rootEl, bus),
    createTutorial(rootEl, bus)
  ];
  return {
    bus,
    destroy() { for (const p of parts) { try { p.destroy(); } catch (e) { console.error('[ui] destroy', e); } } }
  };
}
