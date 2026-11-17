# 迷宫冒险家 · 第一章复盘（Retro）

> 角色：retro。上游：docs/plan/project-plan.md、docs/product/product-baseline.md、docs/design/ui-spec.md、docs/architecture/architecture.md、contracts/openapi.yaml、tests/test-plan.md、docs/qa/findings.md、docs/security/threat-model.md。
> 原则：不追责个人、不修改基准/规则/职责；只给可验证的流程与规则优化。所有结论为 findings，不构成门禁判定。
> 证据口径：本复盘未获得任何产物 sha256 与基线命令实际运行输出，故不将任何 Agent 自述计为证据。

---

## 1. 时间线（按切片与角色交付顺序）

| 序 | 角色 | 交付 | 门禁 | 观察 |
|---|---|---|---|---|
| 1 | pm | docs/plan/project-plan.md（S0~S7 切片） | pass | 切片依赖清晰，明确不可改基线与多人仅缩放 |
| 2 | product | docs/product/product-baseline.md | fail | 范围与非目标完整，但门禁未过，需查失败项 |
| 3 | ui | docs/design/ui-spec.md（Design Token/状态机） | pass | Token 与品质色可落地 |
| 4 | arch | docs/architecture/architecture.md + contracts/openapi.yaml | fail | 契约完整，但门禁未过 |
| 5 | backend | gameplay 纯逻辑模块（combat/classes/player/enemies/items/loot/inventory/save/coop） | pass | 自述落盘，无 sha256 佐证 |
| 6 | frontend | src/frontend/game/js/ui/hud.js | fail | 路径违规：不在 game/js/ui/ |
| 7 | review | 静态评审 findings | pass | 已识别路径违规与证据缺口 |
| 8 | qa | game/tests/qa_*.mjs + tests/test-plan.md + docs/qa/findings.md | pass | 以契约为断言目标，模块缺失显式失败 |
| 9 | security | docs/security/threat-model.md | pass | 存档完整性/路径违规列为高危 |
| 10 | ops | 发布与回滚方案 | fail | 因路径违规与无基线证据阻断 |
| 11 | kb | knowledge/project-notes.md | pass | 归档决策与数值口径 |

---

## 2. 偏差（计划 vs 实际）

| 编号 | 偏差 | 影响 | 严重度 |
|---|---|---|---|
| D-01 | frontend 产物路径 src/frontend/game/js/ui/hud.js 违反代码只写 game/js/gameplay|ui 硬约束 | ESM 无法被 game/index.html 加载；ui 层缺失 | 高 |
| D-02 | arch 模块表声明 game/js/ui/hud.js，与 frontend 实际路径不一致 | 契约-实现断裂，集成风险 | 高 |
| D-03 | 全链路无产物 sha256、无基线两条命令运行输出 | 基线仍通过不可证实，验收不可信 | 高 |
| D-04 | product、arch、frontend、ops 四个角色 gate=fail | 范围/契约/落盘/发布门禁未收口 | 中 |
| D-05 | gameplay 模块落盘未证实，qa_*.mjs 以契约为断言目标 | 测试可能对空实现通过或显式失败，覆盖率存疑 | 中 |
| D-06 | 读档成功率>99.5%、崩溃率<0.5% 无量化手段 | 验收指标不可测 | 中 |

---

## 3. 根因分析（5 Whys 归纳，不指向个人）

**根因 R-01：交付路径校验缺失（流程）**
- 为什么路径违规未被拦截？→ 无落盘前缀门禁检查。
- 为什么无门禁？→ 切片计划只写代码只写 game/js/gameplay|ui，未定义自动校验命令。
- 结论：约束停留在文档，未转为可执行校验。

**根因 R-02：证据链强制缺失（流程）**
- 为什么无法确认基线通过？→ 无强制要求提交 sha256 与命令输出。
- 为什么无强制？→ 输出契约允许 artifacts 为空且 claims 不计证据，但未要求有产物必附 sha256、有测试必附输出。
- 结论：证据可被省略，导致自述与事实混淆。

**根因 R-03：契约-实现对齐缺失（协作）**
- 为什么 arch 模块表与 frontend 路径不一致？→ 契约发布后无实现路径回填核对环节。
- 结论：契约与落盘之间缺少一次对齐检查。

**根因 R-04：门禁失败未闭环（协作）**
- 为什么 product/arch/frontend/ops 均 fail 仍继续下游？→ 下游未强制等待上游 gate=pass。
- 结论：切片依赖顺序存在，但门禁依赖未强制。

---

## 4. 行动项（owner / deadline / verification）

> deadline 以切片内相对时间给出，避免虚构绝对日期；verification 均为可执行命令或可核对产物。

| 编号 | 行动项 | owner | deadline | verification |
|---|---|---|---|---|
| A-01 | 将 hud.js 迁移至 game/js/ui/hud.js，核对 import 路径与 arch 模块表一致 | frontend | S5 前 | 文件存在于 game/js/ui/；node game/tests/smoke.mjs 通过；人工确认 index.html 可加载 |
| A-02 | 补齐 gameplay 模块落盘清单与导出签名，逐项对照 contracts/openapi.yaml | backend | S3 结束前 | 清单文件存在；node --test game/tests/qa_*.mjs 全通过 |
| A-03 | 所有产物提交 sha256 清单，测试提交命令输出摘要 | 全体代码/QA 角色 | 每个切片合并前 | sha256 清单存在且可复算；输出含两条基线命令结果 |
| A-04 | 新增落盘前缀校验规则：产物路径必须匹配 game/js/(gameplay|ui)/ 或 game/tests/qa_*.mjs | pm（规则）/ review（检查） | S1 起生效 | review findings 中路径违规项为 0 |
| A-05 | 强制门禁依赖：上游 gate=fail 时下游不得标记 done | pm | 立即 | 切片状态表中无上游 fail 下游 pass 组合 |
| A-06 | 为读档成功率/崩溃率定义可测口径（qa_save.mjs 往返 N 次统计） | qa | S4 结束前 | qa_save.mjs 输出成功率数值；阈值 >99.5% |
| A-07 | 修复 product/arch/ops 门禁失败项并复评 | product/arch/ops | 各自切片内 | 复评 gate=pass |

---

## 5. 规则/流程优化建议（不修改基准，仅建议）

1. 证据最小集：任何 status=done 且 artifacts 非空时，必须附 sha256；任何声称测试通过必须附命令与输出摘要。
2. 路径白名单校验：将代码只写 game/js/gameplay|ui、QA 只加 qa_*.mjs 转为可执行检查项，纳入 review 必查清单。
3. 契约回填核对：arch 发布契约后，代码角色落盘时回填实际路径，review 核对一致性。
4. 门禁依赖显式化：切片状态表增加上游 gate 列，上游 fail 时下游状态置 blocked 而非 done。

---

## 6. 升级判断

- 系统性流程问题：是（R-01/R-02/R-03 跨多角色重复出现）→ 按失败处理 escalate。
- 偏差超阈值：路径违规 + 四角色 gate=fail，判定超阈值。
- 同类问题连续 3 次：路径/证据缺口在 review、qa、security、ops 中重复暴露 ≥3 次 → 触发升级。

结论：本复盘升级至流程负责人，建议在 S5 前完成 A-01/A-03/A-04/A-05；未完成前相关切片置 BLOCKED，不默认通过。

---

## 7. 未证实项（open questions，不编造证据）

- 基座 core.js 模块注册/更新/渲染接口签名。
- gameplay 模块是否实际落盘及导出签名。
- 基线两条命令最近运行结果与时间戳。
- 存档双备份+CRC+版本迁移实现与 qa_save.mjs 通过情况。
- 本地同屏 2 人缩放与扶起 3 秒是否在可运行版本生效。
