# test1

- 状态：**completed**
- 需求：`requirements/input.md`
- 模板：`web-2d-game` · 工具证据 profile：`basic`
- 角色记录：`artifacts/<role>/{output.json,summary.md,meta.json,prompt.md,request.md}`
- 工具证据账本：`evidence/tool-ledger.jsonl`
- 质量历史：`quality/history.jsonl`
- 事件账本：`logs/events.jsonl`
- 状态：`state/roles.json`

## 角色执行记录

| 角色 | 标题 | 状态 | 门禁 | 质量 | 模型 | Prompt | 文件 |
|---|---|---|---|---|---|---|---|
| pm | 项目计划与切片 | done | pass | 98 | deepseek-chat | 1 / 11bdc73b9f9e300c | docs/plan/project-plan.md |
| product | 产品基准 | done | pass | 97 | deepseek-chat | 1 / 3e6de06e4795901a | docs/product/product-baseline.md |
| ui | UI/UX 设计规范 | done | pass | 99 | deepseek-chat | 1 / d79973713014ba6c | docs/design/ui-spec.md |
| arch | 架构与契约 | done | pass | 97 | deepseek-chat | 1 / fb5584fc4cae3222 | docs/architecture/architecture.md |
| backend | 后端实现 | done | pass | 76 | deepseek-chat | 1 / c57160acc7ae1330 | game/js/gameplay/classes.js, game/js/gameplay/combat.js, game/js/gameplay/player.js, game/js/gameplay/enemies.js, game/js/gameplay/items.js, game/js/gameplay/loot.js, game/js/gameplay/inventory.js, game/js/gameplay/save.js, game/js/gameplay/coop.js |
| frontend | 前端实现 | done | pass | 78 | deepseek-chat | 1 / e03e38f7405c7201 | game/js/ui/hud.js |
| review | 代码评审 | done | pass | 93 | deepseek-chat | 1 / 14bb816c171b120c | docs/reviews/review.md |
| qa | 测试计划与用例 | done | pass | 91 | stub | 1 / 75651a34fb0a2781 | tests/test-plan.md |
| security | 安全与合规 | done | pass | 96 | deepseek-chat | 1 / 029edc5b6957ee1a | docs/security/threat-model.md |
| ops | 发布与回滚 | done | pass | 97 | deepseek-chat | 1 / 9eed02c89930aed9 | docs/ops/release-plan.md, scripts/ops/build_snapshot.sh, scripts/ops/backup_save.sh, scripts/ops/rollback.sh |
| kb | 知识沉淀 | done | pass | 97 | deepseek-chat | 1 / 62e7cccb3983d9f3 | knowledge/project-notes.md |
| retro | 复盘与改进 | done | pass | 97 | deepseek-chat | 1 / d50198e7c91b58fd | docs/retro/retro.md |

## 运行游戏

- Windows：双击 `play_game.bat`，或 `cd game && python -m http.server 8787`
- 浏览器打开 `http://localhost:8787/`（或监控页的“打开游戏”）
- 验收记录：`acceptance.json`（入口/模块/逻辑/冒烟/QA/渲染）
- 玩法：P1 WASD + Space + J；P2 方向键 + K；F5 存档、F9 读档

> 这是角色产出记录，不是生产验收；代码/文档仍需门禁、证据与裁判。
