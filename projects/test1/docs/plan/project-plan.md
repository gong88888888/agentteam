# 迷宫冒险家 · 项目计划与切片（PM）

> 定位：2D 横版房间制迷宫动作冒险 + 轻刷装 + 本地同屏。单人离线为完整主模式，多人仅动态缩放增强。
> 交付物：可运行游戏，入口 `game/index.html`；技术栈 HTML5 Canvas + 原生 ES Modules。
> 不可改基线：`game/js/core.js`、`game/js/main.js`、`game/index.html`、`game/tests/game_logic.test.mjs`、`game/tests/smoke.mjs`。

## 0. 全局约束（所有切片适用）

- 代码角色只新增/修改 `game/js/gameplay/` 或 `game/js/ui/` 下的增量 `.js` 模块，不覆盖基座文件。
- QA 只新增 `game/tests/qa_*.mjs`，不改基座测试。
- 每个切片合并前必须通过基线：
  - `node --test game/tests/game_logic.test.mjs`
  - `node game/tests/smoke.mjs`
- 设计硬约束：单人基准平衡；所有 Boss/装备/剧情单人可获取；不设必须多人才能开的门/机关；多人只做动态缩放与协作（扶起、独立掉落）。
- 数值口径（多人缩放，供 S5 验收）：2 人 血×1.6/伤×1.15/金×1.25；3 人 ×2.1/×1.25/×1.45；4 人 ×2.6/×1.35/×1.65；Boss 额外 +10% 血。

## 1. 切片总览与依赖顺序

```
S0 基座校验
  └─> S1 房间制迷宫
        └─> S2 横版战斗
              ├─> S3 装备/掉落/强化
              └─> S4 存档
                    └─> S5 本地双人（依赖 S2+S3+S4）
                          └─> S6 五层章节 + Boss（依赖 S1~S5）
                                └─> S7 QA/验收（贯穿，最终收口）
```

- S3 与 S4 可在 S2 完成后并行。
- S5 必须在 S2/S3/S4 之后，因为双人需要战斗、独立掉落、主机世界存档。
- S6 是内容整合切片，最后做，避免内容返工。
- S7 从 S1 起持续补 `qa_*.mjs`，S6 后做全量验收。

## 2. 切片明细

### S0 · 基座校验（0.5 周）
- 目标：确认模板可跑、模块加载方式、输入抽象、渲染循环钩子。
- 范围：只读基座，产出接口说明到 `artifacts/pm/`。
- 交付：`artifacts/pm/baseline-notes.md`（接口/钩子清单）。
- 验收命令：
  - `node --test game/tests/game_logic.test.mjs`
  - `node game/tests/smoke.mjs`
- 退出条件：两条命令通过，且记录 `game/js/core.js` 暴露的模块注册/更新/渲染接口。

### S1 · 房间制迷宫（1.5 周）
- 目标：8-12 房间 + Boss 房，房间模板+门连接+关键路径；固定 1 篝火 1 商店；精英房 60%；宝箱房 2-4；钥匙门每层≤1。
- 交付模块：`game/js/gameplay/rooms.js`、`game/js/gameplay/mapgen.js`（种子可复现）。
- 验收命令：
  - 基线两条命令
  - `node --test game/tests/qa_mapgen.mjs`（同种子生成一致、主路径存在、篝火/商店各 1、钥匙门≤1）

### S2 · 横版战斗（2 周）
- 目标：移动/跳跃/普攻/重击/闪避/2 技能/喝药；三职业（剑士/法师/游侠）；普通怪 4 类 + 精英词缀 + Boss 三阶段骨架；受击闪白、顿帧 80ms、轻震。
- 交付模块：`game/js/gameplay/combat.js`、`game/js/gameplay/player.js`、`game/js/gameplay/enemies.js`、`game/js/gameplay/classes.js`。
- 验收命令：
  - 基线两条命令
  - `node --test game/tests/qa_combat.mjs`（伤害公式、闪避无敌帧、技能 CD、精英词缀生效）

### S3 · 装备 / 掉落 / 强化（1.5 周）
- 目标：5 部位、5 品质权重（白40/绿30/蓝20/紫8/橙2）、Boss 保底蓝（紫20/橙5）、2-4 词条、背包 60/仓库 200、分解、强化 +1~+9 失败不掉级、重铸保底。
- 交付模块：`game/js/gameplay/items.js`、`game/js/gameplay/loot.js`、`game/js/gameplay/inventory.js`、`game/js/ui/inventory_ui.js`。
- 验收命令：
  - 基线两条命令
  - `node --test game/tests/qa_loot.mjs`（品质权重分布、Boss 保底、词条数量区间、强化不掉级、重铸保底）

### S4 · 存档（1 周）
- 目标：3 世界槽；自动存档（进房间/回城/Boss 前/篝火）；手动仅篝火/回城；双备份+CRC；版本号迁移；异常退出回最近篝火。
- 交付模块：`game/js/gameplay/save.js`、`game/js/ui/save_ui.js`。
- 验收命令：
  - 基线两条命令
  - `node --test game/tests/qa_save.mjs`（CRC 校验、双备份回退、版本迁移、种子与已探索房间恢复）

### S5 · 本地同屏双人（1.5 周）
- 目标：2 人共享镜头、键盘+手柄混用、装备独立掉落光柱、金币材料共享、倒地 3 秒扶起、全员倒地回城、动态缩放按第 0 节口径。
- 交付模块：`game/js/gameplay/coop.js`、`game/js/gameplay/input.js`、`game/js/ui/hud_coop.js`。
- 验收命令：
  - 基线两条命令
  - `node --test game/tests/qa_coop.mjs`（2 人缩放数值、独立掉落不串、扶起计时、单人可完成同内容）

### S6 · 五层章节 + Boss（2 周）
- 目标：第一章“蘑菇林迷宫”5 层、20 种怪、1 Boss、50 件装备、商店/篝火/事件房、新手 10 分钟引导（移动/打怪/捡装/回城/存档）。
- 交付模块：`game/js/gameplay/chapter1.js`、`game/js/gameplay/boss.js`、`game/js/ui/tutorial.js`。
- 验收命令：
  - 基线两条命令
  - `node --test game/tests/qa_chapter1.mjs`（5 层可达、Boss 三阶段、保底蓝、单人通关路径存在）

### S7 · QA / 验收（贯穿，收口 1 周）
- 目标：全量回归 + 指标校验。
- 指标：新手 10 分钟内首蓝；30 分钟内首精英/Boss；单局 15-30 分钟；读档成功率>99.5%（逻辑层模拟）。
- 验收命令：
  - `node --test game/tests/game_logic.test.mjs`
  - `node game/tests/smoke.mjs`
  - `node --test game/tests/qa_*.mjs`
- 退出条件：全部通过；`game/index.html` 可加载并进入第一章。

## 3. 里程碑

| 里程碑 | 含切片 | 周期 | 出口标准 |
|---|---|---|---|
| M0 基座就绪 | S0 | 0.5 周 | 基线通过 + 接口说明 |
| M1 可探索可战斗 | S1+S2 | 3.5 周 | 迷宫可走、三职业可打 |
| M2 有成长有存档 | S3+S4 | 2.5 周 | 掉装强化可用、读档可靠 |
| M3 双人可玩 | S5 | 1.5 周 | 本地 2 人同屏通过 |
| M4 第一章完整 | S6 | 2 周 | 5 层+Boss 单人可通关 |
| M5 验收 | S7 | 1 周 | 全量测试通过 |

合计约 11 周，留 1 周缓冲对齐 12 周 MVP。

## 4. 风险与对策（计划视角）

- 基座接口不明 → S0 先冻结接口，后续切片只依赖已冻结接口。
- 双人改动波及单人 → 所有多人逻辑走缩放/协作开关，单人路径默认关闭，S5 验收含“单人可完成同内容”。
- 存档兼容 → S4 起存档带版本号，S6 内容变更必须走迁移。
- 内容量 → 房间模板组合 + 词条 + 无尽层（EA 阶段）。

## 5. 待确认（open questions）

1. `game/js/core.js`/`main.js` 暴露的模块注册与更新/渲染钩子具体签名。
2. Canvas 模板是否已有输入抽象层（键盘+手柄混用）。
3. 浏览器存档用 localStorage 还是 IndexedDB（影响双备份+CRC）。
4. 局域网联机确认不在本次 MVP 切片内（需求列为 P1）。
