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
# 离线：确定性 stub 走通 12 角色流水线，不调用模型
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export \
  --offline

# 真实：本地 Qwen 3.6；DeepSeek 作为 fallback；--kb 注入知识库
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export-real \
  --real --roles pm,product,arch,backend,frontend --kb
```

参数：

- `--requirements`：需求文件（建议 `selected.md`）
- `--project-dir`：开发文件夹；非空目录需 `--force`
- `--offline` / `--real`：stub 或真实模型
- `--roles`：逗号分隔，默认 12 角色全跑
- `--kb`：检索 `data/knowledge.db` 注入上下文
- `--stop-on-error`：首个角色失败即停止
- `--force`：允许写入已有目录

## 3. 查看角色工作记录

每个角色都有独立目录：

```
projects/<project>/
├── requirements/input.md
├── artifacts/<role>/
│   ├── prompt.md          # 本次实际使用的系统提示词
│   ├── request.md         # 实际发送的 system + user（含调整要求、前置摘要、KB 引用）
│   ├── output.json        # 结构化输出（schema 校验）
│   ├── summary.md         # 人读摘要、claims、写入文件、未决问题
│   ├── meta.json          # 模型/后端/耗时/Token/成本/prompt hash/文件/adjustment
│   └── code_pass_attempt*.txt  # 代码角色的文件块原始输出（调试）
├── src/backend/**         # 后端角色实际写出的代码
├── src/frontend/**        # 前端角色实际写出的代码
├── logs/events.jsonl      # role.started / role.finished / file.written / project.*
├── state/roles.json       # 每个角色状态与 meta
├── project.json
└── README.md              # 角色执行记录表
```

示例：

- `projects/example-csv-export/README.md`：12 角色离线结构跑通
- `projects/example-csv-export-real/README.md`：pm/product/arch/backend/frontend 真实 Qwen 跑通，backend/frontend 已写出代码文件

### 在监控页检查与调整角色

```bash
python dashboard/serve.py --port 8765
# http://localhost:8765/projects.html
```

- 左栏选项目，中栏选角色；右侧可看摘要、输出 JSON、System Prompt、实际请求、Meta、文件内容。
- 发现角色工作不合格时，在“调整并重跑该角色”里写清缺什么（例如“非目标不足，补 2 条；验收标准必须可量化”），再重跑。
- 重跑只影响该角色；调整要求写入 `request.md`、`meta.json.adjustment` 与 `logs/events.jsonl` 的 `role.started`，可追溯。
- 默认勾选 stub 便于快速验证流程；取消勾选才调用本地 Qwen/DeepSeek，耗时和成本会明显上升。

注意：**角色产出是草稿，不是生产验收**。代码角色输出仍需测试、契约证据、评审、裁判与门禁；当前 runner 只负责“按角色工作 + 留痕”，不替代 W1/W2 的门禁。

## 4. 项目优化工作（按优先级）

| 优先级 | 工作 | 为什么现在做 | 交付标准 |
|---|---|---|---|
| P0 | 真实工具证据 + CI | 当前角色输出是文本/代码草稿，门禁仍缺 pytest/schemathesis/semgrep/trivy 签名证据 | 每个代码切片有可复现工具证据；门禁只查证据 |
| P0 | 执行沙箱 + worktree | runner 能写文件，但没有隔离执行/租约，无法安全跑生成代码 | 每角色/任务独立 worktree；命令白名单；测试在沙箱执行 |
| P1 | 角色间门禁 | runner 现在是串行角色流水线，没有产品/架构/代码/验收门禁 | 每个阶段产出进入决策包 + J1/J2/J3 或硬约束 |
| P1 | 全量真实 prompt 回归 | 当前 role eval 离线全量、真实只跑子集 | 12 角色 × 2 用例真实跑完，记录 schema/keyword/latency/cost |
| P1 | 知识库 rerank 与质量 | RRF + bge-m3 已可用，但缺独立 rerank 与检索评测扩容 | recall@5 保持 7/7 以上，新增 20+ 检索用例 |
| P2 | 决策收件箱接门禁 | UI/API 已可用，但示例决策是 seed 数据 | 门禁升级/超时/分歧自动生成决策包并进入收件箱 |
| P2 | ~~项目监控页~~（已完成） | W5 已提供项目列表、角色记录、请求/输出/文件查看与单角色重跑 | `dashboard/projects.html`；后续补角色质量分与成本趋势 |
| P2 | 角色质量分与趋势 | 目前能看记录和重跑，但缺跨版本质量/成本对比 | 每次重跑记录 schema/keyword/latency/cost，生成角色趋势图 |
| P2 | 模板化项目 | 每次从零生成角色上下文 | 产品/架构/后端/前端模板与可复用资产库 |

## 5. 建议的第一个真实闭环

1. 选 `REQ-CSV`。
2. `start_project.py --real --roles pm,product,arch,backend,frontend --kb` 生成草稿。
3. 对 `src/backend/**` 跑 pytest + 契约测试，对 `src/frontend/**` 跑 lint/加载态检查。
4. 用真实证据替换 `claims`，进入代码门禁/裁判。
5. 把结果写入决策收件箱（升级项）与知识库。
6. 跑 `sim/w3.py`/评估，确认没有破坏既有流程。

这条闭环跑通后，再扩 12 角色全量、共享文件冲突、契约变更影响图和更复杂的项目类型。
