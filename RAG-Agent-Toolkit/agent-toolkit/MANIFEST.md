# 工具与技能清单（Manifest）

本包共打包：**MCP 工具（`mcp/` + `mcp-tools/`）约 68 个可注册能力**、**Harness 18 个工具/模块**、**4 个 Agent Skill**。机器可读版本见 `manifest.json`。

---

## 一、MCP 内置核心工具（`mcp/tools/builtin.js` + `mcp/index.js`）

| 工具 | 说明 |
|---|---|
| `ai.chat` | 调用 AI 大模型完成对话/生成（OpenAI 兼容，按 userId 读 Profile） |
| `rag.context` | 从知识库文件构建 RAG 上下文 |
| `excel.formula` | 自然语言 → Excel 公式 |
| `excel.clean` | Excel 数据清洗 |
| `excel.chart` | Excel 图表配置生成 |
| `excel.pivot` | 数据透视建议 |
| `excel.compare` | 两表差异对比 |
| `ppt.outline` | 根据内容生成 PPT 大纲 |
| `ppt.generate` | 根据大纲生成 PPTX |
| `ppt.compose_graphics` | 组合矢量图形 |
| `fs.readText` | 读取本地文本文件 |
| `web.search` | 联网搜索（占位/可插拔） |
| `math.eval` | 数学表达式求值 |
| `workflow.split` | 工作流智能拆分（复用 `services/workflow/splitter`，动态注册） |

## 二、Git 工具（`mcp/tools/gitTool.js`，11 个）

`git.init` `git.clone` `git.status` `git.add` `git.commit` `git.log` `git.diff` `git.branch` `git.push` `git.remote` `git.tag`

## 三、GitHub 工具（`mcp/tools/githubTool.js`，12 个）

`github.list_repos` `github.repo_info` `github.get_file` `github.create_file` `github.search_repos` `github.search_code` `github.get_issue` `github.get_pr` `github.download_zip` `github.parse_url` `github.test_token` `github.get_config`
（Token 采用 AES-256 加密存储）

## 四、Office 工具（`mcp/tools/officeTool.js`，7 个，封装 OfficeCLI）

`office.create` `office.view` `office.set` `office.add` `office.merge` `office.batch` `office.info`

## 五、PPT 设计系统 + 矢量图形（`mcp/tools/htmlPptTool.js` + `pptVectorTools.js`，10 个）

`ppt.themes` `ppt.layouts` `ppt.html` `ppt.enhanced` `ppt.outline` `ppt.generate` `ppt.compose_graphics` `ppt.search_vector_graphics` `ppt.clone_vector_graphic` `ppt.generate_vector_diagram`
（内置 8 主题 + 31 布局，主题示例：极简白/德古拉/东京之夜/极光/毛玻璃/柔和粉彩/赛博朋克/VC路演 — 这些是主题名，非工具）

## 六、Excel 经典 + 管理 + 统计工具（`mcp/tools/excelManagement.js` 等，16 个）

- 经典：`excel.chart` `excel.clean` `excel.pivot` `excel.formula` `excel.compare` `excel.anomaly`
- 管理：`excel.gantt` `excel.schedule` `excel.budget` `excel.kpi` `excel.riskRegister` `excel.meetingNotes` `excel.taskStats`
- 统计：`excel.regression` `excel.correlation` `excel.timeSeries`

## 七、工具市场（`mcp/marketplace.js`，6 个可安装）

`web.browse` `email.send` `db.query` `calendar.event` `code.python` `image.generate`

## 八、mcp-tools 独立框架（`mcp-tools/`）

- `document-processor`：`split_document` / `get_chunk_info` / `evaluate_chunk_quality` / `batch_process`
- `knowledge-graph`：占位实现（不进运行时注册表）
- 引擎库（`lib/`）：TextPreprocessor、ChunkingEngine、QualityScorer、DocumentParser、StatsEngine、GanttEngine

## 九、Harness 多智能体框架（`harness/`）

- 编排：`controller` `stateMachine` `dualRoleStateMachine` `validator` `logger` `toolLoader`
- 基础工具（9）：`aiTool` `ragTool` `pptOutline` `pptGenerate` `excelFormula` `excelDataClean` `excelChart` `excelPivot` `excelCompare`
- 运行时通过 `mcp/harnessBridge.js` 注入全部 MCP 工具

## 十、Agent Skills（`skills/`，4 个）

| 技能 | 简介 | 来源 |
|---|---|---|
| `frontend-design` | 有辨识度的 UI 视觉设计指引 | anthropics/skills（LICENSE 随附） |
| `adaptive-frontend-optimization` | 审计并增量优化前端工作流/响应式/异步/无障碍 | 项目自带（含 frontend-kit 资产与测试） |
| `postmortem-to-tests` | 事故复盘 → 根因分析 + 回归测试（固定 6 阶段） | MIT |
| `ui-ux-pro-max` | UI/UX 知识库（67 风格 / 96 配色 / 57 字体 / 13 栈，CSV + Python 检索） | 项目自带 |

---

## 统计

| 类别 | 数量 |
|---|---|
| MCP 可注册工具（内置+Git+GitHub+Office+PPT+Excel+市场+workflow.split+document-processor） | ≈68 |
| Harness 基础工具 | 9 |
| mcp-tools 引擎库 | 6 |
| Agent Skills | 4 |
| 打包源码文件 | 见 `manifest.json` 的 `files` 计数 |
