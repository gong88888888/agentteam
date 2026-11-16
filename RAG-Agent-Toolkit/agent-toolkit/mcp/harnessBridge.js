/**
 * Harness ↔ MCP 桥接
 * - 把所有 MCP 工具注册为 Harness 工具（前缀 mcp.）
 * - 这样 Harness 流水线可以无缝调用任何 MCP 工具
 * - 同时保留原 Harness 内置工具不动（向后兼容）
 */
const harness  = require('../harness/controller');
const client   = require('./client');
const registry = require('./registry');

function bridgeAll() {
  let count = 0;
  for (const tool of registry.list()) {
    // Harness 注册名：直接用 MCP 工具名（保留点号）
    const harnessName = tool.name;
    if (harness.hasTool(harnessName)) continue;

    harness.registerTool(harnessName, {
      name:        harnessName,
      description: `[MCP] ${tool.description}`,
      execute:     async (input) => {
        // 用 system ctx（无用户身份）；上层 Harness 任务的 ctx 通过 input 透传
        const ctx = {
          userId:  input?._ctx?.userId  ?? input?.userId  ?? null,
          isAdmin: input?._ctx?.isAdmin ?? false,
          sessionId: input?._ctx?.sessionId ?? null,
          username: input?._ctx?.username ?? null
        };
        const cleaned = { ...input };
        delete cleaned._ctx;
        const result = await client.callTool(tool.name, cleaned, ctx);
        // 解包成 Harness 友好的格式
        return {
          isError: result.isError,
          content: result.content,
          text:    client.extractText(result),
          json:    client.extractJSON(result)
        };
      }
    });
    count++;
  }
  console.log(`[MCP/bridge] 已把 ${count} 个 MCP 工具桥接到 Harness`);
  return count;
}

module.exports = { bridgeAll };
