// UI Design Tokens —— 与 docs/design/ui-spec.md 对齐，单一来源
export const TOKENS = Object.freeze({
  grid: 16,
  scale: 2,
  base: { width: 1280, height: 720 },
  color: {
    bg: '#12141c',
    panel: '#1e2230',
    panelAlt: '#2a3042',
    border: '#3d4660',
    text: '#e8ecf5',
    textDim: '#9aa4bd',
    hp: '#e5484d',
    mp: '#3b82f6',
    gold: '#f5c542',
    interact: '#4ade80',
    danger: '#f97316',
    quality: { white: '#d6d9e0', green: '#4ade80', blue: '#3b82f6', purple: '#a855f7', orange: '#f97316' }
  },
  font: { xs: 12, sm: 14, md: 16, lg: 20, xl: 28 },
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 },
  radius: { sm: 4, md: 8, lg: 12 },
  motion: { fast: 120, normal: 200, slow: 320, ease: 'cubic-bezier(0.2,0.8,0.2,1)' },
  z: { hud: 100, panel: 200, modal: 300, toast: 400 }
});

export function qualityColor(q) {
  return TOKENS.color.quality[q] || TOKENS.color.quality.white;
}
