/**
 * MCP 工具注册中心
 * - 注册标准 MCP 工具（含 name / description / inputSchema / handler）
 * - 支持启用/禁用、配置参数
 * - 持久化：data/mcp-tools.json（仅存元数据，handler 在内存中）
 */
const fs   = require('fs');
const path = require('path');

const TOOLS_FILE = path.join(__dirname, '../data/mcp-tools.json');

class McpRegistry {
  constructor() {
    this.tools  = new Map();   // name → { name, description, inputSchema, category, handler, enabled, config }
    this.meta   = this._loadMeta();
  }

  /* ── 元数据持久化 ────────────────────────────────────── */
  _loadMeta() {
    if (!fs.existsSync(TOOLS_FILE)) {
      this._saveMeta({});
      return {};
    }
    try { return JSON.parse(fs.readFileSync(TOOLS_FILE, 'utf-8')); }
    catch { return {}; }
  }

  _saveMeta(data = this.meta) {
    fs.writeFileSync(TOOLS_FILE, JSON.stringify(data, null, 2), 'utf-8');
  }

  /* ── 工具注册 ───────────────────────────────────────── */
  register(tool) {
    if (!tool || !tool.name) throw new Error('MCP 工具必须有 name');
    if (typeof tool.handler !== 'function') throw new Error(`工具 ${tool.name} 必须提供 handler 函数`);

    const meta = this.meta[tool.name] || {};
    const enriched = {
      name:        tool.name,
      description: tool.description || '',
      inputSchema: tool.inputSchema || { type: 'object', properties: {} },
      category:    tool.category    || 'general',
      icon:        tool.icon        || '🛠️',
      handler:     tool.handler,
      enabled:     meta.enabled !== false,           // 默认启用
      config:      meta.config || tool.defaultConfig || {},
      version:     tool.version || '1.0.0',
      source:      tool.source  || 'builtin'         // builtin / custom / market
    };

    this.tools.set(tool.name, enriched);

    // 同步元数据
    this.meta[tool.name] = {
      enabled: enriched.enabled,
      config:  enriched.config,
      source:  enriched.source,
      version: enriched.version
    };
    this._saveMeta();
    return enriched;
  }

  unregister(name) {
    const ok = this.tools.delete(name);
    if (ok && this.meta[name]?.source !== 'builtin') {
      delete this.meta[name];
      this._saveMeta();
    }
    return ok;
  }

  /* ── 查询 ──────────────────────────────────────────── */
  get(name) { return this.tools.get(name) || null; }
  has(name) { return this.tools.has(name); }

  list({ enabledOnly = false, category = null } = {}) {
    let arr = [...this.tools.values()];
    if (enabledOnly) arr = arr.filter(t => t.enabled);
    if (category)    arr = arr.filter(t => t.category === category);
    return arr.map(t => this._safe(t));
  }

  /* ── 启用 / 禁用 / 配置 ────────────────────────────── */
  setEnabled(name, enabled) {
    const t = this.tools.get(name);
    if (!t) return false;
    t.enabled = !!enabled;
    if (!this.meta[name]) this.meta[name] = {};
    this.meta[name].enabled = t.enabled;
    this._saveMeta();
    return true;
  }

  setConfig(name, config) {
    const t = this.tools.get(name);
    if (!t) return false;
    t.config = { ...t.config, ...config };
    if (!this.meta[name]) this.meta[name] = {};
    this.meta[name].config = t.config;
    this._saveMeta();
    return true;
  }

  /* ── 内部：去掉 handler 后的安全对象（用于响应） ───── */
  _safe(t) {
    const { handler, ...rest } = t;
    return rest;
  }
}

module.exports = new McpRegistry();
