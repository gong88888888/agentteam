/**
 * McpToolRegistry — 新工具框架的注册中心
 * 与 backend/mcp/registry.js 平行但独立，
 * 专门管理 mcp-tools/ 目录下的文档/知识图谱工具。
 * 通过 index.js 桥接到全局 MCP 系统。
 */
const BaseMcpTool = require('./baseMcpTool');

class McpToolRegistry {
  constructor() {
    /** @type {Map<string, BaseMcpTool>} */
    this.tools = new Map();
  }

  /**
   * 注册工具（幂等，重复注册覆盖旧版本）
   * @param {BaseMcpTool} tool
   */
  register(tool) {
    if (!(tool instanceof BaseMcpTool)) {
      throw new TypeError(`工具必须继承 BaseMcpTool: ${tool?.constructor?.name}`);
    }
    if (!tool.name) throw new Error('工具 name 不能为空');
    this.tools.set(tool.name, tool);
    return this;
  }

  /** @returns {boolean} */
  has(name) { return this.tools.has(name); }

  /** @returns {BaseMcpTool|null} */
  get(name) { return this.tools.get(name) || null; }

  /** 列出所有工具的 MCP 定义（不含 handler） */
  list() {
    return [...this.tools.values()].map(t => t.toMcpDefinition());
  }

  /**
   * 调用工具
   * @returns {Promise<{success, data, error, durationMs}>}
   */
  async call(toolName, input = {}) {
    const tool = this.tools.get(toolName);
    if (!tool) {
      return {
        success: false,
        data: null,
        error: `工具 "${toolName}" 不存在`,
        durationMs: 0
      };
    }
    return tool.call(input);
  }

  /** 工具数量 */
  get size() { return this.tools.size; }
}

module.exports = McpToolRegistry;
