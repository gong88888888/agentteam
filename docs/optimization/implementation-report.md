# AgentTeam 优化实施报告（2026-11-18）

实施对象：`optimization-2026-11-18/` 的 18 篇方案与 T00–T31 任务卡。
基线提交：`afbfaab7e0e290373722b811bbfe536606511411`（分支 `v4.1-protocol-fixes`）。
实施方式：按依赖分 8 轮，每轮先补反例测试，再做最小修改，最后跑原有与新增回归。

## 1. 结果摘要

- 单元/集成测试：**30 → 146**，全部通过。
- 确定性故障注入：**20/20** 失败关闭（`eval/out/failure-injection.json`）。
- 原有 selfcheck、离线评测、角色评测、Prompt 回归、知识库评测、v4.1/W3 预演、Schema 校验全部保持通过。
- 审计反例 P01–P08 全部被新测试锁住：
  - P01 伪造来源 + blocked 评审 → 失败；
  - P02 单角色 + 无效入口的 Web DoD → 失败；
  - P03 空产品文档 → 失败；
  - P04 未核验证据字典 → `need_evidence`；
  - P05 旧门禁活过新失败 → 当前整体失败，历史保留；
  - P06 未知后端 → `ConfigurationError`，不再退 stub；
  - P07 前插标题 → 稳定单元 ID 不变；
  - P08 未接入游戏模块 → 集成门禁失败；test1 已注册 14 个模块。

## 2. 18 篇方案与交付对照

| 方案 | 交付 |
|---|---|
| 01 实际审查与证据 | 每项反例转为回归测试；`docs/optimization/baseline.md` 记录环境与基线 |
| 02 目标架构与统一协议 | 项目/迭代/任务/尝试/产物/事件 SQLite 账本；manifest、状态机、CAS |
| 03 文档解析与需求完整性 | `orchestrator/sources/parser.py` 稳定单元与版本 diff；`requirements_ledger.py` 原子需求与处置 |
| 04 产品设计协作与验收 | 产品评审结构化需求/处置；`design_states.py` 状态与转移检查 |
| 05 上下文与执行循环 | `ChatResult` 工具调用/finish_reason；`context/assembler.py`；`execution/loop.py` |
| 06 工具证据与真实运行验收 | `EvidenceResolver`；Web 启动/健康/业务流验收；阶段阻塞 |
| 07 持续迭代与缺陷回流 | `findings.py`、`qa.py`、`actions.py`、`iterations/controller.py` |
| 08 示例游戏专项 | 扩展注册表、manifest、集成 harness；test1 14 模块接入；修复 player.js 缺失依赖 |
| 09 持久化并发恢复 | SQLite WAL、租约、心跳、孤儿恢复、outbox、幂等消费 |
| 10 评测指标与失败注入 | `eval/failure_injection.py` 20 例；离线评测保持 |
| 11 第一阶段任务卡 | T01–T15 全部落地（T04 归入第 1/2 轮） |
| 12 第二阶段任务卡 | T16–T29 落地（T27 为可选 `--judge-gate`）；T30/T31 见“未完成/限制” |
| 13 角色提示词 | 未整篇重写；行为约束进入程序与协议（详见限制） |
| 14 接口契约字段 | 新增 4 个 schema；Python 接口与错误码 |
| 15 故障演练 | 单元/集成与 20 例注入覆盖关键演练；未做浏览器人工走查 |
| 16 发布与回退 | 本文与 `rounds.md` 给出回退边界；未执行真实发布 |
| 17 验收用例 | 24 条验收中的确定性部分由测试与注入套件覆盖 |
| 18 关键取舍 | 保留现有模块渐进改造；未整体重写、未调用付费模型 |

## 3. 主要行为变化

### 3.1 失败关闭

- 未知模型后端、真实模式显式 stub：构造 `ModelRouter` 时直接 `ConfigurationError`。
- 产品评审：缺失 status 不再默认 `done`；`blocked/failed/error` 不能通过；无效 `SRC-999` 失败。
- 产品评审覆盖：只统计当前运行注册的角色产物；请求、提示词、输入副本、历史文件不贡献分子。
- 评审重跑：当前门禁集合绑定 `run_id + source_hash + attempt_id`；失败尝试替换该角色当前门禁；未变化来源的其他门禁可复用并标记 `reused_from`。
- 角色产物：空文件、只有标题、`runner-summary` 补写均不能满足正式交付。
- 代码门禁：只接受签名账本中的证据 ID；签名、有效期、撤销、对象指纹、类型不匹配都会被拒绝。

### 3.2 完成定义

- Web 和游戏都要求已批准迭代清单（`state/manifest.json`）。
- 必需角色来自清单，不从 `state/roles.json` 反推；历史项目无清单为 `legacy_incomplete`。
- 门禁必须属于当前迭代（`run_id` 匹配）。
- Web 必须通过真实启动、健康检查和至少一条业务流；游戏必须通过入口/逻辑/冒烟/渲染/集成。
- `mode=rehearsal` 永远不能得到正式完成。
- 正式模式下上游阶段失败会跳过下游阶段并记录 `role.skipped`。

### 3.3 上下文与证据

- 下游角色收到按任务装配的文档/代码上下文包，含条目 ID、哈希、截断标记；700 字摘要只作导航。
- 每条上下文写入 `artifacts/<role>/context-manifest.json`。
- 证据消费统一走 `EvidenceResolver`；`VerifiedEvidence` 只能由解析器创建。

### 3.4 游戏集成

- 模板新增 `game/js/extensions/registry.js`、`manifest.json`、`tests/integration.mjs`。
- 生成模块通过 `export const extension = {...}` 声明；运行器自动写入 manifest。
- 集成验收要求模块可达、可 import、可调用并断言返回类型；只有文件存在或独立单测通过不算集成。
- test1 的 `player.js` 原先 import 了不存在的 cooldown/dodge 函数，本次补齐 `combat.js` 导出并完成 14 模块接入。

### 3.5 持久化与迭代

- 每个项目生成 `state/agentteam.db`：projects/iterations/tasks/attempts/artifacts/findings/verifications/actions/knowledge/events/outbox。
- 任务领取使用版本 CAS + 租约；心跳续租；过期 worker 不能提交；恢复为 `recovering` 而非直接 `ready`。`run_id` 带随机后缀，避免同秒并发运行复用任务身份。
- 事件与状态同事务写入 outbox；消费者按 `(consumer_id,event_id)` 幂等。
- 迭代控制器支持暂停/恢复、预算停止、验证积压限流和 idle 状态。
- 审计项：finding 去重、按根因路由、独立 QA 关闭、复盘行动入队、知识权威等级、类型化影响图。
- 主运行器在门禁失败时自动创建并分诊 finding（按角色/证据原因路由），并启动时恢复过期租约。
- outbox 通过 `project-view` 消费者导出 `state/domain-events.json`，按 event_id 幂等。

### 3.6 裁判整合（可选）

- `start_project.py --judge-gate` 在 backend/frontend/security/ops 的确定性门禁通过后构建决策包并调用 J1/J2。
- 机械硬约束先于裁判；确定性门禁失败时裁判根本不会被调用。
- 裁判拒绝或不可用都会把角色置为 blocked；裁判不能批准失败门禁。

### 3.7 观测与评测

- 项目 `project.json` 记录 manifest、mode、DoD、验收、任务计数、每个模型调用的实际 model/model_version/finish_reason，以及 `trust`。
- Dashboard 首页与项目页显示信任标签：`current_verified / incomplete / rehearsal / legacy_unverified`。
- 新增 `python -m orchestrator.cli model-capabilities --offline`。
- CI 增加故障注入与能力探针步骤。

## 4. 新增/修改文件索引

新增模块：

```
orchestrator/acceptance_web.py
orchestrator/sources/{__init__,parser}.py
orchestrator/requirements_ledger.py
orchestrator/design_states.py
orchestrator/context/{__init__,assembler}.py
orchestrator/iterations/{__init__,manifest,controller}.py
orchestrator/persistence/{__init__,db,tasks,events,adapter}.py
orchestrator/execution/{__init__,tools,loop,capabilities}.py
orchestrator/findings.py
orchestrator/qa.py
orchestrator/actions.py
orchestrator/knowledge/authority.py
orchestrator/trust.py
orchestrator/evidence/resolver.py
eval/failure_injection.py
specs/{iteration-manifest,source-unit,requirement,source-disposition}.schema.json
tests/test_optimization_round{1..8}.py
```

主要修改：`models/{base,router,deepseek,ollama,stub}.py`、`product_review.py`、`role_gates.py`、`process.py`、`project_runner.py`、`game_check.py`、`impact.py`、`cli.py`、`start_project.py`、`start.bat`、`dashboard/{serve,live,template,projects}.html/py`、`templates/minimal-api/**`、`templates/web-2d-game/game/**`、`projects/test1/game/**`、`sim/w3_selfcheck.py`、`.github/workflows/ci.yml`。

## 5. 实际验证记录

见 [rounds.md](rounds.md) 的最终验证表。关键数字：

- `python -m unittest discover -s tests`：146 tests OK。
- `python eval/failure_injection.py`：20/20。
- `python -m orchestrator.selfcheck`：ALL CHECKS PASSED。
- `python eval/role_eval.py --offline --full`：24/24，full_coverage=true。
- `python eval/kb_eval.py`：22/22。
- `python -I sim/selfcheck.py`、`python -I sim/w3_selfcheck.py`：ALL CHECKS PASSED。
- `test1` 游戏验收：7/7（entry/modules/logic/smoke/qa/integration/render）。
- 真实浏览器加载 test1：`window.__AGENTTEAM_EXTENSIONS__` 显示 loaded=14，14 个扩展 init 全部 ok，游戏菜单正常渲染。
- Dashboard 信任标签已用浏览器预览核对。

## 6. 未完成、限制与需要真实环境确认的事项

1. **真实模型回归未执行**：本次没有调用本地 Qwen 或 DeepSeek。能力探针的真实分支默认 `skipped`，需要显式 `--allow-network` 与已配置端点。模型成功率、成本和延迟仍需在目标机器测量。
2. **T30 历史项目迁移未全量执行**：现有 `projects/` 只读保留；test1 标记 `legacy_unverified`。没有批量重验或影子导入。
3. **T31 高并发未做压力测试**：SQLite 租约/outbox 通过单进程与线程级测试，未验证多进程高吞吐。
4. **容器级沙箱未实现**：仍是进程级 allowlist/argv/超时/隔离副本；生产需要容器、seccomp、网络命名空间。
5. **提示词未按第 13 篇整篇重写**：本轮把约束放进程序、schema、门禁与上下文，避免只靠提示词。`prompts/` 的 12 角色文本仍是上一版；后续可在不改协议的前提下迭代。
6. **测试1 的玩法模块已注册并由集成 harness 调用，但 main.js 的用户路径尚未逐一迁移到这些模块**。基础游戏仍使用自己的 core/main 逻辑；集成证据证明模块加载/调用/断言，不证明所有玩法都由增量模块驱动。
7. **Dashboard 只增加信任/模式/任务摘要标签**，未按第 10 篇重构为任务/切片/缺陷/行动的多层视图。
8. **T29 的三层评测集未扩充真实模型样本**：本轮新增的是 20 例确定性失败注入；角色/切片/迭代的真实对照仍需固定模型与预算。
9. **T27 以可选 `--judge-gate` 接入**，默认关闭，避免没有 DeepSeek Key 时把全部运行变成失败关闭；启用后裁判只能阻塞、不能批准失败门禁。
10. **T20–T24 的 finding/QA/controller/action/KB 能力已实现并有测试**，但主运行器目前只自动创建 finding 与领域事件视图，尚未形成完整的自动分诊→修复→复验→下一轮调度闭环。
11. **需求召回率、真实用户流程、长期缺陷逃逸**没有样本量，未给出百分比承诺。

## 7. 回退策略

- 行为回退：删除 `state/manifest.json` 不会让项目重新通过 DoD，而是显示 `legacy_incomplete`；这是有意的安全行为。
- 代码回退：按轮次撤销对应提交即可；数据库表均为 `CREATE IF NOT EXISTS`，旧项目 JSON 仍被 Dashboard 读取。
- 数据回退：`state/agentteam.db` 是新增文件，删除不影响旧账本与产物；不建议删除，保留历史。
- 游戏集成回退：删除 `game/js/extensions/manifest.json` 中的条目或整个文件，模块回到未集成状态；基础模板功能不受影响。

## 8. 建议的下一步

1. 在目标机器执行 `python -m orchestrator.cli model-capabilities --real --allow-network`，记录真实模型能力与成本。
2. 选一个真实小切片，按新协议跑完整“来源→需求→设计→实现→验收→反馈→修复”两轮。
3. 对一个历史项目执行只读迁移预览，确认 `legacy_unverified` 与新门禁差异。
4. 为 test1 选一个 UI 增量，把用户路径真正切到扩展模块，补充加载/调用/行为三层证据。
5. 在 CI 之外做一次两 worker 并发领取与进程中断恢复演练。
