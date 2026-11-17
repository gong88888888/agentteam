# AgentTeam 流程优化与提升方案

> 复盘：为什么第一次 `test1` 会“显示完成但游戏不可用”，以及如何把 AgentTeam 从“角色输出流水线”升级为“可验收的交付流程”。

## 1. 第一次失败的真实原因

不是单个模型能力问题，而是流程缺少“完成”的定义：

1. **需求被当成提示词，而不是交付合同**
   - 产品设计文档直接塞给 12 个角色；没有先转成可执行切片、状态流程、验收标准和任务卡。
2. **产品/架构角色没有被强制产出深度资产**
   - 产品只写功能清单，缺少主流程、失败恢复、非目标、量化验收；架构没有锁定唯一技术栈和模块契约。
3. **项目类型/模板选择错误**
   - 游戏需求套用了 `minimal-api` 模板，产出 Python API/React 片段；没有引擎/运行入口。
4. **角色门禁是“局部证据”，不是“项目完成”**
   - 后端只检查自己写的文件能否编译，历史坏文件、前端、入口、集成都不在门禁里。
5. **QA 测试没有被执行**
   - 测试文件存在就被当成通过；测试与真实模块 API 不一致也不会反馈。
6. **没有项目级 Definition of Done**
   - 没有入口、构建、渲染、QA、文档、证据中的任何一项，项目仍可能显示 `completed`。
7. **没有阶段门禁和反馈回路**
   - 产品→架构→实现→QA 全部串行；失败只记录在某个角色，不阻止下一阶段，也不生成返工任务。
8. **监控只展示“记录”，不展示“结论”**
   - 看不到项目验收明细、失败项、证据 ID、阶段状态；用户只能在最后发现不可用。
9. **上下文与模型限制**
   - 长需求被 Ollama 默认上下文截断；模型误判“缺少需求”，角色返回 blocked。

## 2. 新流程：六阶段项目生命周期

```
INTAKE → PRODUCT → DESIGN → IMPLEMENTATION → QUALITY → RELEASE
  │        │         │             │              │
需求画像  流程/验收   UI+架构契约   可运行切片      评审/QA/安全
+preflight +deep gate +contracts   +stage acceptance +QA contract tests
  │        │         │             │              │
  └────────┴─────────┴───── 每阶段失败 → 决策收件箱/阶段记录 ─────┘
                                                    │
                                    FINAL DoD + acceptance + release
```

| 阶段 | 角色 | 必须产物 | 门禁 |
|---|---|---|---|
| INTAKE | pm | 项目画像、切片顺序、依赖 | preflight：模板、入口、运行工具 |
| PRODUCT | product | 主流程状态机、异常/恢复、非目标、量化验收 | `deep_brief`：章节+长度 |
| DESIGN | ui, arch | UI 状态、模块边界、接口契约、存档契约 | 架构深度 + 文档传递 |
| IMPLEMENTATION | backend, frontend | 可运行垂直切片/增量模块 | 项目级 acceptance（入口/模块/逻辑/smoke/render） |
| QUALITY | review, qa, security | findings、可执行 QA、威胁模型 | **执行真实 `qa_*.mjs`**，失败不得当通过 |
| RELEASE | ops, kb, retro | 发布/回滚、知识、复盘 | 最终 acceptance + DoD |

### 项目 Definition of Done（DoD）

`orchestrator/process.py` 对每个项目计算：

- 角色全部 `done`，没有 `blocked/error`；
- 每个角色门禁 `pass`；
- 产品/架构文档存在；
- 运行入口存在（game `game/index.html`，web `src/backend/app.py`）；
- game 项目项目级 acceptance `pass`（入口/模块/逻辑/smoke/QA/Chrome 渲染）；
- 任一失败：项目不能 `completed`，并写入 `dod`、`stages`、`process_metrics`。

### 阶段验收

- 代码角色完成后立即跑 `implementation` 阶段 acceptance，不等到最后。
- QA 完成后跑 `quality` 阶段 acceptance，真实执行 `game/tests/qa_*.mjs`。
- 阶段失败写入 `state/stages.json`、`logs/events.jsonl`，并自动生成 `DEC-<project>-STAGE-<stage>` 决策包。
- 最终 acceptance 仍必须通过；`start_project.py` 只有 `completed` 才返回 0，`partial/failed` 返回非零，适合 CI。

## 3. 角色与契约优化

- **产品角色**：从“功能清单”升级为“可执行流程 + 状态/输入/失败恢复 + 量化验收 + 非目标”。
- **架构角色**：锁定唯一运行时、模块边界、导出签名、存档/事件契约；不允许混合 Web/React/引擎。
- **实现角色**：只写授权增量目录；基座入口/核心/基座测试受保护。
- **QA 角色**：先读实际模块，测试失败必须写 findings；QA 测试是门禁输入，不是文档附件。
- **下游上下文**：产品/架构/UI/QA 的文档正文（截断）传给后续角色，不再只传摘要。
- **游戏契约模块**：`maze/mapgen/combat/loot/items/save/coop/actors/events` 作为可被 Node 直接 import 的纯逻辑契约。

## 4. 监控与反馈

监控页现在展示：

- 项目类型、模板、证据 profile、门禁计数、质量均值；
- 项目 acceptance 的逐项检查、✓/✗、evidence id；
- 阶段记录（implementation/quality）与阶段决策；
- 运行中当前角色/序号/心跳；
- 单角色调整重跑，失败自动进入决策收件箱。

## 5. 提升方案（按优先级）

### P0（本轮已落地）

- preflight：项目类型、模板、入口、Node/Python 工具检查。
- 产品/架构深度文档门禁。
- 项目级 acceptance + DoD，失败关闭。
- QA 契约测试真实执行，失败可见。
- 阶段 acceptance（implementation/quality）与阶段决策。
- 长需求 `num_ctx=32768`、状态/claims 归一化、角色文件 scope。

### P1（建议下一步）

1. **自动返工循环**：阶段失败 → 自动生成角色修复任务（带失败项/证据/命令），重跑 1 次；仍失败才升级决策。
2. **任务 DAG 与切片**：pm 产出 task cards（输入/输出/依赖/验收/owner），runner 按 DAG 而非固定角色顺序执行。
3. **能力适配器**：Godot/Unity/Node/Python 能力探测；引擎缺失时明确选择浏览器切片或阻塞，而不是静默套错模板。
4. **契约注册表**：模块导出签名、消费者测试、变更影响图联动 W3。
5. **项目级 golden set**：web/game 各 3 个项目基准，检查首次可运行率、false-complete 率、返工次数。

### P2（规模化）

- 角色级成本/时延预算与降级策略；
- 并行切片 + 共享文件租约 + 合并冲突；
- 运行器崩溃恢复、worktree 隔离、容器沙箱；
- 质量趋势、模型/提示词版本对比、自动金丝雀；
- 发布门禁与回滚演练证据接入 CI。

## 6. 关键指标

| 指标 | 目标 |
|---|---|
| 首次项目可运行率 | ≥ 90% |
| false-complete（显示完成但不可运行） | 0 |
| QA 测试真实执行率 | 100% |
| 阶段失败有决策记录 | 100% |
| 产品/架构深度文档通过率 | 100% |
| 单项目返工轮次 | ≤ 1（自动修复后） |
| 验收证据可追溯 | 100%（evidence id + subject hash） |

## 7. 命令

```bash
# 新项目（自动识别 game/web）
python start_project.py --requirements <需求.md> --project-dir projects/<name> --real

# 只重跑一个角色并保留其他人
python start_project.py --requirements <需求.md> --project-dir projects/<name> \
  --real --merge --roles qa --force --note "按验收失败项修复"
```

```bash
python dashboard/serve.py --port 8765
# http://localhost:8765/projects.html
```

## 8. 当前边界

- 自动返工、任务 DAG、引擎能力适配器仍列 P1，尚未全部实现。
- 游戏正式版仍需 Unity/Godot、正式美术/音频/局域网；当前是可运行第一章 MVP 切片。
- 阶段验收目前覆盖 game profile；web profile 的 acceptance 仍以角色门禁 + 工具证据为主，后续补项目级 smoke。
