'use strict';

const buckets = new Map();

function check(userId, toolName, { limit = 30, windowMs = 60000 } = {}) {
  const now = Date.now();
  const key = `${userId || 'anonymous'}:${toolName}`;
  const recent = (buckets.get(key) || []).filter(ts => now - ts < windowMs);
  if (recent.length >= limit) {
    const err = new Error(`MCP 工具调用过于频繁，请在 ${Math.ceil(windowMs / 1000)} 秒后重试`);
    err.code = 'MCP_RATE_LIMITED';
    throw err;
  }
  recent.push(now);
  buckets.set(key, recent);
}

function reset() { buckets.clear(); }

module.exports = { check, reset };
