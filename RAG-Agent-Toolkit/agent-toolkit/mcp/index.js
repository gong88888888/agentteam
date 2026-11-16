/**
 * MCP 系统入口
 * 由 server.js 调用 initMCP(app)
 */
const registry            = require('./registry');
const { ALL_BUILTIN_TOOLS } = require('./tools/builtin');
const { restoreInstalled } = require('./marketplace');
const { loadAllCustom }    = require('./customLoader');
const { bridgeAll }        = require('./harnessBridge');

function initMCP(app) {
  // 1. 注册所有内置 MCP 工具
  for (const tool of ALL_BUILTIN_TOOLS) {
    try { registry.register(tool); }
    catch (e) { console.error(`[MCP] 注册 ${tool.name} 失败: ${e.message}`); }
  }
  console.log(`[MCP] ✅ 内置工具已注册: ${ALL_BUILTIN_TOOLS.length} 个`);

  // 1b. 注册工作流拆分智能体（workflow-splitter）
  try {
    const splitter = require('../services/workflow/splitter');
    registry.register({
      name: 'workflow.split',
      description: '工作流智能拆分：将提示词或模板解析为标准多步骤工作流（角色分工+依赖+MCP工具）',
      category: 'workflow',
      icon: '🔀',
      enabled: true,
      handler: async (input = {}) => {
        const mode = input.mode === 'template' ? 'template' : 'prompt';
        const wf = mode === 'template'
          ? splitter.splitFromTemplate(input.text || input.description || '', { name: input.name, outputType: input.outputType })
          : splitter.splitFromPrompt(input.description || '', { name: input.name, outputType: input.outputType });
        return { workflow: wf, valid: splitter.validateWorkflow(wf).valid };
      }
    });
  } catch (e) {
    console.error('[MCP] 注册 workflow.split 失败:', e.message);
  }

  // 2. 恢复已"安装"的市场工具
  restoreInstalled();

  // 3. 加载自定义工具
  loadAllCustom();

  // 4. 桥接到 Harness（让 Harness 流水线能调用 MCP 工具）
  bridgeAll();

  // 5. 挂载 REST API
  const { requireAuth, requirePermission } = require('../middleware/auth');
  app.use('/api/mcp', requireAuth, requirePermission('mcp:use'), require('../routes/mcp'));

  console.log('[MCP] ✅ API 已挂载到 /api/mcp');
}

module.exports = { initMCP };
