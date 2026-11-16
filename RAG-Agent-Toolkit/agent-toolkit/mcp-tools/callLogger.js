/**
 * 工具调用日志记录器
 * 内存存储最近 1000 条，提供统计接口
 */
const MAX_RECORDS = 1000;

class CallLogger {
  constructor() {
    this.records = [];
  }

  record({ tool, input, output, error, durationMs, success, userId }) {
    const entry = {
      id:         `log_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      tool:       tool || 'unknown',
      input:      this._truncate(input),
      output:     success ? this._truncate(output) : null,
      error:      success ? null : (error || 'unknown error'),
      durationMs: durationMs || 0,
      success:    !!success,
      userId:     userId || null,
      timestamp:  new Date().toISOString()
    };

    this.records.push(entry);
    if (this.records.length > MAX_RECORDS) {
      this.records.shift();
    }

    return entry.id;
  }

  getRecent(limit = 50) {
    return this.records.slice(-Math.min(limit, this.records.length)).reverse();
  }

  getByTool(toolName, limit = 20) {
    return this.records
      .filter(r => r.tool === toolName)
      .slice(-limit)
      .reverse();
  }

  stats() {
    const total   = this.records.length;
    const success = this.records.filter(r => r.success).length;
    const byTool  = {};
    for (const r of this.records) {
      if (!byTool[r.tool]) byTool[r.tool] = { calls: 0, errors: 0, totalMs: 0 };
      byTool[r.tool].calls++;
      byTool[r.tool].totalMs += r.durationMs;
      if (!r.success) byTool[r.tool].errors++;
    }
    return {
      total,
      success,
      failures:    total - success,
      successRate: total ? +(success / total * 100).toFixed(1) : 100,
      byTool
    };
  }

  clear() { this.records = []; }

  _truncate(v) {
    try {
      const s = JSON.stringify(v);
      if (!s) return null;
      return s.length > 2000 ? s.slice(0, 2000) + '...' : v;
    } catch { return null; }
  }
}

module.exports = new CallLogger();
