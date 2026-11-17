// 地图面板：已探索房间、Boss 房、篝火图标
import { TOKENS } from './ui-tokens.js';
import { el, safeNum } from './ui-dom.js';

export function createMapPanel(root, bus) {
  const panel = el('div', { class: 'ui-panel ui-map hidden', attrs: { role: 'dialog', 'aria-label': '地图' } });
  const canvas = el('canvas', { attrs: { width: 480, height: 320 } });
  panel.appendChild(canvas);
  root.appendChild(panel);
  const ctx = canvas.getContext('2d');

  function render(rooms) {
    ctx.fillStyle = TOKENS.color.bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (const r of Array.isArray(rooms) ? rooms : []) {
      if (!r.explored) continue;
      ctx.fillStyle = r.type === 'boss' ? TOKENS.color.danger : r.type === 'campfire' ? TOKENS.color.gold : TOKENS.color.panelAlt;
      ctx.fillRect(safeNum(r.x, 0), safeNum(r.y, 0), 24, 18);
      ctx.strokeStyle = TOKENS.color.border;
      ctx.strokeRect(safeNum(r.x, 0), safeNum(r.y, 0), 24, 18);
    }
  }

  const off = bus.on('map:update', (p) => render(p && p.rooms));
  return { open() { panel.classList.remove('hidden'); }, close() { panel.classList.add('hidden'); }, render, destroy() { off && off(); panel.remove(); } };
}
