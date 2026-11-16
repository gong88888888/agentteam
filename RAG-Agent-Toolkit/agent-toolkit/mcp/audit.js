/**
 * MCP 审计日志
 * 记录每次工具调用：用户、工具、入参、出参、耗时、状态
 */
const fs   = require('fs');
const path = require('path');

const AUDIT_DIR  = path.join(__dirname, '../../logs/mcp');
const AUDIT_FILE = path.join(AUDIT_DIR, 'audit.log');
const MAX_LINES  = 5000;          // 内存中保留的最近调用数

if (!fs.existsSync(AUDIT_DIR)) fs.mkdirSync(AUDIT_DIR, { recursive: true });

class McpAudit {
  constructor() {
    this.recent = [];             // 最近的调用（内存）
  }

  /** 记录一次工具调用 */
  record(entry) {
    const safe = {
      id:        entry.id || `a_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      userId:    entry.userId || null,
      username:  entry.username || null,
      tool:      entry.tool,
      input:     this._truncate(entry.input),
      output:    this._truncate(entry.output),
      status:    entry.status || 'success',
      error:     entry.error || null,
      durationMs: entry.durationMs || 0,
      sessionId: entry.sessionId || null,
      timestamp: new Date().toISOString()
    };

    this.recent.push(safe);
    if (this.recent.length > MAX_LINES) this.recent.shift();

    try {
      fs.appendFileSync(AUDIT_FILE, JSON.stringify(safe) + '\n', 'utf-8');
    } catch { /* 磁盘写入失败不影响主流程 */ }

    return safe.id;
  }

  /** 获取最近 N 条审计记录（可按 userId / tool 过滤） */
  query({ userId, tool, status, limit = 100 } = {}) {
    let rows = this.recent;
    if (userId)  rows = rows.filter(r => r.userId === userId);
    if (tool)    rows = rows.filter(r => r.tool   === tool);
    if (status)  rows = rows.filter(r => r.status === status);
    return rows.slice(-limit).reverse();
  }

  /** 统计：每个工具的调用次数、平均耗时 */
  stats() {
    const acc = {};
    for (const r of this.recent) {
      if (!acc[r.tool]) acc[r.tool] = { tool: r.tool, calls: 0, errors: 0, totalMs: 0 };
      acc[r.tool].calls++;
      acc[r.tool].totalMs += r.durationMs;
      if (r.status !== 'success') acc[r.tool].errors++;
    }
    return Object.values(acc).map(s => ({
      ...s,
      avgMs:    s.calls ? Math.round(s.totalMs / s.calls) : 0,
      errorRate: s.calls ? Math.round((s.errors / s.calls) * 100) : 0
    }));
  }

  _truncate(v) {
    try {
      const s = JSON.stringify(v);
      if (!s) return v;
      return s.length > 2000 ? s.slice(0, 2000) + '...[截断]' : v;
    } catch { return null; }
  }
}

module.exports = new McpAudit();
