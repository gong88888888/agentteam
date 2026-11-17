# pm · 项目计划与切片

- 状态：done
- 摘要：产出 docs/plan/project-plan.md：以单人离线完整第一章为第一优先级，按 8 个切片（S0 基座校验→S1 房间制迷宫→S2 横版战斗→S3 装备掉落强化→S4 存档→S5 本地双人→S6 五层章节+Boss→S7 QA/验收）给出目标、范围、依赖、交付文件前缀与逐项验收命令；明确代码只写 game/js/gameplay|ui 增量模块、QA 只加 qa_*.mjs、基座测试与 smoke 为不可改基线；多人仅动态缩放且所有内容单人可完成；信息缺口（基座接口、输入层、存储方案、局域网范围）写入 open_questions，不编造证据。

- 门禁：pass · G-TEST1-pm

## Claims（不参与门禁）

- 将需求拆为 8 个可交付切片（S0 基座校验、S1 房间/迷宫、S2 战斗、S3 装备/掉落、S4 存档、S5 本地双人、S6 章节5层+Boss、S7 QA/验收），依赖顺序为 S0→S1→S2→S3→S4→S5→S6→S7，S3 与 S4 可并行于 S2 之后。
- 每切片给出可执行验收命令，基线为 node --test game/tests/game_logic.test.mjs 与 node game/tests/smoke.mjs，QA 新增 game/tests/qa_*.mjs。
- 单人基准平衡、所有内容单人可完成、多人仅动态缩放，作为切片验收的硬性设计约束。

## 写入文件

- `docs/plan/project-plan.md` · 17e360d37165 · role

## 未决问题

- 基座 game/js/core.js 与 main.js 暴露的模块接口（房间/战斗/存档钩子）未在需求中给出，需代码角色在 S0 阶段确认后回填计划。
- 本地双人输入（键盘+手柄）在 Canvas 模板中的输入抽象层是否已存在，需 S0 校验。
- 存档持久化在浏览器环境用 localStorage 还是 IndexedDB，需 S4 前确认（影响双备份+CRC 实现）。
- MVP 是否包含局域网联机：需求写 P1，本计划按不含局域网、仅本地同屏 2 人切片。

## 门禁检查

- 全部通过
