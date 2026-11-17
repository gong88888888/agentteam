// 设置：关闭震屏 / 减少粒子（低配降级）
import { el } from './ui-dom.js';

export function createSettings(root, bus) {
  const panel = el('div', { class: 'ui-panel ui-settings hidden', attrs: { role: 'dialog', 'aria-label': '设置' } });
  const opts = [
    ['关闭震屏', 'settings:shake'],
    ['减少粒子', 'settings:particles']
  ];
  for (const [label, evt] of opts) {
    const input = el('input', { attrs: { type: 'checkbox' } });
    input.addEventListener('change', () => bus.emit(evt, { enabled: input.checked }));
    panel.appendChild(el('label', { class: 'setting-row' }, [input, el('span', { text: label })]));
  }
  root.appendChild(panel);
  return { open() { panel.classList.remove('hidden'); }, close() { panel.classList.add('hidden'); }, destroy() { panel.remove(); } };
}
