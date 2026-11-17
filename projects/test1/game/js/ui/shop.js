// 商店面板：买药/钥匙/随机装备
import { qualityColor } from './ui-tokens.js';
import { el, safeNum } from './ui-dom.js';

export function createShop(root, bus) {
  const panel = el('div', { class: 'ui-panel ui-shop hidden', attrs: { role: 'dialog', 'aria-label': '商店' } });
  const list = el('div', { class: 'shop-list' });
  panel.appendChild(list);
  root.appendChild(panel);

  function render(goods, gold) {
    list.textContent = '';
    for (const g of Array.isArray(goods) ? goods : []) {
      const row = el('div', { class: 'shop-row' }, [
        el('span', { text: g.name || '商品' }),
        el('span', { class: 'price', text: `${safeNum(g.price, 0)}G` })
      ]);
      if (g.quality) row.style.borderLeftColor = qualityColor(g.quality);
      const btn = el('button', { class: 'btn', text: '购买', attrs: { type: 'button' } });
      btn.disabled = safeNum(gold, 0) < safeNum(g.price, 0);
      btn.addEventListener('click', () => bus.emit('shop:buy', { id: g.id }));
      row.appendChild(btn);
      list.appendChild(row);
    }
  }

  const off = bus.on('shop:update', (p) => render(p && p.goods, p && p.gold));
  return { open() { panel.classList.remove('hidden'); }, close() { panel.classList.add('hidden'); }, render, destroy() { off && off(); panel.remove(); } };
}
