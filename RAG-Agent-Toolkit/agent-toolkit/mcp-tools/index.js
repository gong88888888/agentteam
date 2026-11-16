/**
 * mcp-tools 框架入口
 *
 * 职责：
 * 1. 维护本地 McpToolRegistry（独立于 backend/mcp/registry.js）
 * 2. 首次使用时注册文档处理工具
 * 3. 同时向全局 MCP 注册表注册（让 /api/mcp/tools 接口可见）
 * 4. 暴露 callTool(name, input) 供内部测试和路由使用
 */
const McpToolRegistry   = require('./toolRegistry');
const DocumentProcessor = require('./documentProcessor');

/** 本地注册表（此框架专用） */
const localRegistry = new McpToolRegistry();

let _initialized = false;

function initMcpTools() {
  if (_initialized) return;

  // knowledge-graph 仍是占位实现，不进入运行时注册表。
  // document-processor 由 getLocalRegistry/callTool 首次调用时初始化。
  const dp = new DocumentProcessor();

  localRegistry.register(dp);

  // 2. 桥接到全局 MCP 注册表（让 /api/mcp/tools 可见）
  _bridgeToGlobalRegistry(dp);

  _initialized = true;
  console.log(`[mcp-tools] ✅ 已注册 ${localRegistry.size} 个工具: ${localRegistry.list().map(t => t.name).join(', ')}`);
}

function _bridgeToGlobalRegistry(toolInstance) {
  try {
    const globalReg = require('../mcp/registry');
    // 用 MCP handler 包装，让全局注册表可以调用本地工具
    globalReg.register({
      name:        toolInstance.name,
      description: toolInstance.description,
      inputSchema: toolInstance.inputSchema,
      category:    'analysis',
      icon:        toolInstance.name === 'document-processor' ? '📄' : '🕸️',
      source:      'mcp-tools',
      handler:     async (input) => {
        const result = await toolInstance.call(input);
        return result;
      }
    });
  } catch (e) {
    // 全局注册失败不影响本地使用（测试环境下注册表可能 mock）
    console.warn(`[mcp-tools] 全局注册失败 (${toolInstance.name}): ${e.message}`);
  }
}

/** 获取本地注册表 */
function getLocalRegistry() {
  initMcpTools();
  return localRegistry;
}

/**
 * 通过本地注册表调用工具
 * @returns {Promise<{success, data, error, durationMs}>}
 */
async function callTool(name, input = {}) {
  initMcpTools();
  return localRegistry.call(name, input);
}

module.exports = { initMcpTools, getLocalRegistry, callTool };
