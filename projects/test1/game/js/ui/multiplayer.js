// 多人面板：本地同屏加入提示 + 局域网房间码（P1 占位）
import { el } from './ui-dom.js';

export function createMultiplayer(root, bus) {
  const panel = el('div', { class: 'ui-panel ui-multi hidden', attrs: { role: 'dialog', 'aria-label': '多人' } });
  const hint = el('div', { class: 'multi-hint', text: '本地同屏：按手柄 A 加入' });
  const codeInput = el('input', { class: 'input', attrs: { placeholder: '房间码（P1）', maxlength: 8 } });
  const joinBtn = el('button', { class: 'btn', text: '加入', attrs: { type: 'button' } });
  joinBtn.addEventListener('click', () => bus.emit('multi:join', { code: codeInput.value.trim() }));
  panel.append(hint, codeInput, joinBtn);
  root.appendChild(panel);
  return { open() { panel.classList.remove('hidden'); }, close() { panel.classList.add('hidden'); }, destroy() { panel.remove(); } };
}
