// 10 分钟新手引导步骤条：移动→打怪→捡装→回城→存档
import { el } from './ui-dom.js';

const STEPS = ['移动', '打怪', '捡装', '回城', '存档'];

export function createTutorial(root, bus) {
  const bar = el('div', { class: 'ui-tutorial hidden', attrs: { role: 'status', 'aria-live': 'polite' } });
  root.appendChild(bar);
  let idx = 0;

  function render() {
    bar.textContent = '';
    STEPS.forEach((s, i) => {
      bar.appendChild(el('span', { class: i === idx ? 'step active' : i < idx ? 'step done' : 'step', text: s }));
    });
  }

  const off = bus.on('tutorial:advance', () => { idx = Math.min(idx + 1, STEPS.length - 1); render(); });
  render();
  return { show() { bar.classList.remove('hidden'); }, hide() { bar.classList.add('hidden'); }, destroy() { off && off(); bar.remove(); } };
}
