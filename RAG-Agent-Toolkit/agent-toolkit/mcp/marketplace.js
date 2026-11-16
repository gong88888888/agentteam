/**
 * MCP 工具市场（内置目录）
 * 列出可"一键安装"的第三方/示例 MCP 工具
 * 安装动作：在 registry 中注册一份 mock handler（生产环境替换为真实 stdio client）
 */
const fs   = require('fs');
const path = require('path');
const registry = require('./registry');

const INSTALLED_FILE = path.join(__dirname, '../data/mcp-installed.json');

const CATALOG = [
  {
    name: 'web.browse', icon: '🌐', category: 'web',
    title: '浏览器自动化', author: 'community',
    description: '通过 MCP 控制 Chromium 浏览器：打开网页、点击、抓取内容',
    rating: 4.8, downloads: 12500,
    handlerKind: 'echo',
    sampleInputSchema: { type: 'object', properties: { url: { type: 'string' } }, required: ['url'] }
  },
  {
    name: 'email.send', icon: '✉️', category: 'productivity',
    title: '邮件发送', author: 'community',
    description: '调用 SMTP 发送邮件，支持 HTML、附件',
    rating: 4.6, downloads: 8700,
    handlerKind: 'echo',
    sampleInputSchema: { type: 'object', properties: { to: { type: 'string' }, subject: { type: 'string' }, body: { type: 'string' } }, required: ['to', 'subject', 'body'] }
  },
  {
    name: 'db.query', icon: '🗄️', category: 'data',
    title: '数据库查询', author: 'community',
    description: '执行 SQL 查询并返回结果集（PostgreSQL / MySQL / SQLite）',
    rating: 4.7, downloads: 15300,
    handlerKind: 'echo',
    sampleInputSchema: { type: 'object', properties: { sql: { type: 'string' } }, required: ['sql'] }
  },
  {
    name: 'calendar.event', icon: '📅', category: 'productivity',
    title: '日历事件', author: 'community',
    description: '创建/查询日历事件（Google Calendar / Outlook）',
    rating: 4.5, downloads: 5200,
    handlerKind: 'echo',
    sampleInputSchema: { type: 'object', properties: { title: { type: 'string' }, when: { type: 'string' } }, required: ['title', 'when'] }
  },
  {
    name: 'code.python', icon: '🐍', category: 'dev',
    title: 'Python 代码解释器', author: 'community',
    description: '在沙箱内执行 Python 代码并返回输出（演示）',
    rating: 4.9, downloads: 22100,
    handlerKind: 'echo',
    sampleInputSchema: { type: 'object', properties: { code: { type: 'string' } }, required: ['code'] }
  },
  {
    name: 'image.generate', icon: '🎨', category: 'ai',
    title: 'AI 图片生成', author: 'community',
    description: '调用 SD/DALL·E 生成图片（演示）',
    rating: 4.7, downloads: 18900,
    handlerKind: 'echo',
    sampleInputSchema: { type: 'object', properties: { prompt: { type: 'string' } }, required: ['prompt'] }
  }
];

/** 安装态持久化 */
function _loadInstalled() {
  if (!fs.existsSync(INSTALLED_FILE)) {
    fs.writeFileSync(INSTALLED_FILE, '[]', 'utf-8');
    return [];
  }
  try { return JSON.parse(fs.readFileSync(INSTALLED_FILE, 'utf-8')); }
  catch { return []; }
}

function _saveInstalled(list) {
  fs.writeFileSync(INSTALLED_FILE, JSON.stringify(list, null, 2), 'utf-8');
}

function listCatalog() {
  const installed = new Set(_loadInstalled().map(t => t.name));
  return CATALOG.map(c => ({ ...c, installed: installed.has(c.name) }));
}

function install(name) {
  const item = CATALOG.find(c => c.name === name);
  if (!item) throw new Error(`市场中无此工具: ${name}`);

  const installed = _loadInstalled();
  if (installed.some(t => t.name === name)) return { ok: true, alreadyInstalled: true };

  // mock handler：回显输入并附带"模拟执行"标记
  registry.register({
    name:        item.name,
    description: item.description + '（演示模式：未连接真实后端）',
    category:    item.category,
    icon:        item.icon,
    inputSchema: item.sampleInputSchema,
    source:      'market',
    version:     '1.0.0',
    handler: async (input) => ({
      simulated: true,
      tool:      item.name,
      input,
      note:      '此工具来自 MCP 市场（演示模式）。生产请替换为真实 stdio MCP server 连接。'
    })
  });

  installed.push({ name, installedAt: new Date().toISOString() });
  _saveInstalled(installed);
  return { ok: true };
}

function uninstall(name) {
  const installed = _loadInstalled();
  const newList = installed.filter(t => t.name !== name);
  if (newList.length === installed.length) return { ok: false, message: '未安装' };
  _saveInstalled(newList);
  registry.unregister(name);
  return { ok: true };
}

function restoreInstalled() {
  const installed = _loadInstalled();
  for (const { name } of installed) {
    const item = CATALOG.find(c => c.name === name);
    if (item && !registry.has(name)) {
      try { install(name); } catch { /* 忽略 */ }
    }
  }
}

module.exports = { CATALOG, listCatalog, install, uninstall, restoreInstalled };
