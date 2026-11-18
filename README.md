# AgentTeam

一人公司主导的全栈交付 Agent 集群。当前仓库包含 **v4.1 编排协议**、**W1/W2 真实适配层**、**W3 三切片并行/共享文件/契约影响/Serial Baseline**、**W4 角色 golden set/prompt 回归、混合检索知识库、决策收件箱** 与 **W5 需求选择/项目启动/角色监控**，并完成 **P0–P2 升级**（工具证据 + CI、进程级沙箱、角色门禁、决策升级、质量趋势、模板、rerank）：本地 Qwen 3.6 负责执行 Agent，DeepSeek（deepseekharness）负责裁判或作为补充；门禁只接受工具签名证据，裁决和证据失效可审计、可复评；W3 工作台、W4 决策收件箱与 W5 角色监控在 `dashboard/`。

## 2026-11-18 优化实施

按 `optimization-2026-11-18/` 的 18 篇方案分 8 轮完成，详细交付与限制见
[实施报告](docs/optimization/implementation-report.md) 与 [轮次记录](docs/optimization/rounds.md)。

| 能力 | 结果 |
|---|---|
| 失败关闭 | 未知后端/真实模式 stub 直接配置错误；空产物、伪造/过期证据、旧门禁、blocked 评审不再通过 |
| 完成定义 | 必需集合来自已批准 `state/manifest.json`；Web 必须真实启动+健康+业务流；游戏必须集成验收 |
| 来源与需求 | 稳定来源单元（内容身份/移动/修改/新增/删除）、原子需求、来源处置与结构校验 |
| 上下文 | `ContextAssembler` 按任务注入原文/规范/代码，带哈希、截断标记与 manifest |
| 持久化 | SQLite 任务/尝试/产物/租约/outbox；CAS 完成、孤儿恢复、幂等消费 |
| 工具循环 | read/list/search/apply_patch/run_check/submit_result；路径、写入范围、预算、哈希校验 |
| 缺陷与迭代 | finding 去重/路由/修复任务、独立 QA、暂停/预算/验证积压、复盘行动入队、知识权威等级、影响图 |
| 裁判整合 | `--judge-gate`：高风险角色确定性门禁通过后追加 J1/J2；拒绝/不可用都阻塞，且不能批准失败门禁 |
| 观测 | `project.json` 记录 manifest/mode/DoD/任务/模型调用/trust；Dashboard 显示 `current_verified` 等信任标签 |
| 验收 | **146 项测试**；`eval/failure_injection.py` **20/20**；test1 游戏 **7/7**（14 个扩展 loaded/invoked/asserted） |

```bash
python -m unittest discover -s tests -v
python eval/failure_injection.py
python -m orchestrator.cli model-capabilities --offline
python start_project.py --requirements requirements/examples/csv-export/selected.md \
    --project-dir projects/example-csv-export-new --offline --template minimal-api --mode formal
# rehearsal 只用于探索，不能得到正式完成
python start_project.py --requirements requirements/examples/csv-export/selected.md \
    --project-dir projects/_rehearsal --offline --mode rehearsal
```

## 先看这几份

| 文档 | 作用 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 当前代码的架构汇总：分层、五条运行链路、账本、状态矩阵、启动方式 |
| [agentteam-v4-外部模型裁判.md](agentteam-v4-外部模型裁判.md) | v4 目标架构：外部模型裁判 J1/J2/J3 |
| [agentteam-评审报告-2026-11-16.md](agentteam-评审报告-2026-11-16.md) | 独立评审：问题清单与改进方向 |
| [修复实施记录.md](修复实施记录.md) | 对照《修复建议1.md》逐项修复与验证 |
| [specs/README.md](specs/README.md) | 任务卡/证据/决策包/裁决/Agent 规格 |
| [eval/README.md](eval/README.md) | W2/W4 评测集、金丝雀、role/prompt/KB 评测 |
| [PROJECT_PLAYBOOK.md](PROJECT_PLAYBOOK.md) | 选需求、启动项目、角色记录与优化路线 |
| [PROCESS_OPTIMIZATION.md](PROCESS_OPTIMIZATION.md) | 第一次失败的复盘、六阶段流程、DoD 与 P0–P2 提升方案 |
| [PRODUCT_REVIEW_TEAM.md](PRODUCT_REVIEW_TEAM.md) | 产品文档深析/流程细化/版本升级预演团队与门禁 |

## Windows 启动

```bat
start.bat                 :: 交互菜单（第 1 项：选设计文档开工）
start.bat project         :: 选择/拖入设计文档，创建并启动项目
start.bat project requirements\examples\csv-export\selected.md my-app offline
start.bat project "C:\designs\ledger.md" ledger-app real
start.bat check           :: 环境检查 + 自检
start.bat sim             :: v4.1 编排预演
start.bat w3              :: W3 并行/串行 + 看板构建
start.bat dashboard       :: 启动看板 http://localhost:8765
start.bat test            :: 单测 + 自检 + schema
start.bat eval            :: 离线评测套件
start.bat demo            :: 离线 12 角色示例项目
start.bat real            :: 本地 Qwen 真实示例项目
start.bat kb              :: 知识库索引与统计
start.bat setup           :: 创建本地配置并安装依赖
start.bat all             :: 本地校验流水线
```

`start.bat` 文件为纯 ASCII（英文提示），避免 Windows 控制台编码问题；详细说明见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 快速运行

```bash
# 编排层预演（无真实 LLM）
python -I sim/dryrun.py
python -I sim/selfcheck.py

# W1：检查本地模型/账本/技能
python -m orchestrator.cli check-env
python -m orchestrator.cli demo --offline
python -m orchestrator.cli skills --role ui

# W1/W2：离线评测（CI）
python eval/run_eval.py --offline

# W1/W2：真实本地模型（Qwen 3.6；无 DeepSeek Key 时裁判显式降级）
python eval/run_eval.py --real --allow-local-judge

# 配置 DEEPSEEK_API_KEY 或 Windows 用户变量 deepseek-key1 后：
# J1/J3 走 DeepSeek，J2 走本地 Qwen
python eval/run_eval.py --real

# W3：3 切片并行 / 共享文件冲突 / 契约变更影响图 / serial baseline
python sim/w3.py --mode both
python sim/w3_selfcheck.py

# 看板首页：实时项目任务 + W3 并行/串行基线
python dashboard/build.py
# open dashboard/index.html，或 python dashboard/serve.py --port 8765
# 首页实时面板读取 projects/<name>/state + logs/events.jsonl + evidence/tool-ledger.jsonl

# W4：角色 golden set + prompt 回归
python prompts/build_prompts.py
python eval/role_eval.py --offline --full
python eval/role_eval.py --real --full
python eval/prompt_regression.py --offline

# W4：知识库混合检索（bge-m3 + FTS5）
python -m orchestrator.cli kb-index
python eval/kb_eval.py

# W4：决策收件箱
python dashboard/serve.py --port 8765
# open http://localhost:8765/decisions.html

# 选需求 → 启动项目 → 查看角色记录
python -m orchestrator.requirements select   --backlog requirements/backlog.example.yaml --out requirements/examples/csv-export
python start_project.py   --requirements requirements/examples/csv-export/selected.md   --project-dir projects/example-csv-export --offline --template minimal-api
# 真实模型：--real --roles pm,product,arch,backend,frontend --kb --sandbox
# 高保证：--tool-profile standard --stop-on-gate

# P0：沙箱/工具证据/门禁/质量单测 + 签名证据校验
python -m unittest discover -s tests -v
python -m orchestrator.tool_evidence --project projects/example-csv-export --profile basic
```

## 结果

| 指标 | v3 人审批 | v4.1 编排预演 |
|---|---|---|
| 虚拟工期 | 1,910 min | 1,252 min（-34%） |
| 人决策 / 人等待 | 7 / 1,545 min | 0 / 0 |
| 裁判调用 / 等待 | — | 20 / 82 min |
| 门禁首过 | 6/7 = 86% | 3/8 = 38%（口径更严） |
| 返工 | 4 | 6（含 2 次补证） |
| 任务 | 52 | 59（成功 56 / 失败 2 / 被取代 1） |
| 证据 | 34 | 80（复用 9 / 失效 3） |
| 缺陷 | 2（致命 1） | 2（致命 1，全部闭环） |

W2 评测：

| 模式 | Judge | Canary | Agents | Revalidation | 模型调用 |
|---|---|---|---|---|---|
| `--offline` | 11/11 | 7/7 | 6/6 schema | 4/4 | stub |
| `--real --allow-local-judge` | 11/11 | 7/7 | 6/6 schema | 4/4 | 13 次 / 49s / 17.2K Token / $0（本地） |
| `--real`（DeepSeek J1/J3 + 本地 J2） | 11/11 | 7/7 | 6/6 schema | 4/4 | 约 14 次 / 55s / 19.6K Token / $0.0039，family=0 |

> `deepseek-key1` / `DEEPSEEK_API_KEY` 会自动识别，无需手动 export。真实 DeepSeek 模式下 J1/J3 与 J2（本地 Qwen）不同家族，`family_collisions=0`。`--allow-local-judge` 仅在无 Key 或离线预演时显式降级，会产生 family collision。

W3 结果（3 切片、共享 package.json/ui-tokens、X1 契约变更）：

| 指标 | Parallel | Serial baseline |
|---|---|---|
| 虚拟工期 | 1,302 min | 2,815 min |
| 平均排队等待 | 12.8 min | 60.7 min |
| 峰值并发 | 4 | 1 |
| 共享文件冲突 / 锁等待 | 3 / 85 min | 0 / 0 |
| 契约变更 / 影响任务 | 1 / 6（3 切片） | 1 / 6（3 切片） |
| 门禁首过 | 38% | 50% |
| 返工 | 7 | 6 |
| 裁判调用 / 成本 | 24 / $0.27 | 23 / $0.266 |

**并行加速比 2.16x**。共享文件冲突与锁等待是并行带来的真实成本；契约变更会失效 3 个切片的旧证据并强制 3 个复评门禁。

## 项目启动与角色记录

需求选择使用确定性评分（价值/战略/工作量/风险/依赖），选出 `now` 需求；`start_project.py` 接收需求文件和开发目录，按角色顺序执行并落盘：

```
projects/<project>/
├── artifacts/<role>/{prompt.md,request.md,output.json,summary.md,meta.json}
├── evidence/tool-ledger.jsonl      # HMAC 签名工具证据 + 哈希链
├── quality/history.jsonl           # 角色质量分历史
├── logs/events.jsonl
├── state/roles.json
├── state/progress.json             # 实时角色/序号/心跳
├── src/backend/**, src/frontend/**
├── tests/**, contracts/**, docs/**
└── README.md
```

示例：

- `projects/example-csv-export/`：12 角色离线跑通，含模板、门禁、证据与质量记录
- `projects/example-csv-export-real/`：本地 Qwen 3.6 跑 pm/product/arch/backend/frontend，backend/frontend 已生成代码文件

角色监控与调整：

```bash
python dashboard/serve.py --port 8765
# open http://localhost:8765/projects.html
```

项目角色页展示状态、门禁、质量分、模型、耗时、Token、文件、System Prompt、实际请求与输出；运行中每 2 秒自动刷新当前角色、序号和耗时（`state/progress.json` 心跳每 3 秒更新）；发现不合格时可填写调整要求并**只重跑该角色**（可选隔离沙箱与 basic/standard/full 证据 profile）。门禁未通过会自动进入决策收件箱。W3 工作台与 W4 决策收件箱原样保留。

详见 [PROJECT_PLAYBOOK.md](PROJECT_PLAYBOOK.md) 与 [projects/README.md](projects/README.md)。

## P0–P2 升级结果

| 能力 | 实现 | 验证 |
|---|---|---|
| 工具证据 + CI | `orchestrator/tool_evidence.py`；compile/unit/sast/contract/secret + 可选 api_test（schemathesis）证据；HMAC 链 | `tests/` 20 项通过；`example-csv-export` 4 条签名证据 |
| 执行沙箱 | `orchestrator/sandbox.py`：allowlist、argv-only、脱敏环境、超时、隔离副本/worktree、门禁后提升 | 沙箱测试覆盖越权/密钥/超时/提升；`--sandbox` 项目完成 |
| 角色门禁 | `orchestrator/role_gates.py`，内容/交付物/工具证据检查，失败 blocked | 通过/缺证据/失败升级三条路径均有测试 |
| 全量真实回归 | `role_eval --real --full` 与 `prompt_regression --real` | 12 角色 × 2 用例，schema/required 24/24（keyword 见 `eval/out`） |
| 检索 rerank | `orchestrator/knowledge/rerank.py`；22 用例；MRR 对比 RRF baseline | recall@5 22/22；MRR 0.92 vs baseline 0.895（离线） |
| 决策升级 | 门禁失败自动创建 `DEC-<project>-<role>` | 收件箱可见，支持 `decisions.html?id=...` 深链 |
| 质量分/趋势 | `orchestrator/quality.py` + 监控页质量页签 | 分项得分、问题、历史趋势与数据表 |
| 项目模板 | `templates/minimal-api` + `orchestrator/templates.py` | 脚手架含可运行测试、OpenAPI 与本地 semgrep 规则 |

说明：沙箱是进程级隔离，不是内核容器；standard/full 的 semgrep/trivy 在本地缺失时显式为 missing 并失败关闭，CI 会安装并跑 full。

## 游戏项目（game profile）

需求包含“游戏/玩家/关卡/Boss/职业/存档/迷宫”等关键词时，`start_project.py --project-type auto` 自动选择 `web-2d-game` 模板，并启用**项目级可玩性验收**：

- `game/index.html`：Canvas 入口与 ES Module。
- `game/js/core.js` / `game/js/main.js`：可运行基座。
- `node --test game/tests/game_logic.test.mjs`：纯逻辑。
- `node game/tests/smoke.mjs`：冒烟。
- `game/tests/qa_*.mjs`：QA 验收（群怪/掉落/存档/双人契约）。
- Chrome 无头渲染截图：证明入口实际渲染。
- `acceptance.json` 记录全部检查和签名证据；任一失败，项目状态强制 `failed`，不能靠角色摘要“完成”。

test1 游戏产品已按此重跑：产品/架构角色产出深度文档并通过 `deep_brief` 门禁，12 角色门禁通过；`acceptance.json` 6/6（entry/modules/logic/smoke/qa/render），QA 27/27；第一章 5 层 × 8–12 房间 + Boss、3 职业双技能、等级/任务、装备/词条/强化、商店/篝火/事件、3 槽存档和本地双人可玩；`F5` 或右下角“保存进度”即时存档，战斗中每 15 秒自动保存。

```bash
python start_project.py --requirements projects/test1/requirements/input.md --project-dir projects/test1-game --real --template web-2d-game --project-type game
```

## 产品评审与升级预演团队

发版/升级前先运行独立的 Product Review Team，不直接进入开发：

```bash
python start_product_review.py   --doc projects/test1/docs/product/product-baseline.md   --out reviews/test1-product --real --kb
```

11 个角色：product-lead、doc-analyst、user-researcher、flow-architect、feature-designer、ux-reviewer、tech-feasibility、release-strategist、qa-rehearsal、red-team、knowledge-curator。输出 `REFERENCE-PLAN.md`、`state/gates.json`、补丁/小版本/大版本预演、兼容/迁移/回滚方案和下一次升级清单。

示例：`reviews/test1-product/`（11/11 门禁、22/22 来源章节覆盖）；监控页 `http://localhost:8765/reviews.html`。详见 [PRODUCT_REVIEW_TEAM.md](PRODUCT_REVIEW_TEAM.md)。

## W4 结果

| 能力 | 结果 |
|---|---|
| 角色 golden set（12 角色 × 2 用例，离线） | schema 24/24 · required 24/24 · keyword 24/24 |
| 全量真实回归（12 角色 × 2 用例，本地 Qwen） | schema/required/keyword **24/24**；79.6s；25.0K Token；full_coverage=true |
| Prompt 回归（offline baseline vs strict-json） | delta 0 · regressed=false |
| Prompt 回归（real 完整 12 角色 × 2 用例） | schema/required/keyword 均 1.0；tokens 25,011 → 28,158；latency 80.1s → 86.7s；regressed=false |
| 知识库（bge-m3 + FTS5 + rerank） | 296 chunks（离线索引）；kb recall@5 **22/22**；MRR 0.92（baseline 0.895）；真实 bge-m3 22/22，MRR 0.879（0.864）；source filter 3/3 |
| 决策收件箱 | 3 个示例决策；approve / conditions / reject / defer / request evidence；审计持久化 |

角色提示词由 `specs/agent-specs.yaml` + 本地技能生成，版本和 hash 见 `prompts/registry.yaml`；知识库对应 RAGFlow 的解析/切块/embedding/混合检索/引用思想，但不引入其重型运行时；决策收件箱只处理升级、审计与 L3 策略变更，不把常规门禁退回人工。

## 模型路由

| 角色 | 主模型 | 补充 |
|---|---|---|
| 产品/UI/架构/前端/后端/评审/QA/安全/运维/知识库/复盘 | 本地 `qwen3.6:35b-a3b-mtp-q4_K_M` | DeepSeek `deepseek-chat` |
| 裁判 J1 | DeepSeek `deepseek-chat` | 本地 Qwen（仅 `--allow-local-judge`） |
| 裁判 J2 | 本地 Qwen（不同家族） | DeepSeek |
| 裁判 J3 | DeepSeek `deepseek-reasoner` | 本地 Qwen（仅显式降级） |

本地 Qwen 3.x 是推理模型；`ollama.think=false` 关闭 thinking，直接输出 JSON；`num_ctx=32768` 避免长需求被 Ollama 截断。配置见 [config/config.example.yaml](config/config.example.yaml)，密钥从 `.env`、环境变量或 Windows 用户变量 `deepseek-key1` 读取。

## 目录

```
orchestrator/          W1/W2：模型路由、裁判、证据账本、裁决账本、技能、CLI
  models/              Ollama(qwen3.6) / DeepSeek / Stub / Router；严格配置校验
  judge/               packet / verdict / panel / canary / revalidation / rubric
  evidence/            evidence store / verdict store / resolver / dependency graph / signing
  sources/             稳定来源单元解析与版本 diff
  requirements.py      确定性需求评分与选择（now/next/later）
  requirements_ledger.py 原子需求、来源处置、结构校验与 Markdown 渲染
  design_states.py     交互状态/转移/适用性检查
  context/             按任务装配的上下文包与 manifest
  iterations/          manifest、计划编译、暂停/预算/在制品控制器
  persistence/         SQLite 任务/尝试/产物/租约/outbox/仓储
  execution/           工具注册表、执行循环、能力探针
  acceptance_web.py    Web 启动/健康/业务流运行验收
  project_runner.py    需求文件 → 项目目录 → 12 角色记录/代码/日志
  findings.py          finding 去重、分诊、修复任务
  qa.py                独立 QA 验证与关闭条件
  actions.py           复盘行动 → 任务
  trust.py             项目信任标签
  sandbox.py           进程级沙箱：allowlist、脱敏环境、超时、隔离工作区
  tool_evidence.py     编译/单测/SAST/契约/密钥扫描 → HMAC 签名证据
  role_gates.py        角色门禁与决策收件箱升级
  quality.py           角色质量分与历史趋势
  templates.py         项目脚手架加载与复制
  game_check.py        游戏入口/逻辑/QA/渲染/集成验收与签名证据
  knowledge/           FTS5 + bge-m3 + RRF + rerank + 权威等级
eval/                  W2/W4 评测 + failure_injection 故障注入
dashboard/             W3 工作台 + W4 决策收件箱 + W5 角色/门禁/质量/信任监控
templates/             minimal-api 与 web-2d-game 脚手架
tools/                 默认 semgrep 规则（各项目可覆盖）
tests/                 沙箱/证据/门禁/质量/rerank/runner/8 轮优化测试
.github/workflows/     CI：单测、故障注入、能力探针、评测、预演、specs、工具证据
prompts/               12 角色版本化提示词 + 候选 v2 + registry
knowledge/             RAGFlow 风格混合检索说明（FTS5 + bge-m3 + RRF）
skills/                本地技能注册表（引用 RAG-Agent-Toolkit 的 4 个技能）
specs/                 任务卡、证据、决策包、裁决、Agent 规格、迭代清单、来源/需求
rubrics/               产品/架构/代码/验收/发布/复核 rubric
sim/                   编排协议预演（v4.1 + W3），v4.0 备份在 dryrun_v4.0.py
config/                配置示例（只放环境变量名）
requirements/          backlog、需求选择脚本与示例需求
projects/              角色运行示例（prompt/output/meta/evidence/quality/logs/src/db）
docs/optimization/     本次优化基线、轮次记录与实施报告
start_project.py       项目启动脚本（--mode formal|rehearsal）
start.bat              Windows 启动器（ASCII）
ARCHITECTURE.md        当前代码架构汇总
PROJECT_PLAYBOOK.md    选需求/启动/角色记录/门禁/质量/优化路线
```

## 当前边界

- 本次优化没有调用真实模型：能力探针真实分支默认 `skipped`；真实成功率、成本与时延仍需在目标端点测量。
- 旧项目没有迭代清单时显示 `legacy_unverified`，不会被新 DoD 自动放行；历史项目只读保留，未批量迁移。
- `state/agentteam.db` 是新权威状态；旧 `project.json`/`roles.json` 继续作为 Dashboard 兼容视图。
- SQLite 租约/outbox 通过了单进程与线程级测试，尚未做多进程高吞吐压测。
- 游戏集成证明扩展被加载、调用和断言；test1 的玩法主路径仍主要使用基座 core/main，尚未逐模块迁移。
- Dashboard 增加了信任/模式/任务摘要标签，但未重构为完整的任务/切片/缺陷/行动多层视图。
- 裁判真实调用依赖 DeepSeek Key；没有 Key 时默认失败关闭，`--allow-local-judge` 是显式降级并记录 family collision。
- 本地 Qwen 输出通过 Schema 校验与少量“格式修复”（只修 severity/line/额外字段，不改 decision/evidence），修复次数记录在 `schema_repairs`。
- 机械硬约束先于裁判执行：确定性失败、缺证据、未签名证据、越界写、高危漏洞、无回滚发布、指令性文本，裁判无权批准。
- 医疗、金融持牌等要求人工签核的场景不适用本方案。
- W3 的共享文件锁是内存租约模型；真实仓库的 worktree/锁文件/合并冲突仍需执行层。
- 知识库未直接运行 RAGFlow（依赖 Elasticsearch/MySQL/Redis），复用其检索概念；`data/knowledge.db` 可重建。
- 决策收件箱是策略所有者/审计入口；常规门禁由角色门禁与 J1/J2/J3 裁决，不逐次人工审批。
- `start_project.py` 的角色输出是**开发草稿**；工具证据、门禁、运行验收与沙箱已接入，但仍需真实测试/契约/扫描通过后才算可验收。
- 沙箱是进程级隔离（allowlist、脱敏环境、超时、隔离副本/worktree），**不是内核容器**；生产需要容器/seccomp/网络命名空间。
- 本地未安装 semgrep/trivy 时，standard/full 的对应证据显式为 missing 并失败关闭；CI 会安装并跑 full profile。
- 模板是 stdlib 脚手架，用来验证链路；真实项目需替换依赖、测试与契约，TODO 不算交付物。
- 尚未实现：容器级沙箱、工作树租约、进程崩溃恢复的完整外部副作用核对、完整 MCP 服务端、历史项目批量迁移。
- 监控工作台读取 `sim/out/w3`；重新跑 W3 后执行 `python dashboard/build.py` 刷新。
