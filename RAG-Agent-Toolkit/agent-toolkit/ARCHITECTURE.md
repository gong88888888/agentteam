# 智能体执行架构说明

本文说明本工具包中三套「智能体能力层」如何组织、如何被任务执行链调用，以及它们与整个 RAG 双 AI 平台的关系。

---

## 一、在整体架构中的位置

```
前端（Full / Lite / Work 三版本）
   │  REST /api/*  +  SSE /api/tasks/events  +  WS /ws/progress
   ▼
Express 后端 server.js
   ├─ 中间件: requireAuth(JWT) → requirePermission → 路由 → 全局异常
   ├─ taskManager（任务执行体：document / ppt / workflow / excel 四路分发）
   │     └─ 调度中心 scheduler + workerPool + 分片并行 sharding
   │     └─ aiService（按用户 Profile 流式调用）+ lengthGuard（字数管控）
   ├─ 【本包】MCP 注册表  ←─ initMCP(app)
   ├─ 【本包】Harness 双角色状态机  ←─ initHarness(app)
   └─ 【本包】mcp-tools 独立框架（文档处理/统计/Gantt 引擎）
   ▼
SQLite app.db（22 表, WAL）+ data/*.json（权威数据源 + 原子写）
```

**关键点**：MCP、Harness、mcp-tools 都是「让 AI 真正执行工具」的能力层。它们并行并存：

- `taskManager` 负责长文/PPT/Excel/工作流的生成调度；
- **MCP** 提供标准化工具注册与调用（REST + JSON-RPC + 对话调度）；
- **Harness** 提供双角色状态机编排（A 执行 → B 审核的流转），并通过 `harnessBridge` 调用 MCP 工具；
- **mcp-tools** 是一套更细粒度的文档处理/统计引擎，既供自身路由也桥接进全局 MCP 注册表。

---

## 二、MCP 集成层（`mcp/`）

实现 **Model Context Protocol 1.0** 的本地原生集成，无需外部 MCP 进程。

```
types.js      JSON-RPC 2.0 消息构造
registry.js   工具注册中心（元数据持久化 data/mcp-tools.json）
server.js     handleRequest(jsonRpcMsg, ctx) — 本地 MCP 服务器
client.js     listTools / callTool / extractText — 高层客户端
sandbox.js    沙箱执行：超时、输入大小限制、异常归一化
permissions.js 工具权限（data/mcp-permissions.json）
audit.js      调用审计（logs/mcp/audit.log + 内存统计）
chat.js       对话会话 & AI 工具调度（AI 自动决定调哪个工具）
demos.js      一键演示案例
marketplace.js 工具市场：安装/卸载（restoreInstalled）
customLoader.js 自定义工具 .js 上传后热加载
harnessBridge.js 把所有 MCP 工具注册进 Harness（bridgeAll）
index.js      initMCP(app) — 串联以上全部
```

### 启动链路（`initMCP(app)`）

1. 遍历 `tools/builtin.js` 的 `ALL_BUILTIN_TOOLS` 逐个 `registry.register(tool)`
2. 动态注册 `workflow.split`（复用 `services/workflow/splitter`）
3. `restoreInstalled()` 恢复已安装的市场工具
4. `loadAllCustom()` 加载用户自定义工具
5. `bridgeAll()` 把全部工具桥接进 Harness
6. 挂载 `/api/mcp` 路由（`requireAuth` + `mcp:use` 权限）

### 工具定义结构

每个工具是一个对象：`{ name, description, inputSchema, category, icon, source, handler }`。`handler(input, ctx)` 返回结果；Harness 工具通过 `wrap()` 适配为 MCP 工具（`builtin.js`）。

### REST / JSON-RPC 端点（`/api/mcp`，需 Bearer Token）

- `GET /tools`、`GET /tools/:name`、`POST /tools/:name/toggle`、`POST /tools/:name/config`
- `POST /call {name, arguments}` — 直接调用
- `POST /jsonrpc` — 标准 MCP JSON-RPC（兼容真实 MCP 客户端）
- `POST /chat/new`、`POST /chat/send`、`GET /chat/:id`、`GET /chat`、`DELETE /chat/:id`
- `GET /audit?tool=&status=&limit=` — 调用记录与统计

---

## 三、Harness 多智能体框架（`harness/`）

与 `taskManager` 平行的**双角色状态机**编排框架（实验性/可选路径）。

```
controller.js            任务编排入口（submitTask / getTask / cancelTask / tools）
stateMachine.js          通用状态机
stateMachines/dualRoleStateMachine.js   角色A生成 → 角色B审核 的流转
toolLoader.js            旧版工具加载（仅 ENABLE_LEGACY_HARNESS_TOOLS=1）
validator.js             输入/结果校验
logger.js                任务磁盘日志 + 7 天清理
index.js                 initHarness(app) — 挂载 /api/harness
tools/
  baseTool.js            基类：name / description / execute() 抽象
  aiTool.js              调用 AI 大模型
  ragTool.js             从知识库文件构建 RAG 上下文
  pptTool.js             pptOutline / pptGenerate
  excelTool.js           excelFormula / excelDataClean / excelChart / excelPivot / excelCompare
```

**工具来源**：Harness 自身 9 个基础工具；运行时通过 `mcp/harnessBridge.js` 的 `bridgeAll()` 注入全部 MCP 工具，使流水线可调用任意 MCP 能力。

REST（`/api/harness`，内部无鉴权）：`POST /submit`、`GET /task/:id`、`GET /tasks`、`POST /cancel/:id`、`GET /logs/:id`、`GET /tools`。

---

## 四、mcp-tools 独立框架（`mcp-tools/`）

一套独立于 `backend/mcp` 的细粒度工具框架，偏向**文档工程与数据分析引擎**。

```
toolRegistry.js   本地注册表（与 backend/mcp/registry 隔离）
baseMcpTool.js    工具基类（name/description/inputSchema/call）
callLogger.js     调用日志
documentProcessor.js  文档处理：split_document / get_chunk_info / evaluate_chunk_quality / batch_process
knowledgeGraph.js     知识图谱（占位实现，不进运行时注册表）
lib/
  textPreprocessor.js  规范化清洗（逐行 trim → 合并空行 → 去零宽/全角）
  chunkingEngine.js    语义/标题感知/段落分块 + 重叠
  qualityScorer.js     0-100 多维分块质量评分
  documentParser.js    TXT / MD / PDF / DOCX / XLSX 解析
  statsEngine.js       线性回归 / 皮尔逊 / IQR 异常 / K-Means / ANOVA / 指数平滑
  ganttEngine.js       甘特图 Excel 生成
```

`index.js` 暴露 `initMcpTools()`、`getLocalRegistry()`、`callTool(name, input)`；首次调用时把 `document-processor` 桥接进全局 MCP 注册表（`/api/mcp/tools` 可见）。

---

## 五、Agent Skills（`skills/`）

项目为编码/设计类子任务配置的技能包（Claude Agent Skills 规范：`SKILL.md` + 资源文件）：

| 技能 | 作用 |
|---|---|
| `frontend-design` | 有辨识度的 UI 视觉设计指引（美学方向/字体/反模板化），来自 `anthropics/skills` |
| `adaptive-frontend-optimization` | 审计并增量优化既有前端工作流/响应式布局/异步状态/无障碍，附带 frontend-kit 资产 |
| `postmortem-to-tests` | 把工程事故复盘转为结构化根因分析 + 可落地回归测试（固定 6 阶段流程） |
| `ui-ux-pro-max` | UI/UX 设计知识库：67 风格 / 96 配色 / 57 字体搭配 / 25 图表 / 13 技术栈（CSV 数据 + Python 检索脚本） |

这些技能服务于「开发本项目本身」的场景（前端设计与优化、事故复盘、UI/UX 决策），由 Claude Code / Agent 运行时按任务描述自动匹配触发。

---

## 六、端到端调用示例（MCP 直接调用）

```
POST /api/mcp/call
Authorization: Bearer <token>
{
  "name": "rag.context",
  "arguments": { "fileIds": ["f_xxx"], "query": "产品定价策略", "maxChars": 6000 }
}
```

沙箱执行 → 权限校验 → 审计落盘 → 返回 `{ success, data, durationMs }`。

工作流拆分：

```
POST /api/mcp/call  { "name": "workflow.split", "arguments": { "description": "写一份市场分析报告", "mode": "prompt" } }
→ 返回 { workflow, valid }
```

---

*本说明聚焦智能体执行能力层；平台完整架构（任务调度/分片/数据层/前端三版本）见宿主项目根目录 `系统全景架构与功能说明.md`。*
