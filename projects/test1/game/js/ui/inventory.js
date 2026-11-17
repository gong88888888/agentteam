// 背包：品质色、对比箭头、一键分解白绿
import { qualityColor, TOKENS } from './ui-tokens.js';
import { el, safeNum } from './ui-dom.js';

export function createInventory(root, bus) {
  const panel = el('div', { class: 'ui-panel ui-inventory hidden', attrs: { role: 'dialog', 'aria-label': '背包' } });
  const head = el('div', { class: 'panel-head' }, [
    el('span', { text: '背包' }),
    el('button', { class: 'btn', text: '一键分解白绿', attrs: { type: 'button' } })
  ]);
  const grid = el('div', { class: 'inv-grid' });
  panel.append(head, grid);
  root.appendChild(panel);

  head.querySelector('button').addEventListener('click', () => bus.emit('inventory:salvage', { qualities: ['white', 'green'] }));

  function render(items, equipped) {
    grid.textContent = '';
    for (const it of Array.isArray(items) ? items : []) {
      const cell = el('div', { class: 'inv-cell', attrs: { title: it.name || '' } });
      cell.style.borderColor = qualityColor(it.quality);
      cell.appendChild(el('span', { class: 'inv-name', text: it.name || '未知' }));
      const diff = safeNum(it.power, 0) - safeNum(equipped && equipped[it.slot] && equipped[it.slot].power, 0);
      if (diff !== 0) cell.appendChild(el('span', { class: diff > 0 ? 'arrow up' : 'arrow down', text: diff > 0 ? '▲' : '▼' }));
      cell.addEventListener('click', () => bus.emit('inventory:equip', { id: it.id }));
      grid.appendChild(cell);
    }
  }

  const off = bus.on('inventory:update', (p) => render(p && p.items, p && p.equipped));
  return {
    open() { panel.classList.remove('hidden'); },
    close() { panel.classList.add('hidden'); },
    render,
    destroy() { off && off(); panel.remove(); }
  };
}
