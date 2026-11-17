// 结算面板：本局掉落/金币/用时
import { qualityColor } from './ui-tokens.js';
import { el, safeNum } from './ui-dom.js';

export function createResults(root, bus) {
  const panel = el('div', { class: 'ui-panel ui-results hidden', attrs: { role: 'dialog', 'aria-label': '结算' } });
  const body = el('div', { class: 'results-body' });
  const back = el('button', { class: 'btn', text: '回城', attrs: { type: 'button' } });
  back.addEventListener('click', () => bus.emit('results:town', {}));
  panel.append(body, back);
  root.appendChild(panel);

  function render(data) {
    body.textContent = '';
    body.appendChild(el('div', { text: `金币 +${safeNum(data && data.gold, 0)}` }));
    body.appendChild(el('div', { text: `用时 ${safeNum(data && data.seconds, 0)}s` }));
    for (const it of (data && Array.isArray(data.drops)) ? data.drops : []) {
      const row = el('div', { class: 'drop-row', text: it.name || '装备' });
      row.style.color = qualityColor(it.quality);
      body.appendChild(row);
    }
  }

  const off = bus.on('results:show', render);
  return { open() { panel.classList.remove('hidden'); }, close() { panel.classList.add('hidden'); }, render, destroy() { off && off(); panel.remove(); } };
}
