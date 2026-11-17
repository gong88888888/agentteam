# pm · 项目计划与切片

- 状态：done
- 摘要：产出 docs/plan/project-plan.md：定义项目目标（单人离线完整通关优先、本地同屏差异化、局域网P1）、MVP范围（第一章5层、3职业、20怪、1 Boss、50装备、单人+本地双人、存档/背包/强化/商店/篝火）、功能切片 S0-S8 与依赖顺序、门禁规则（node --test game_logic.test.mjs 与 node game/tests/smoke.mjs 必须通过，QA 只新增 qa_*.mjs，代码只写 game/js/gameplay|ui 增量模块）、角色分工（pm/arch/gameplay/ui/qa/reviewer/judge）与升级路径。所有切片以可运行 game/index.html 为交付形态，技术栈固定 Canvas + 原生 ES Modules。

- 门禁：pass · G-TEST1-pm

## Claims（不参与门禁）

- 项目以单人离线完整通关为第一优先级，本地同屏为差异化卖点，局域网联机为P1；MVP聚焦第一章5层+3职业+存档+掉装强化。
- 功能切片按基座→战斗→房间迷宫→掉落装备→存档→UI→本地双人→联机的依赖顺序推进，每片以逻辑测试与smoke为门禁。

## 写入文件

- `docs/plan/project-plan.md` · 4fd67fd5a0f2 · role

## 未决问题

- 基座 game/js/core.js 与 main.js 已暴露的模块接口（如场景切换、输入、渲染循环）未在需求中给出，需代码角色首轮读取后回填依赖细节。
- MVP 是否包含局域网联机需产品确认：需求写 P1/EA前补，但验收指标含本地多人使用率，建议 MVP 仅本地同屏。
- 装备词条数值表与怪物数值表由谁产出（策划文档 vs 代码内配置）未定，建议由 pm 在 plan 中列为 docs/plan 子文档由后续角色补。

## 门禁检查

- 全部通过
