/**
 * MCP 工具权限管理
 * 管理：每个用户可调用的工具白名单（admin 默认全部可用）
 * 持久化：data/mcp-permissions.json
 */
const fs   = require('fs');
const path = require('path');

const PERMS_FILE = path.join(__dirname, '../data/mcp-permissions.json');

class McpPermissions {
  constructor() {
    this.data = this._load();
  }

  _load() {
    if (!fs.existsSync(PERMS_FILE)) {
      const initial = { defaults: { allow: '*' }, users: {} };
      this._save(initial);
      return initial;
    }
    try { return JSON.parse(fs.readFileSync(PERMS_FILE, 'utf-8')); }
    catch { return { defaults: { allow: '*' }, users: {} }; }
  }

  _save(data = this.data) {
    fs.writeFileSync(PERMS_FILE, JSON.stringify(data, null, 2), 'utf-8');
  }

  /** 检查用户是否有权限调用某工具 */
  canCall(userId, toolName, isAdmin = false) {
    if (isAdmin) return true;
    const userRule = this.data.users?.[userId];
    if (userRule) {
      if (userRule.deny?.includes(toolName)) return false;
      if (userRule.allow === '*') return true;
      if (Array.isArray(userRule.allow)) return userRule.allow.includes(toolName);
    }
    // 回退到默认规则
    const def = this.data.defaults || {};
    if (def.deny?.includes(toolName)) return false;
    if (def.allow === '*') return true;
    if (Array.isArray(def.allow)) return def.allow.includes(toolName);
    return false;
  }

  /** 设置某用户的工具权限 */
  setUserPermission(userId, allow, deny = []) {
    if (!this.data.users) this.data.users = {};
    this.data.users[userId] = { allow, deny };
    this._save();
  }

  /** 设置全局默认权限 */
  setDefaults(allow, deny = []) {
    this.data.defaults = { allow, deny };
    this._save();
  }

  /** 获取某用户的最终权限快照（用于前端展示） */
  describe(userId) {
    return {
      defaults: this.data.defaults,
      user:     this.data.users?.[userId] || null
    };
  }
}

module.exports = new McpPermissions();
