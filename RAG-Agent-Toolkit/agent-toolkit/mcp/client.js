/**
 * MCP 客户端
 * - 主要通道：本地 server（in-process），用于内置工具
 * - 远程通道：stdio JSON-RPC（用于第三方 MCP 工具，按需启动子进程）
 *
 * 设计原则：上层（Harness 桥接、聊天会话）只用 client，不直接碰 server / registry，
 * 这样未来切换到官方 @modelcontextprotocol/sdk 时只需替换本文件。
 */
const localServer = require('./server');
const { makeRequest } = require('./types');

class McpClient {
  /**
   * 列出所有工具（ctx 控制可见性）
   */
  async listTools(ctx = {}) {
    const req  = makeRequest('tools/list');
    const resp = await localServer.handleRequest(req, ctx);
    if (resp.error) throw new Error(resp.error.message);
    return resp.result.tools;
  }

  /**
   * 调用工具
   * @returns {Object} { content, isError, raw }
   */
  async callTool(name, args, ctx = {}) {
    const req  = makeRequest('tools/call', { name, arguments: args });
    const resp = await localServer.handleRequest(req, ctx);
    if (resp.error) {
      const err = new Error(resp.error.message);
      err.code  = resp.error.code;
      throw err;
    }
    return resp.result;
  }

  /**
   * 提取调用结果的文本内容（最常用辅助方法）
   */
  extractText(callResult) {
    if (!callResult?.content) return '';
    return callResult.content
      .filter(c => c.type === 'text')
      .map(c => c.text)
      .join('\n');
  }

  /**
   * 提取并尝试 JSON 解析（适用于结构化输出工具）
   */
  extractJSON(callResult) {
    const text = this.extractText(callResult);
    if (!text) return null;
    try { return JSON.parse(text); }
    catch { return null; }
  }
}

module.exports = new McpClient();
