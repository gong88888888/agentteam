# MCP 模块开发与使用文档

本目录实现了 **Model Context Protocol (MCP) 1.0** 标准在本系统中的原生集成层。
所有 MCP 工具同时通过 Harness 桥接，可在双 AI 任务流水线中调用。

## 目录结构

```
backend/mcp/
├── types.js          — MCP/JSON-RPC 2.0 消息构造工具
├── registry.js       — 工具注册中心（元数据持久化在 data/mcp-tools.json）
├── server.js         — 本地 MCP 服务器：handleRequest(jsonRpcMsg, ctx)
├── client.js         — 高层客户端：listTools / callTool / extractText
├── sandbox.js        — 沙箱执行（超时、输入大小、异常归一化）
├── permissions.js    — 工具权限（data/mcp-permissions.json）
├── audit.js          — 调用审计（logs/mcp/audit.log + 内存）
├── chat.js           — 对话会话 & AI 工具调度
├── demos.js          — 8 个一键演示案例
├── harnessBridge.js  — 把所有 MCP 工具桥接进 Harness
├── marketplace.js    — 工具市场目录与安装/卸载
├── customLoader.js   — 自定义工具 .js 上传加载
├── tools/
│   └── builtin.js    — 12 个内置 MCP 工具（ai/rag/excel/ppt/fs/web/math）
├── custom/           — 用户上传的自定义工具 .js 文件目录
└── index.js          — 入口 initMCP(app)
```

## 启动方式

`backend/server.js` 启动时会自动：
1. `initHarness(app)` — 挂载 Harness API；默认不预加载旧版工具
2. `initMCP(app)` — 注册内置 MCP 工具 → 恢复已安装市场工具 → 加载自定义工具 → 桥接到 Harness → 挂载 `/api/mcp` 路由
3. `mcp-tools/document-processor` — 仅在 RAG 或兼容接口首次调用时懒加载

如需临时启用旧版 Harness 工具，设置 `ENABLE_LEGACY_HARNESS_TOOLS=1` 后重启。

无需额外步骤。

## REST API（全部需要 `Authorization: Bearer <token>`）

### 工具
- `GET  /api/mcp/info` — 服务器信息
- `GET  /api/mcp/tools` — 列出所有工具（含禁用/无权限状态）
- `GET  /api/mcp/tools/:name` — 工具详情
- `POST /api/mcp/tools/:name/toggle` `{ enabled }` *(admin)*
- `POST /api/mcp/tools/:name/config` `{ ...config }` *(admin)*
- `POST /api/mcp/call` `{ name, arguments }` — 直接调用
- `POST /api/mcp/jsonrpc` — 标准 MCP JSON-RPC 端点（兼容真实 MCP 客户端）

### 对话
- `POST /api/mcp/chat/new` — 新建会话
- `POST /api/mcp/chat/send` `{ sessionId, message, manualTool? }`
- `GET  /api/mcp/chat/:id` — 获取会话详情
- `GET  /api/mcp/chat` — 我的会话列表
- `DELETE /api/mcp/chat/:id`

### 审计
- `GET  /api/mcp/audit?tool=&status=&limit=` — 调用记录 + 统计

### 权限 *(admin)*
- `GET  /api/mcp/permissions`
- `POST /api/mcp/permissions/user/:userId` `{ allow, deny }`
- `POST /api/mcp/permissions/defaults` `{ allow, deny }`

### 市场 *(install/uninstall 为 admin)*
- `GET  /api/mcp/marketplace`
- `POST /api/mcp/marketplace/install` `{ name }`
- `POST /api/mcp/marketplace/uninstall` `{ name }`

### 自定义 *(admin)*
- `POST /api/mcp/custom/upload` `{ filename, code }`
- `POST /api/mcp/custom/uninstall` `{ name }`

### 演示
- `GET  /api/mcp/demos` — 8 个固定案例

## 编写自定义 MCP 工具

在前端 **MCP 工具中心 → 自定义工具** 上传 `.js`，或直接放到 `backend/mcp/custom/*.js`：

```js
module.exports = {
  name: 'demo.hello',
  description: '示例：返回问候语',
  category: 'utility',
  icon: '👋',
  inputSchema: {
    type: 'object',
    properties: { who: { type: 'string', default: 'world' } }
  },
  handler: async (input) => {
    return { greeting: 'Hello, ' + (input.who || 'world') + '!' };
  }
};
```

字段说明：
- `name` *(必填)* — 工具名，建议 `<category>.<verb>` 风格
- `description` *(必填)* — 一句话描述
- `inputSchema` — JSON Schema，供 AI 工具调度器理解参数
- `handler(input) => any` *(必填)* — 实际执行函数；返回任意值，会被自动包装为 MCP `content[]`
- `category` / `icon` — 前端展示用
- `defaultConfig` — 工具配置默认值（如 `{ timeoutMs: 30000 }`）

## 安全保证

1. **沙箱**：所有 handler 调用都经过 `sandbox.run()`，自动超时（默认 60s）、输入大小限制（5MB）、异常归一化。
2. **权限**：每次 `tools/call` 都经过 `permissions.canCall()`，admin 可绕过；普通用户受 `defaults` + 用户级 `allow/deny` 约束。
3. **审计**：每次调用记录用户、工具、入参、出参、耗时、状态，落地 `logs/mcp/audit.log`。
4. **文件访问**：`fs.readText` 工具硬限制只能访问 `uploads/exports/data` 三个目录。

## 与 Harness 的关系

启动时 `harnessBridge.bridgeAll()` 把每个 MCP 工具按原名（含点号）注册到 Harness。
原有 Harness 任务（如 `taskManager.js` 调度的双 AI 任务）继续使用原内置工具，**功能 100% 兼容**；
若新写流水线步骤，建议直接用 MCP 工具名，自动享有沙箱、权限、审计。

## 测试

```bash
cd backend
npx jest tests/mcp.test.js --testTimeout=15000 --forceExit
```

当前覆盖：31 个用例（types/registry/sandbox/permissions/audit/server/client/marketplace/bridge/chat 全覆盖）。
