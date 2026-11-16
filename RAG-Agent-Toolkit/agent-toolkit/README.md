# RAG 双 AI 生成平台 — Agent 工具与技能工具包

> 本压缩包从 `RAG-Dual-AI-Generator` 项目中抽取「智能体执行链路」实际用到的 MCP 工具、Harness 多智能体框架与前端/工程技能，整理为可独立查阅、可移植复用的工具包。

## 这是什么

项目以「角色A（执行者）生成 → 角色B（监督者）审核」的双 AI 协作为核心，AI 在执行任务时会调用 **MCP 工具**（文件/知识库/PPT/Excel/Office/Git/GitHub 等 60+ 个能力）以及 **Harness 双角色状态机** 编排。此外项目还配置了 4 个 **Agent Skills**（前端设计与优化、事故复盘转回归测试、UI/UX 知识库）。本包把这些资产集中打包。

## 目录结构

```
agent-toolkit/
├── README.md                 # 本文件
├── ARCHITECTURE.md           # 智能体执行架构说明（MCP / Harness / mcp-tools 关系）
├── MANIFEST.md               # 工具与技能清单（人类可读）
├── manifest.json             # 工具与技能清单（机器可读）
├── mcp/                      # MCP 1.0 原生集成层（注册中心/服务器/客户端/沙箱/权限/审计/市场/自定义工具）
│   ├── index.js              # initMCP(app) 入口
│   ├── registry.js           # 工具注册中心（元数据持久化在 data/mcp-tools.json）
│   ├── server.js             # 本地 MCP 服务器 handleRequest(jsonRpc, ctx)
│   ├── client.js             # 高层客户端 listTools / callTool / extractText
│   ├── sandbox.js            # 沙箱执行（超时/输入大小/异常归一化）
│   ├── permissions.js        # 工具权限（data/mcp-permissions.json）
│   ├── audit.js              # 调用审计（logs/mcp/audit.log + 内存）
│   ├── chat.js               # 对话会话 & AI 工具调度
│   ├── demos.js              # 一键演示案例
│   ├── harnessBridge.js      # 把 MCP 工具桥接进 Harness
│   ├── marketplace.js        # 工具市场目录与安装/卸载
│   ├── customLoader.js       # 自定义工具 .js 上传加载
│   ├── rateLimit.js / types.js / server.js
│   └── tools/                # 各工具实现
│       ├── builtin.js        # 内置工具（ai/rag/excel/ppt/fs/web/math）
│       ├── gitTool.js        # Git 工具（11 个）
│       ├── githubTool.js     # GitHub 工具（12 个）
│       ├── officeTool.js     # OfficeCLI 封装（7 个）
│       ├── htmlPptTool.js    # HTML-PPT 设计系统（主题/布局/演示文稿）
│       ├── pptVectorTools.js # PPT 矢量图形工具
│       └── excelManagement.js# Excel 管理与统计工具
├── mcp-tools/                # 独立 mcp-tools 框架（文档处理/知识图谱 + 引擎库）
│   ├── baseMcpTool.js / toolRegistry.js / callLogger.js
│   ├── documentProcessor.js  # 文档分词/分块/质检/批量处理
│   ├── knowledgeGraph.js     # 知识图谱（占位实现）
│   └── lib/                  # TextPreprocessor / ChunkingEngine / QualityScorer / DocumentParser / StatsEngine / GanttEngine
├── harness/                  # Harness 多智能体框架（双角色状态机）
│   ├── controller.js / stateMachine.js / stateMachines/dualRoleStateMachine.js
│   ├── toolLoader.js / validator.js / logger.js / index.js
│   └── tools/                # aiTool / ragTool / pptTool / excelTool / baseTool
└── skills/                   # Agent Skills（SKILL.md + 数据/资产）
    ├── adaptive-frontend-optimization/
    ├── frontend-design/
    ├── postmortem-to-tests/
    └── ui-ux-pro-max/
```

## 来源与依赖说明

- 本包是**源码抽取包**：`mcp/`、`mcp-tools/`、`harness/` 从项目中同名目录原样复制（保留相对布局，`mcp/tools/builtin.js` 中的 `../../harness/tools/*` 相对引用仍可解析）。
- 完整运行仍需宿主项目提供 `backend/services/*`、`backend/middleware/auth`、`backend/routes/mcp`、`backend/config`、`data/*.json` 等依赖。本包用于**阅读、审计、二次移植或作知识资产**，并非开箱即跑的独立 npm 包。
- `mcp/custom/`（用户上传自定义工具目录）在原项目中为空，未打包。

## 快速上手（在宿主项目内）

```js
// server.js 启动时
const { initHarness } = require('./harness');
const { initMCP }     = require('./mcp');
initHarness(app);
initMCP(app);              // 注册内置工具 → 恢复市场工具 → 加载自定义 → 桥接 Harness → 挂载 /api/mcp
```

REST：`/api/mcp/tools`、`/api/mcp/call`、`/api/mcp/jsonrpc`、`/api/mcp/audit`、`/api/harness/submit` 等。

详见 `ARCHITECTURE.md` 与 `MANIFEST.md`。
