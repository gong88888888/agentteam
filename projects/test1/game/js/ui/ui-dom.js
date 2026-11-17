// DOM 工具：安全创建元素、文本转义、整数像素对齐
import { TOKENS } from './ui-tokens.js';

export function el(tag, opts = {}, children = []) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = String(opts.text);
  if (opts.style) Object.assign(node.style, opts.style);
  if (opts.attrs) for (const [k, v] of Object.entries(opts.attrs)) node.setAttribute(k, String(v));
  for (const c of children) if (c) node.appendChild(c);
  return node;
}

export function px(n) {
  return `${Math.round(n / TOKENS.scale) * TOKENS.scale}px`;
}

export function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, Number.isFinite(v) ? v : lo));
}

export function safeNum(v, d = 0) {
  return Number.isFinite(v) ? v : d;
}
