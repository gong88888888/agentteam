// 篝火面板：回血、存档、复活队友、快速回城
import { el } from './ui-dom.js';

export function createCampfire(root, bus) {
  const panel = el('div', { class: 'ui-panel ui-campfire hidden', attrs: { role: 'dialog', 'aria-label': '篝火' } });
  const actions = [
    ['回血', 'campfire:heal'],
    ['存档', 'campfire:save'],
    ['复活队友', 'campfire:revive'],
    ['快速回城', 'campfire:town']
  ];
  for (const [label, evt] of actions) {
    const btn = el('button', { class: 'btn', text: label, attrs: { type: 'button' } });
    btn.addEventListener('click', () => bus.emit(evt, {}));
    panel.appendChild(btn);
  }
  root.appendChild(panel);
  return { open() { panel.classList.remove('hidden'); }, close() { panel.classList.add('hidden'); }, destroy() { panel.remove(); } };
}
