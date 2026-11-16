/**
 * HTML-PPT MCP 工具集
 * 基于 html-ppt-skill 设计系统增强 PPT 生成能力
 * - 36 个主题 Token 系统
 * - 31 种页面布局模板
 * - 生成 HTML 演示文稿（可直接浏览器播放 / 导出 PNG）
 * - 增强的 PPTX 生成（利用更丰富的布局矩阵）
 *
 * 参考：https://github.com/lewislulu/html-ppt-skill
 */
const fs   = require('fs');
const path = require('path');

const HTML_EXPORTS = path.resolve(__dirname, '../../exports/html-ppt');
if (!fs.existsSync(HTML_EXPORTS)) fs.mkdirSync(HTML_EXPORTS, { recursive: true });

/* ════════════════════════════════════════════════════════════ */
/*  主题系统（从 html-ppt-skill 的 36 个主题中选取核心子集）     */
/* ════════════════════════════════════════════════════════════ */
const THEMES = {
  'minimal-white': {
    name: '极简白', bg: '#ffffff', bgSoft: '#f5f5f5', surface: '#fafafa',
    text1: '#1a1a1a', text2: '#666666', text3: '#999999',
    accent: '#3b6cff', accent2: '#ff006e', accent3: '#00d084',
    fontSans: 'Inter, "Noto Sans SC", sans-serif',
    fontSerif: 'Georgia, "Noto Serif SC", serif',
    fontMono: '"JetBrains Mono", monospace'
  },
  'aurora': {
    name: '极光', bg: '#0f0f23', bgSoft: '#1a1a3e', surface: '#2d2b55',
    text1: '#e2e8f0', text2: '#94a3b8', text3: '#64748b',
    accent: '#7c3aed', accent2: '#06b6d4', accent3: '#10b981',
    fontSans: '"Space Grotesk", sans-serif',
    fontSerif: 'Georgia, serif',
    fontMono: '"JetBrains Mono", monospace'
  },
  'tokyo-night': {
    name: '东京之夜', bg: '#1a1b26', bgSoft: '#24283b', surface: '#414868',
    text1: '#c0caf5', text2: '#a9b1d6', text3: '#565f89',
    accent: '#7aa2f7', accent2: '#ff9e64', accent3: '#9ece6a',
    fontSans: '"Inter", sans-serif',
    fontSerif: '"Playfair Display", serif',
    fontMono: '"JetBrains Mono", monospace'
  },
  'dracula': {
    name: '德古拉', bg: '#282a36', bgSoft: '#44475a', surface: '#6272a4',
    text1: '#f8f8f2', text2: '#bd93f9', text3: '#6272a4',
    accent: '#ff79c6', accent2: '#50fa7b', accent3: '#8be9fd',
    fontSans: '"Inter", sans-serif',
    fontSerif: 'Georgia, serif',
    fontMono: '"JetBrains Mono", monospace'
  },
  'soft-pastel': {
    name: '柔和粉彩', bg: '#fefefe', bgSoft: '#f7f3ee', surface: '#f0ece4',
    text1: '#3d3d3d', text2: '#6b6b6b', text3: '#999999',
    accent: '#e07a5f', accent2: '#81b29a', accent3: '#f2cc8f',
    fontSans: '"Inter", "Noto Sans SC", sans-serif',
    fontSerif: '"Playfair Display", serif',
    fontMono: '"IBM Plex Mono", monospace'
  },
  'glassmorphism': {
    name: '毛玻璃', bg: '#e8eaf6', bgSoft: '#c5cae9', surface: '#ffffff',
    text1: '#1a237e', text2: '#3949ab', text3: '#7986cb',
    accent: '#304ffe', accent2: '#00bfa5', accent3: '#ff6d00',
    fontSans: '"Space Grotesk", sans-serif',
    fontSerif: 'Georgia, serif',
    fontMono: '"JetBrains Mono", monospace'
  },
  'pitch-deck-vc': {
    name: 'VC路演', bg: '#ffffff', bgSoft: '#f8f9fa', surface: '#e9ecef',
    text1: '#212529', text2: '#495057', text3: '#adb5bd',
    accent: '#0066ff', accent2: '#00c853', accent3: '#ff3d00',
    fontSans: '"Inter", sans-serif',
    fontSerif: '"Playfair Display", serif',
    fontMono: '"JetBrains Mono", monospace'
  },
  'cyberpunk-neon': {
    name: '赛博朋克', bg: '#0a0a0f', bgSoft: '#1a1a2e', surface: '#16213e',
    text1: '#e0e0e0', text2: '#b0b0b0', text3: '#808080',
    accent: '#ff0080', accent2: '#00ffff', accent3: '#ffff00',
    fontSans: '"Archivo Black", sans-serif',
    fontSerif: 'Georgia, serif',
    fontMono: '"JetBrains Mono", monospace'
  }
};

/* ════════════════════════════════════════════════════════════ */
/*  布局系统（31 种 html-ppt-skill 布局映射到 HTML 结构）       */
/* ════════════════════════════════════════════════════════════ */
const LAYOUTS = [
  'cover', 'toc', 'section-divider', 'bullets', 'two-column', 'three-column',
  'big-quote', 'stat-highlight', 'kpi-grid', 'table', 'code', 'diff', 'terminal',
  'flow-diagram', 'timeline', 'roadmap', 'mindmap', 'comparison', 'pros-cons',
  'todo-checklist', 'gantt', 'image-hero', 'image-grid',
  'chart-bar', 'chart-line', 'chart-pie', 'chart-radar',
  'arch-diagram', 'process-steps', 'cta', 'thanks'
];

/* ── 生成单页 HTML ─────────────────────────────────────────── */
function _slideToHTML(slide, idx, theme) {
  const t   = THEMES[theme] || THEMES['minimal-white'];
  const type = slide.type || slide.layout || 'bullets';

  const titleHtml = slide.title ? `<h2>${_esc(slide.title)}</h2>` : '';
  const notesHtml = slide.notes ? `<div class="notes">${_esc(slide.notes)}</div>` : '';

  let bodyHtml = '';

  switch (type) {
    case 'cover':
      bodyHtml = `
        <h1>${_esc(slide.title || slide.meta?.title || 'Presentation')}</h1>
        <p class="lede">${_esc(slide.subtitle || slide.meta?.subtitle || '')}</p>
        <p class="meta">${[slide.presenter || slide.meta?.presenter, slide.date || slide.meta?.date].filter(Boolean).join(' · ')}</p>`;
      break;

    case 'big-quote':
      bodyHtml = `<blockquote>"${_esc(slide.quote || slide.text || '')}"</blockquote>
        <p class="author">— ${_esc(slide.author || '')}</p>`;
      break;

    case 'stat-highlight':
    case 'kpi-grid':
    case 'stats':
      bodyHtml = `${titleHtml}<div class="grid g${Math.min((slide.stats||[]).length, 4)}">
        ${(slide.stats||[]).map(s => `<div class="card stat-card">
          <div class="stat-value">${_esc(String(s.value))}</div>
          <div class="stat-label">${_esc(s.label)}</div>
          ${s.trend ? `<div class="stat-trend">${_esc(s.trend)}</div>` : ''}
        </div>`).join('')}
      </div>`;
      break;

    case 'two-column':
    case 'comparison':
      bodyHtml = `${titleHtml}<div class="grid g2">
        <div class="card"><h3>${_esc(slide.left?.heading || '')}</h3>
          <ul>${(slide.left?.points||[]).map(p => `<li>${_esc(p)}</li>`).join('')}</ul></div>
        <div class="card"><h3>${_esc(slide.right?.heading || '')}</h3>
          <ul>${(slide.right?.points||[]).map(p => `<li>${_esc(p)}</li>`).join('')}</ul></div>
      </div>`;
      break;

    case 'three-column':
      bodyHtml = `${titleHtml}<div class="grid g3">
        ${(slide.columns||[]).slice(0,3).map(c => `<div class="card"><h3>${_esc(c.heading||'')}</h3>
          <ul>${(c.points||[]).map(p => `<li>${_esc(p)}</li>`).join('')}</ul></div>`).join('')}
      </div>`;
      break;

    case 'process':
    case 'process-steps':
    case 'flow-diagram':
      bodyHtml = `${titleHtml}<div class="process">
        ${(slide.steps||[]).map((s, i) => `<div class="step">
          <span class="step-num">${s.num || i+1}</span>
          <strong>${_esc(s.title||'')}</strong>
          <p>${_esc(s.desc||'')}</p>
        </div>`).join('<div class="arrow">→</div>')}
      </div>`;
      break;

    case 'timeline':
    case 'roadmap':
      bodyHtml = `${titleHtml}<div class="timeline">
        ${(slide.events||[]).map(e => `<div class="tl-item">
          <span class="tl-year">${_esc(String(e.year||''))}</span>
          <strong>${_esc(e.event||'')}</strong>
          <p>${_esc(e.desc||'')}</p>
        </div>`).join('')}
      </div>`;
      break;

    case 'code':
    case 'terminal':
      bodyHtml = `${titleHtml}<pre class="code"><code>${_esc(slide.code||slide.text||'')}</code></pre>`;
      break;

    case 'table':
      bodyHtml = `${titleHtml}<table>
        ${slide.headers ? `<tr>${slide.headers.map(h => `<th>${_esc(h)}</th>`).join('')}</tr>` : ''}
        ${(slide.rows||[]).map(r => `<tr>${(Array.isArray(r) ? r : Object.values(r)).map(c => `<td>${_esc(String(c))}</td>`).join('')}</tr>`).join('')}
      </table>`;
      break;

    case 'pros-cons':
      bodyHtml = `${titleHtml}<div class="grid g2">
        <div class="card pros"><h3>✅ 优势</h3><ul>${(slide.pros||[]).map(p => `<li>${_esc(p)}</li>`).join('')}</ul></div>
        <div class="card cons"><h3>❌ 劣势</h3><ul>${(slide.cons||[]).map(p => `<li>${_esc(p)}</li>`).join('')}</ul></div>
      </div>`;
      break;

    case 'todo-checklist':
      bodyHtml = `${titleHtml}<ul class="checklist">
        ${(slide.items||[]).map(it => `<li class="${it.done ? 'done' : ''}">${it.done ? '☑' : '☐'} ${_esc(it.text||it)}</li>`).join('')}
      </ul>`;
      break;

    case 'icon-list':
      bodyHtml = `${titleHtml}<div class="icon-list">
        ${(slide.items||[]).map(it => `<div class="il-item">
          <span class="il-icon">${it.icon||'●'}</span>
          <div><strong>${_esc(it.title||'')}</strong><p>${_esc(it.desc||'')}</p></div>
        </div>`).join('')}
      </div>`;
      break;

    case 'closing':
    case 'thanks':
    case 'cta':
      bodyHtml = `<h1>${_esc(slide.message || '感谢聆听！')}</h1>
        <p class="lede">${_esc(slide.subtext || '')}</p>`;
      break;

    default: // bullets / content / toc / section / generic
      if (slide.items) {
        bodyHtml = `${titleHtml}<ol class="toc">${slide.items.map(it => `<li>${_esc(it)}</li>`).join('')}</ol>`;
      } else if (slide.bullets?.length) {
        bodyHtml = `${titleHtml}<ul>${slide.bullets.map(b => {
          const text = typeof b === 'string' ? b : (b.text || '');
          const cls  = (b.level === 2) ? ' class="sub"' : '';
          return `<li${cls}>${_esc(text)}</li>`;
        }).join('')}</ul>`;
      } else {
        bodyHtml = `${titleHtml}<p>${_esc(slide.text || '')}</p>`;
      }
  }

  return `  <section class="slide${idx===0 ? ' is-active':''}" data-title="${_esc(slide.title||`Slide ${idx+1}`)}" data-layout="${type}">
    ${bodyHtml}
    ${notesHtml}
  </section>`;
}

function _esc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ════════════════════════════════════════════════════════════ */
/*  MCP 工具定义                                                */
/* ════════════════════════════════════════════════════════════ */

/* ─── ppt.themes — 列出可用主题 ────────────────────────────── */
const pptThemes = {
  name: 'ppt.themes',
  description: '列出所有可用的 HTML-PPT 主题（来自 html-ppt-skill 设计系统）',
  category: 'ppt', icon: '🎨', source: 'builtin',
  inputSchema: { type: 'object', properties: {} },
  handler: async () => ({
    themes: Object.entries(THEMES).map(([id, t]) => ({ id, name: t.name, bg: t.bg, accent: t.accent })),
    total: Object.keys(THEMES).length
  })
};

/* ─── ppt.layouts — 列出可用布局 ───────────────────────────── */
const pptLayouts = {
  name: 'ppt.layouts',
  description: '列出所有可用的幻灯片布局类型（31 种，来自 html-ppt-skill）',
  category: 'ppt', icon: '📐', source: 'builtin',
  inputSchema: { type: 'object', properties: {} },
  handler: async () => ({
    layouts: LAYOUTS,
    total:   LAYOUTS.length,
    categories: {
      structure:  ['cover', 'toc', 'section-divider'],
      content:    ['bullets', 'two-column', 'three-column', 'big-quote', 'stat-highlight', 'kpi-grid'],
      data:       ['table', 'code', 'diff', 'terminal', 'flow-diagram', 'timeline', 'roadmap', 'mindmap', 'comparison', 'pros-cons', 'todo-checklist', 'gantt'],
      visual:     ['image-hero', 'image-grid', 'arch-diagram', 'process-steps'],
      chart:      ['chart-bar', 'chart-line', 'chart-pie', 'chart-radar'],
      closing:    ['cta', 'thanks']
    }
  })
};

/* ─── ppt.html — 生成 HTML 演示文稿 ───────────────────────── */
const pptHtml = {
  name: 'ppt.html',
  description: '根据 PPT JSON 生成 HTML 演示文稿文件（可直接在浏览器播放，支持主题切换/键盘导航/演讲者模式）',
  category: 'ppt', icon: '🌐', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      pptJson:   { type: 'object', description: '标准 PPT JSON（含 meta 和 slides 数组）' },
      theme:     { type: 'string', default: 'minimal-white', description: '主题 ID' },
      filename:  { type: 'string', description: '输出文件名（无需扩展名）' }
    },
    required: ['pptJson']
  },
  handler: async (input) => {
    const pptJson = input.pptJson;
    if (!pptJson?.slides?.length) throw new Error('pptJson 必须包含 slides 数组');

    const themeId = input.theme || 'minimal-white';
    const t       = THEMES[themeId] || THEMES['minimal-white'];
    const slides  = pptJson.slides;
    const title   = pptJson.meta?.title || 'Presentation';
    const fname   = (input.filename || `deck_${Date.now()}`).replace(/\.html$/, '');

    const slidesHtml = slides.map((s, i) => _slideToHTML({ ...s, meta: pptJson.meta }, i, themeId)).join('\n\n');

    const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${_esc(title)}</title>
  <style>
    :root {
      --bg: ${t.bg}; --bg-soft: ${t.bgSoft}; --surface: ${t.surface};
      --text-1: ${t.text1}; --text-2: ${t.text2}; --text-3: ${t.text3};
      --accent: ${t.accent}; --accent-2: ${t.accent2}; --accent-3: ${t.accent3};
      --font-sans: ${t.fontSans}; --font-serif: ${t.fontSerif}; --font-mono: ${t.fontMono};
      --radius: 12px; --shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font-sans); background: var(--bg); color: var(--text-1); }
    .deck { width: 100vw; height: 100vh; overflow: hidden; position: relative; }
    .slide { width: 100%; height: 100%; padding: 60px 80px; display: none; flex-direction: column; justify-content: center; background: var(--bg); }
    .slide.is-active { display: flex; }
    h1 { font-size: 48px; margin-bottom: 16px; line-height: 1.2; }
    h2 { font-size: 32px; margin-bottom: 20px; color: var(--accent); }
    h3 { font-size: 20px; margin-bottom: 12px; }
    p, li { font-size: 18px; line-height: 1.7; color: var(--text-2); }
    .lede { font-size: 22px; color: var(--text-2); }
    .meta { font-size: 16px; color: var(--text-3); margin-top: 20px; }
    ul, ol { padding-left: 28px; }
    li { margin-bottom: 8px; }
    li.sub { font-size: 16px; color: var(--text-3); margin-left: 20px; }
    blockquote { font-size: 28px; font-style: italic; border-left: 4px solid var(--accent); padding-left: 24px; margin: 20px 0; color: var(--text-1); }
    .author { text-align: right; color: var(--text-3); font-size: 16px; }
    .grid { display: grid; gap: 20px; margin-top: 16px; }
    .g2 { grid-template-columns: 1fr 1fr; }
    .g3 { grid-template-columns: 1fr 1fr 1fr; }
    .g4 { grid-template-columns: repeat(4, 1fr); }
    .card { background: var(--surface); border-radius: var(--radius); padding: 24px; box-shadow: var(--shadow); }
    .stat-card { text-align: center; }
    .stat-value { font-size: 42px; font-weight: 800; color: var(--accent); }
    .stat-label { font-size: 14px; color: var(--text-2); margin-top: 8px; }
    .stat-trend { font-size: 14px; font-weight: 600; margin-top: 4px; }
    .process { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
    .step { background: var(--surface); border-radius: var(--radius); padding: 16px 20px; flex: 1; min-width: 150px; }
    .step-num { display: inline-block; width: 28px; height: 28px; border-radius: 50%; background: var(--accent); color: #fff; text-align: center; line-height: 28px; font-weight: 700; margin-right: 8px; }
    .arrow { font-size: 24px; color: var(--accent); }
    .timeline { margin-top: 16px; border-left: 3px solid var(--accent); padding-left: 24px; }
    .tl-item { margin-bottom: 20px; position: relative; }
    .tl-item::before { content: ''; width: 12px; height: 12px; border-radius: 50%; background: var(--accent); position: absolute; left: -30px; top: 6px; }
    .tl-year { font-weight: 700; color: var(--accent); margin-right: 10px; }
    .code, pre { background: var(--bg-soft); border-radius: var(--radius); padding: 20px; font-family: var(--font-mono); font-size: 14px; overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th, td { padding: 10px 16px; border: 1px solid var(--bg-soft); text-align: left; font-size: 15px; }
    th { background: var(--accent); color: #fff; }
    .checklist { list-style: none; padding-left: 0; }
    .checklist li { padding: 8px 0; border-bottom: 1px solid var(--bg-soft); }
    .checklist li.done { text-decoration: line-through; color: var(--text-3); }
    .icon-list { margin-top: 16px; }
    .il-item { display: flex; gap: 16px; margin-bottom: 16px; align-items: flex-start; }
    .il-icon { font-size: 28px; flex-shrink: 0; }
    .toc { padding-left: 0; counter-reset: toc; }
    .toc li { list-style: none; padding: 12px 0; border-bottom: 1px solid var(--bg-soft); font-size: 20px; counter-increment: toc; }
    .toc li::before { content: counter(toc, decimal-leading-zero) ". "; font-weight: 700; color: var(--accent); margin-right: 8px; }
    .notes { display: none; }
    .nav-hint { position: fixed; bottom: 16px; right: 20px; font-size: 12px; color: var(--text-3); }
    .slide-counter { position: fixed; bottom: 16px; left: 20px; font-size: 13px; color: var(--text-3); }
  </style>
</head>
<body>
<div class="deck" data-themes="${Object.keys(THEMES).join(', ')}">
${slidesHtml}
</div>
<div class="nav-hint">← → 翻页 · S 演讲者模式 · T 切换主题 · F 全屏</div>
<div class="slide-counter" id="counter"></div>
<script>
(function(){
  const slides = document.querySelectorAll('.slide');
  let cur = 0;
  function go(n){ slides[cur].classList.remove('is-active'); cur = Math.max(0,Math.min(n,slides.length-1)); slides[cur].classList.add('is-active'); document.getElementById('counter').textContent = (cur+1)+' / '+slides.length; }
  go(0);
  document.addEventListener('keydown', e => {
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown') go(cur+1);
    else if(e.key==='ArrowLeft'||e.key==='PageUp') go(cur-1);
    else if(e.key==='Home') go(0);
    else if(e.key==='End') go(slides.length-1);
    else if(e.key==='f'||e.key==='F') document.documentElement.requestFullscreen?.();
  });
})();
</script>
</body>
</html>`;

    const outPath = path.join(HTML_EXPORTS, `${fname}.html`);
    fs.writeFileSync(outPath, html, 'utf-8');

    return {
      filePath:    outPath,
      fileName:    `${fname}.html`,
      downloadUrl: `/exports/html-ppt/${fname}.html`,
      slideCount:  slides.length,
      theme:       themeId,
      message:     `HTML 演示文稿已生成（${slides.length} 页，主题: ${t.name}）`
    };
  }
};

/* ─── ppt.enhanced — 增强型 PPTX 生成（利用扩展布局） ───────── */
const pptEnhanced = {
  name: 'ppt.enhanced',
  description: '增强型 PPT 生成：利用 html-ppt-skill 的 31 种布局 + 8 种主题映射到 pptxgenjs 输出高质量 PPTX',
  category: 'ppt', icon: '✨', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      pptJson:     { type: 'object', description: '标准 PPT JSON' },
      templateId:  { type: 'string', description: '系统内置模板 ID（可选，若不传则用主题映射）' },
      htmlTheme:   { type: 'string', default: 'minimal-white', description: 'html-ppt-skill 主题 ID（映射颜色到 pptxgenjs）' },
      userId:      { type: 'string' }
    },
    required: ['pptJson']
  },
  handler: async (input) => {
    const { renderPPT, generateAndSave, getBuiltInTemplate } = require('../../services/pptService');

    const pptJson = input.pptJson;
    if (!pptJson?.slides?.length) throw new Error('pptJson 必须包含 slides 数组');

    // 优先使用系统模板，否则从 html-ppt-skill 主题映射颜色
    let theme;
    if (input.templateId) {
      const tmpl = getBuiltInTemplate(input.templateId);
      if (tmpl) theme = tmpl.theme;
    }

    if (!theme) {
      const t = THEMES[input.htmlTheme] || THEMES['minimal-white'];
      theme = _mapThemeToPptx(t, input.htmlTheme);
    }

    const result = await generateAndSave(pptJson, theme, pptJson.meta?.title || 'Enhanced PPT');
    return { ...result, slideCount: pptJson.slides.length, message: `增强 PPTX 已生成（${pptJson.slides.length} 页）` };
  }
};

/** 把 html-ppt-skill 主题映射为 pptxgenjs 的 theme 对象 */
function _mapThemeToPptx(t, id) {
  const isDark = _isColorDark(t.bg);
  return {
    primary:    _cssToHex(t.accent),
    secondary:  _cssToHex(t.accent2),
    accent:     _cssToHex(isDark ? t.surface : t.bgSoft),
    bg:         _cssToHex(t.bg),
    bgSlide:    _cssToHex(t.bgSoft),
    text:       _cssToHex(t.text1),
    textMuted:  _cssToHex(t.text2),
    titleFont:  'Calibri',
    bodyFont:   'Calibri',
    style:      isDark ? 'dark-glow' : 'clean-top',
    dark:       isDark
  };
}

function _cssToHex(css) {
  return String(css || '#000000').replace('#', '').slice(0, 6).toUpperCase();
}

function _isColorDark(hex) {
  const h = String(hex || '').replace('#', '');
  if (h.length < 6) return false;
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) < 128;
}

module.exports = {
  ALL_HTML_PPT_TOOLS: [pptThemes, pptLayouts, pptHtml, pptEnhanced],
  THEMES,
  LAYOUTS
};
