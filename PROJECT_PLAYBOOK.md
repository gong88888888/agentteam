# 项目启动与优化 Playbook

## 1. 如何选定需求

不要从“想到什么做什么”开始。先维护一个 backlog，再用策略所有者设定的规则选出**一个**可验收需求。

### 需求条目必须包含

| 字段 | 说明 |
|---|---|
| `id` / `title` | 唯一标识与一句话目标 |
| `description` | 目标用户、场景、用户价值 |
| `users` | 目标用户 |
| `value` | 用户价值 0-2 |
| `strategic_fit` | 战略契合 0-2 |
| `effort` | 工作量 0-2（越高越慢） |
| `risk` | 风险 0-2（越高越危险） |
| `dependency` | 未满足依赖 0-2 |
| `acceptance` | 可观察、可测试的验收标准（必填） |
| `non_goals` | 本版本绝对不做的事（必填） |
| `constraints` | 技术/合规/时间约束 |
| `depends_on` | 前置需求 ID |

### 评分

```
评分 = (价值×2 + 战略×2 + (2-工作量) + (2-风险) + (2-依赖)) / 12 × 10
```

- ≥8 → `now`；6-8 → `next`；<6 → `later`；有未满足依赖 → `next`。
- 选择是**确定性策略**，不由执行 Agent 自由扩范围；模型只用于补充风险/验收澄清。

### 示例

```bash
python -m orchestrator.requirements select \
  --backlog requirements/backlog.example.yaml \
  --out requirements/examples/csv-export
```

示例 backlog：

| 需求 | 评分 | 结果 |
|---|---|---|
| 月度记录 CSV 导出 | 10.0 | **选中（now）** |
| 家庭共享账本 | 5.8 | later |
| 多币种记账 | 5.0 | later |

输出 `selection.md`（评分表与理由）、`selected.yaml`（机器可读）、`selected.md`（启动脚本输入）。

## 2. 启动项目

```bash
# 离线：确定性 stub + minimal-api 模板，走通 12 角色、门禁、工具证据与质量分
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export \
  --offline --template minimal-api

# 真实：本地 Qwen 3.6；DeepSeek 作为 fallback；--kb 注入知识库
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export-real \
  --real --roles pm,product,arch,backend,frontend --kb --template minimal-api

# 高保证：代码角色在隔离工作区执行，门禁通过后才提升文件
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/secure-run \
  --offline --template minimal-api --sandbox --tool-profile standard --stop-on-gate
```

参数：

| 参数 | 默认 | 作用 |
|---|---|---|
| `--requirements` | 必填 | 需求文件（建议 `selected.md`） |
| `--project-dir` | 必填 | 开发文件夹；非空目录需 `--force` |
| `--offline` / `--real` | offline | stub 或真实模型 |
| `--roles` | 12 角色 | 逗号分隔角色子集 |
| `--kb` | 关 | 检索 `data/knowledge.db` 注入上下文 |
| `--template` | 新目录 `minimal-api`，已有目录 `none` | 项目脚手架；`none` 关闭 |
| `--tool-profile` | `basic` | `basic`=编译+单测；`standard`=+SAST+契约；`full`=+密钥扫描 |
| `--sandbox` | 关 | 代码角色在临时副本/worktree 写入，门禁通过才提升 |
| `--stop-on-gate` | 关 | 任一门禁未通过即停止后续角色 |
| `--no-gates` / `--no-quality` | 开 | 关闭门禁或质量分（不推荐） |
| `--project-type` | auto | `game` / `web`；auto 根据需求关键词判断 |
| `--merge` | 关 | 保留未运行角色的记录，用于单角色重跑 |
| `--decision-db` | `data/decisions.db` | 门禁升级写入的决策库 |
| `--stop-on-error` / `--force` | 关 | 角色失败即停 / 允许写非空目录 |

### 游戏项目（game profile）

游戏需求自动使用 `web-2d-game` 模板，并在角色结束后执行**项目级验收**，不依赖角色自述：

- 入口 `game/index.html` + Canvas/ES Module。
- 逻辑 `node --test game/tests/game_logic.test.mjs`。
- 冒烟 `node game/tests/smoke.mjs`。
- QA `game/tests/qa_*.mjs`（27 项契约测试），并作为验收门禁执行。
- Chrome 无头渲染截图。
- 结果写入 `acceptance.json` 和签名证据账本；任一失败项目强制 `failed`。

模板提供第一章 5 层 × 8–12 房间 + Boss、3 职业/技能、装备词条/强化、商店/篝火/事件、3 槽存档和本地双人的 HTML5 Canvas 垂直切片；正式版再迁移 Unity/Godot 并补美术/音频/局域网。

```bash
python start_project.py --requirements projects/test1/requirements/input.md   --project-dir projects/test1-game --real --template web-2d-game --project-type game
```

## 3. 查看角色工作记录

```
projects/<project>/
├── requirements/input.md
├── .agentteam/template.json      # 模板 ID/hash/复制文件
├── artifacts/<role>/
│   ├── prompt.md                 # 系统提示词
│   ├── request.md                # 实际 system+user（含调整要求、前置摘要、KB 引用）
│   ├── output.json               # 结构化输出（schema 校验）
│   ├── summary.md                # 摘要、claims、写入文件、门禁检查
│   ├── meta.json                 # 模型/耗时/Token/门禁/质量/证据/文件
│   ├── error.json                # 失败时
│   ├── sandbox/<path>            # 沙箱未提升的代码（审阅用）
│   └── code_pass_attempt*.txt    # 代码角色原始文件块
├── src/backend/**、src/frontend/**
├── tests/**、contracts/**、docs/**
├── evidence/tool-ledger.jsonl    # HMAC 签名工具证据（哈希链）
├── quality/history.jsonl         # 每次运行的质量分历史
├── logs/events.jsonl             # role/tool/gate/quality 事件
├── state/roles.json
├── state/progress.json          # 实时当前角色/序号/心跳；运行中每 3 秒更新
├── project.json
└── README.md                     # 角色/门禁/质量执行记录表
```

### 实时进度

- 角色开始时立即写入 `state/roles.json`（status=`running`）和 `artifacts/<role>/meta.json` 占位。
- `state/progress.json` 记录 current_role、current_index、total_roles、elapsed_s、clock；运行器心跳每 3 秒刷新。
- 监控页每 2 秒轮询项目列表和当前项目：显示 pulse、运行时长、当前角色/序号；角色完成或失败后自动刷新摘要、门禁和质量。
- 模型调用本身是同步阻塞的，无法显示 token 级进度；能看到“正在调用哪个角色 + 已运行多久 + 前序角色结果”。

### 角色门禁

每个角色输出后立即执行确定性检查，结果写入 `meta.json.gate` 与 `summary.md`：

| 范围 | 检查 |
|---|---|
| 所有角色 | role 匹配、status 非 blocked、summary 非空、期望交付物存在且不是 TODO 脚手架 |
| 产品/UI/架构/评审/QA/安全/运维/知识/复盘/PM | 关键词组（同义词任一命中）+ 对应文档 |
| 后端/前端 | 至少一个角色写出文件；`compile` 与 `unit` 证据都必须 pass |
| 标准/完整 profile | 追加 `sast`、`contract_test`、`secret_scan`；缺工具则 fail-closed |
| 未通过 | 角色标记 `blocked`；自动写入决策收件箱（除非门禁关闭） |

门禁只读签名工具证据，不把 claims 当证据。`need_evidence` 会列出缺失证据类型，便于只补该检查而不是整包返工。

### 工具证据

`evidence/tool-ledger.jsonl` 每条记录包含 `subject_hash`、命令、工具版本、退出码、输出哈希、签名和哈希链。支持：

- `compile`：`python -m compileall`
- `unit`：有 pytest 用 pytest，否则 stdlib unittest；零用例视为失败
- `sast`：本地 `tools/semgrep.yml`（standard/full）
- `contract_test`：OpenAPI 3.x 结构检查（standard/full）
- `secret_scan`：trivy（full；CI 环境安装）
- `api_test`：schemathesis 对运行中的服务跑契约测试（full + `AGENTTEAM_API_BASE_URL`）

校验命令：

```bash
python -m orchestrator.tool_evidence --project projects/example-csv-export --profile basic
```

### 在监控页检查与调整角色

```bash
python dashboard/serve.py --port 8765
# http://localhost:8765/projects.html
```

- 左栏项目、中栏角色（状态/gate/质量分）、右侧页签：摘要、门禁、质量、输出、System Prompt、实际请求、Meta、文件。
- 门禁页签显示每条检查、证据 ID、缺失项和升级后的决策链接。
- 质量页签显示分项得分、问题与历史趋势（数据表可访问）。
- 重跑时可选 stub/真实模型、basic/standard/full 证据 profile、是否使用隔离沙箱；调整要求写入 `request.md`、`meta.json`、`summary.md` 和事件账本。
- 门禁升级自动进入 `decisions.html`，可按 ID 深链：`decisions.html?id=DEC-...`。

注意：**角色产出是草稿，不是生产验收**；模板只提供可运行脚手架，不等于完成了角色工作。

## 4. P0–P2 升级状态

| 优先级 | 能力 | 交付 | 状态 |
|---|---|---|---|
| P0 | 真实工具证据 + CI | `orchestrator/tool_evidence.py`、签名账本、`.github/workflows/ci.yml`、`tests/` | 完成 |
| P0 | 执行沙箱 + 隔离工作区 | `orchestrator/sandbox.py`：allowlist、argv-only、脱敏环境、超时、copy/git-worktree、门禁后提升 | 完成（进程级） |
| P1 | 角色间门禁 | `orchestrator/role_gates.py`：内容/交付物/证据检查，失败即 blocked | 完成 |
| P1 | 全量真实 prompt 回归 | `eval/role_eval.py --real --full`、`eval/prompt_regression.py --real`，记录 schema/keyword/latency/token/cost | 完成 |
| P1 | 知识库 rerank 与扩容 | `orchestrator/knowledge/rerank.py`；22 个检索用例；MRR 与 RRF baseline 对比 | 完成 |
| P2 | 决策收件箱接门禁 | 门禁失败自动创建 `DEC-<project>-<role>`，可深链审批 | 完成 |
| P2 | 角色质量分与趋势 | `orchestrator/quality.py`、`quality/history.jsonl`、监控页质量页签 | 完成 |
| P2 | 模板化项目 | `templates/minimal-api`、`orchestrator/templates.py`、`--template` | 完成 |

环境与边界：

- 沙箱是进程级隔离（allowlist、脱敏环境、超时、隔离副本/worktree），**不是内核容器**；生产需要容器/seccomp/网络命名空间。
- 本地未安装 semgrep/trivy 时，standard/full 的对应证据显式为 missing，门禁失败关闭；CI job 会安装并跑 full。
- `minimal-api` 是 stdlib 脚手架，用来验证证据/门禁链路；真实项目需替换依赖、测试与契约。
- 模板脚手架中的 TODO 不算交付物；角色未写文档时，runner 仍可生成明确标注的 `runner-summary` 便于审阅，但**它不能满足正式产物门禁**，项目会保持未完成。

## 4.1 流程门禁与 DoD

完整复盘与六阶段流程见 [PROCESS_OPTIMIZATION.md](PROCESS_OPTIMIZATION.md)。要点：preflight → product 深文档 → arch 契约 → implementation 阶段验收 → QA 真实测试 → final acceptance + DoD；任何阶段失败不能 `completed`，`start_project.py` 只有 completed 返回 0。

发版/升级前先运行产品评审团队，见 [PRODUCT_REVIEW_TEAM.md](PRODUCT_REVIEW_TEAM.md)：`python start_product_review.py --doc <新版本文档> --out reviews/<version> --real`。

## 4.2 2026-11-18 后的信任模型

- 每个项目在 `state/manifest.json` 记录本轮承诺角色、验收与文档；DoD 只检查这份集合。
- 无 manifest 的历史项目显示 `legacy_unverified`，不会自动通过。
- Web 项目必须真实启动并通过健康检查和业务流；游戏必须通过入口/逻辑/冒烟/渲染/集成。
- `--mode formal`（默认）失败会阻塞下游；`--mode rehearsal` 只用于探索，永远不是正式完成。
- 单角色“只重跑”使用 `partial_run`：只更新该角色记录，项目状态为 `partial_rerun`，不会把整个项目重新标记为完成。
- 每个项目有 `state/agentteam.db`（任务/尝试/租约/产物/事件）；`project.json` 只作兼容视图。
- Dashboard 显示 `trust`：`current_verified / incomplete / rehearsal / legacy_unverified`。

```bash
python start_project.py --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export-new --offline --template minimal-api
python eval/failure_injection.py
python -m orchestrator.cli model-capabilities --offline
```

## 5. 建议的第一个真实闭环

1. 选 `REQ-CSV`。
2. `start_project.py --real --roles pm,product,arch,backend,frontend --kb --template minimal-api --sandbox` 生成草稿。
3. 对 `src/backend/**` 跑 pytest/契约检查，对 `src/frontend/**` 跑 lint/加载态检查；standard/full profile 追加 SAST/密钥扫描。
4. 检查 `meta.json.gate` 与 `summary.md`；未通过项进入决策收件箱或补充调整要求重跑该角色。
5. 对通过门禁的切片进入 J1/J2/J3 裁判与发布门禁；把决策和复盘写入知识库。
6. 跑 `python -m unittest discover -s tests`、`sim/w3_selfcheck.py`、`eval/*`，确认没有破坏既有流程。

这条闭环跑通后，再扩共享文件冲突、契约变更影响图和更复杂的项目类型。
