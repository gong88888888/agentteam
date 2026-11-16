/**
 * MCP 本地服务器
 * - 提供 handleRequest(jsonRpcMsg) 处理 MCP 标准协议
 * - 实现 initialize / tools/list / tools/call / ping
 * - 透明走 registry + permissions + sandbox + audit
 */
const registry    = require('./registry');
const permissions = require('./permissions');
const sandbox     = require('./sandbox');
const audit       = require('./audit');
const rateLimit   = require('./rateLimit');
const {
  METHODS, ERROR_CODES, MCP_VERSION,
  makeResponse, makeError, makeContent
} = require('./types');

class McpServer {
  /**
   * 处理一次 MCP 请求（JSON-RPC 2.0）
   * @param {Object} msg            - 请求消息
   * @param {Object} ctx            - { userId, isAdmin, sessionId, username }
   */
  async handleRequest(msg, ctx = {}) {
    if (!msg || msg.jsonrpc !== '2.0' || !msg.method) {
      return makeError(msg?.id ?? null, ERROR_CODES.INVALID_REQUEST, '非法 JSON-RPC 请求');
    }

    try {
      switch (msg.method) {
        case METHODS.INITIALIZE:
          return makeResponse(msg.id, {
            protocolVersion: MCP_VERSION,
            serverInfo:      { name: 'rag-dual-ai-mcp', version: '1.0.0' },
            capabilities:    { tools: { listChanged: true } }
          });

        case METHODS.PING:
          return makeResponse(msg.id, { pong: true, time: new Date().toISOString() });

        case METHODS.TOOLS_LIST: {
          const all      = registry.list({ enabledOnly: true });
          const filtered = all.filter(t => permissions.canCall(ctx.userId, t.name, ctx.isAdmin));
          return makeResponse(msg.id, {
            tools: filtered.map(t => ({
              name:        t.name,
              description: t.description,
              inputSchema: t.inputSchema
            }))
          });
        }

        case METHODS.TOOLS_CALL: {
          const { name, arguments: args } = msg.params || {};
          if (!name) return makeError(msg.id, ERROR_CODES.INVALID_PARAMS, '缺少 name');

          const tool = registry.get(name);
          if (!tool)           return makeError(msg.id, ERROR_CODES.TOOL_NOT_FOUND, `工具 "${name}" 不存在`);
          if (!tool.enabled)   return makeError(msg.id, ERROR_CODES.TOOL_DISABLED,  `工具 "${name}" 已禁用`);

          if (!permissions.canCall(ctx.userId, name, ctx.isAdmin)) {
            audit.record({
              userId: ctx.userId, username: ctx.username, tool: name,
              input: args, status: 'denied', error: '无权限', sessionId: ctx.sessionId
            });
            return makeError(msg.id, ERROR_CODES.PERMISSION_DENIED, `无权限调用工具 "${name}"`);
          }

          const t0 = Date.now();
          try {
            rateLimit.check(ctx.userId, name, tool.config?.rateLimit);
            // 自动注入用户上下文到工具入参（工具无需前端手动传 userId）
            const enrichedArgs = { ...(args || {}), userId: ctx.userId, _ctx: ctx };

            const result = await sandbox.run(tool.handler, enrichedArgs, {
              timeoutMs: tool.config?.timeoutMs
            });

            const content = result?.__mcp_content || makeContent(result?.__mcp_type || 'json', result);
            const isError = !!result?.__mcp_error;

            audit.record({
              userId: ctx.userId, username: ctx.username, tool: name,
              input: args, output: result,
              status: isError ? 'error' : 'success',
              durationMs: Date.now() - t0,
              sessionId: ctx.sessionId
            });

            return makeResponse(msg.id, { content, isError });

          } catch (err) {
            audit.record({
              userId: ctx.userId, username: ctx.username, tool: name,
              input: args, status: 'error', error: err.message,
              durationMs: Date.now() - t0, sessionId: ctx.sessionId
            });
            const code = /超时/.test(err.message) ? ERROR_CODES.EXECUTION_TIMEOUT : ERROR_CODES.TOOL_ERROR;
            return makeError(msg.id, code, err.message);
          }
        }

        default:
          return makeError(msg.id, ERROR_CODES.METHOD_NOT_FOUND, `方法 ${msg.method} 不存在`);
      }
    } catch (err) {
      return makeError(msg.id ?? null, ERROR_CODES.INTERNAL_ERROR, err.message);
    }
  }
}

module.exports = new McpServer();
