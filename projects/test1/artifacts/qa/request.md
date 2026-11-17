# system

---
role: qa
version: 1
generated_from: specs/agent-specs.yaml
skills: ["postmortem-to-tests"]
---
# ROLE: qa

QA：基于验收标准设计正常/异常/边界/权限用例，执行测试并产出可复现证据； 不修改产品需求，不直接改业务代码。

## 工具白名单
[
  {
    "name": "read_acceptance",
    "allow": [
      "docs/product/**",
      "tests/**"
    ]
  },
  {
    "name": "write_tests",
    "allow": [
      "tests/**",
      "reports/qa/**"
    ]
  },
  {
    "name": "run_tests",
    "allow": [
      "tool:pytest",
      "tool:playwright",
      "tool:coverage"
    ]
  }
]

## 读写范围
{
  "read": [
    "docs/product/**",
    "src/**",
    "contracts/**",
    "tests/**"
  ],
  "write": [
    "tests/**",
    "reports/qa/**"
  ],
  "deny": [
    "src/**",
    "docs/**",
    "migrations/**"
  ]
}

## 禁止事项
[
  "不得修改验收标准或产品需求。",
  "不得直接改代码让测试通过。",
  "不得提交无复现步骤、无证据的缺陷。"
]

## 输出契约
只输出一个 JSON 对象，必须符合 `specs/agent-output.schema.json`：
- `task_id`、`role`、`status`、`artifacts`、`claims`、`evidence_refs`、`open_questions`、`summary`
- `claims` 不参与门禁，`counts_as_evidence` 必须为 false
- `artifacts` 每项必须含 `path` 和 `sha256`；没有真实产物时使用 `[]`
示例：{"task_id":"T-1","role":"qa","status":"done","artifacts":[],"claims":[{"claim":"一句话结论","counts_as_evidence":false}],"evidence_refs":[],"open_questions":[],"summary":"..."}

## 失败处理
{
  "retry": "用例设计不完整返回 need_evidence；执行失败记录证据，不重试掩盖。",
  "escalate_if": [
    "验收标准不可测",
    "致命缺陷阻塞",
    "同类缺陷反复出现"
  ],
  "on_exhaust": "置 BLOCKED。"
}

可用本地技能（在开始工作前先读取对应 SKILL.md，不要凭记忆代替）：
- adaptive-frontend-optimization: 审计并增量优化现有前端工作流、响应式布局、异步状态与可访问性。（RAG-Agent-Toolkit/agent-toolkit/skills/adaptive-frontend-optimization/SKILL.md）
- postmortem-to-tests: 把事故复盘转成结构化根因分析与可执行回归测试。（RAG-Agent-Toolkit/agent-toolkit/skills/postmortem-to-tests/SKILL.md）


## 项目运行器约束
你正在项目目录 `test1` 中作为 qa 工作。
这是游戏项目：只产出 game/ 下的增量模块与文档，不生成 Web 后端/React/引擎工程；保持 game/tests 的逻辑测试与 smoke 通过。
项目需求文档已经完整放在 user 消息中；不要因为缺少“额外附件、上一轮对话或具体代码路径”而返回 blocked。
先基于现有需求完成本角色的交付物；信息缺口写入 open_questions，不要编造证据。
输出只能是 JSON；如需写文件，files[].path 必须落在 `game/tests/, tests/, docs/qa/, artifacts/qa/`。
不得写项目目录之外，不得写密钥；不确定时写 open_questions，不要编造证据。


# user

# 项目需求
下面按“可落地的产品设计文档”给方案。定位为 **2D横版房间制迷宫动作冒险 + 轻刷装 + 本地多人**，气质接近4399冒险岛/小游戏：低门槛、卡通、打怪掉装、进房间探索、Boss爆装、存档成长。单人模式是完整主模式，多人是增强体验，不是把单人内容阉割后加联机。

---

## 1. 产品定义

**项目代号**：迷宫冒险家  
**平台**：PC Windows，本地运行，离线优先  
**付费**：买断制，无内购；可后续DLC加职业/章节  
**画面**：2D横版卡通像素/手绘，低配可跑  
**视角**：横版平台跳跃，房间制迷宫；房间之间有门连接，整体地图随机生成  
**目标用户**：20-40岁，怀旧4399/冒险岛、喜欢轻肉鸽、刷装备、短会话、可单人可朋友同玩  
**会话时长**：单人15-30分钟一局；完整章节2-4小时；全流程15-25小时  
**核心卖点**：
1. 单人离线完整可通关，所有Boss、装备、剧情可单人获取。
2. 本地同屏2-4人 + 局域网2-4人，朋友来了就能玩。
3. 随机迷宫 + 固定章节Boss + 装备词条，轻刷不肝。
4. 一键存档、角色独立存档、主机世界存档，防丢档。

**一句话**：一款适合下班后单人刷两层、朋友来了同屏打Boss的PC横版迷宫刷装游戏。

---

## 2. 目标用户与场景

| 用户 | 需求 | 设计回应 |
|---|---|---|
| 怀旧玩家 | 冒险岛式横版打怪、掉装、跳台 | 横版房间、平台跳跃、装备品质光柱 |
| 轻中度上班族 | 时间碎、不想重度社交 | 单局15-30分钟，随时存档，单人完整 |
| 朋友同玩 | 本地/局域网低门槛 | 本地同屏、手柄/键盘混用、无服务器 |
| 刷装玩家 | 词条、品质、Boss掉落 | 5品质、词条重铸、图鉴 |
| 手残/休闲 | 不想被高难度卡 | 三档难度、动态人数缩放、复活币 |

**关键原则**：单人模式是基准平衡；多人只做动态缩放和协作机制，不设计必须多人才能开的门/机关。

---

## 3. 核心体验与循环

### 3.1 单局循环（15-30分钟）
回城整备 → 选迷宫层/章节 → 探索8-12个房间 → 打怪掉装/金币/材料 → 事件房/商店/篝火 → 精英/Boss → 结算 → 回城分解/强化/换装 → 下一层。

### 3.2 长期循环
推章节 → 解锁难度/新词条 → 刷Boss套装 → 完成委托/图鉴 → 挑战深层迷宫 → 多职业体验。

### 3.3 情绪节奏
前3分钟给首次掉落；第5-8分钟给精英怪；第10-15分钟给Boss；回城给明确成长。避免“刷半天没提升”。

---

## 4. 游戏模式与多人规则

### 4.1 模式矩阵
| 模式 | 人数 | 说明 |
|---|---|---|
| 单人离线 | 1 | 完整剧情、掉落、Boss、存档 |
| 本地同屏 | 2-4 | 共享镜头，键盘+手柄混用；掉落独立 |
| 局域网联机 | 2-4 | 主机权威，客机加入；适合朋友同网 |
| 远程同乐 | P2 | 后续可选，不纳入MVP |

### 4.2 多人设计原则
- **所有内容单人均可完成**：不设双人开关、不设人数专属剧情。
- **动态难度**：以单人基准，2人怪物血量×1.6、伤害×1.15、掉落金币×1.25；3人×2.1/×1.25/×1.45；4人×2.6/×1.35/×1.65。Boss额外+10%血量。
- **掉落规则**：金币/材料共享拾取；装备独立掉落，每人看到自己的光柱，防抢。
- **复活规则**：单人死亡回篝火/消耗复活币；多人倒地可被队友3秒扶起，全员倒地回城。
- **存档归属**：主机保存世界进度；客机保存自己的角色背包/等级/装备。客机加入时按主机世界难度校验。
- **单人切换**：任何多人存档均可由主机切回单人继续，不锁内容。

---

## 5. 迷宫系统

### 5.1 地图结构
每层迷宫由 **8-12个房间 + 1个Boss房** 组成，房间类型：
- 战斗房：2-4波怪，清怪开门。
- 平台跳跃房：跳台+宝箱，轻解谜。
- 宝箱房：1-3个宝箱，概率陷阱。
- 商店房：买药、钥匙、随机装备。
- 篝火房：回血、存档、复活队友、快速回城。
- 事件房：赌装备、诅咒/祝福、NPC委托。
- 精英房：精英怪+高品质掉落。
- Boss房：章节Boss，必掉1件蓝+。

### 5.2 生成规则
- 采用“房间模板+门连接+关键路径”生成，保证从入口到Boss有主路径，支路给宝箱/事件。
- 每层固定1个篝火、1个商店；精英房概率60%；宝箱房2-4个。
- 钥匙门：每层最多1个，钥匙由精英怪/事件房给，避免卡死。
- 随机种子：每局生成种子，存档记录种子和已探索房间，读档可恢复。

### 5.3 章节
- 第一章“蘑菇林迷宫”：5层，教学+首个Boss。
- 第二章“废弃矿洞”：5层，陷阱+精英。
- 第三章“古代遗迹”：5层，元素怪+最终Boss。
- 通关后解锁“无尽迷宫”：层数递增，刷词条。

---

## 6. 战斗与职业

### 6.1 操作
移动、跳跃、普攻、重击、闪避、2个技能、喝药、交互。手柄/键盘均可，本地同屏支持混用。

### 6.2 三职业（MVP）
| 职业 | 定位 | 普攻 | 技能示例 | 单人友好 |
|---|---|---|---|---|
| 剑士 | 近战坦 | 三连斩 | 旋风斩、盾冲 | 高容错 |
| 法师 | 远程爆发 | 魔法弹 | 火墙、冰环 | 清怪快 |
| 游侠 | 灵活持续 | 射箭 | 后跳射击、箭雨 | 风筝Boss |

### 6.3 怪物
- 普通怪：近战冲撞、远程投掷、飞行怪、自爆怪。
- 精英怪：带1-2词缀（护盾、加速、分裂、吸血）。
- Boss：三阶段，明确前摇，掉落套装。
- AI：巡逻→发现→追击→攻击→硬直；多人时优先仇恨最近/伤害最高，避免只追主机。

### 6.4 打击感
受击闪白、顿帧80ms、屏幕轻震、掉落光柱、音效分层。低配也保证。

---

## 7. 装备与经济

### 7.1 装备部位
武器、头盔、衣服、鞋子、饰品，共5部位。每职业武器独立，防具通用。

### 7.2 品质与掉落
白、绿、蓝、紫、橙。掉落权重：白40%、绿30%、蓝20%、紫8%、橙2%；Boss保底蓝，紫概率20%，橙5%。装备带2-4条词条：攻击、暴击、攻速、生命、移速、技能冷却、金币获取等。

### 7.3 背包与仓库
背包60格，仓库200格；装备可分解为材料，材料用于强化/重铸。强化+1到+9，失败不掉级但耗材料；重铸随机1条词条，有保底。

### 7.4 经济
金币来源：打怪、卖装、任务；消耗：药、强化、重铸、商店。控制通胀：高价装备回收、每日委托上限。单机不做交易行。

---

## 8. 成长与任务

- 角色等级1-30，每级+属性点自动分配，技能点手动。
- 主线任务：每章5-8个，引导打Boss。
- 委托板：随机3个日常，奖励金币/材料，单人可完成。
- 图鉴：怪物、装备收集，给永久小加成。
- 成就：首杀、无伤Boss、四人通关等。

---

## 9. 存档系统

- **存档槽**：3个世界槽，每槽含世界进度+主机角色；客机角色单独档。
- **自动存档**：进房间、回城、Boss前、篝火；手动存档仅篝火/回城。
- **存档内容**：角色属性、背包、装备、金币、任务、地图种子、已开房间、Boss状态、设置。
- **防丢档**：双备份+CRC校验；异常退出回最近篝火。
- **版本兼容**：存档带版本号，升级自动迁移；多人客机角色版本不匹配时只读提示。
- **云存档**：MVP不做，后续可接Steam Cloud。

---

## 10. UI/UX

- 主界面：继续、新游戏、多人、设置、退出。
- HUD：血蓝、技能CD、金币、小地图、队友血条。
- 背包：品质颜色、对比箭头、一键分解白绿。
- 地图：已探索房间、Boss房、篝火图标。
- 多人：加入房间码/局域网列表；本地同屏按手柄A加入。
- 新手引导：10分钟内教会移动、打怪、捡装、回城、存档。

---

## 11. 技术方案与MVP

**引擎**：Unity 2D（或Godot）。本地运行，无强制联网。  
**架构**：单机Host权威；本地同屏单进程；局域网Host-Client，UDP同步位置/攻击/掉落。  
**数据**：JSON/SQLite存档；ScriptableObject配置装备/怪物。  
**性能**：GTX750/集显可60帧；房间加载<2秒。

**MVP范围（12周）**：
- 1章5层、3职业、20种怪、1 Boss、50件装备、单机+本地同屏2人、存档、背包、强化、商店、篝火。
- 局域网联机放P1，EA前补。

**路线**：
1. 原型4周：横版战斗+房间门+掉落。
2. MVP 12周：单人完整第一章+本地双人+存档。
3. EA 20-24周：3章、局域网4人、无尽、图鉴、成就。
4. 正式版：DLC职业/章节、远程同乐。

---

## 12. 验收指标与风险

**指标**：
- 新手10分钟内获得第一件蓝装；30分钟内击败首个精英/Boss。
- 单局15-30分钟；全流程15-25小时。
- 崩溃率<0.5%；读档成功率>99.5%。
- 单人通关率>35%；本地多人使用率>25%；好评关键词“单人能玩”“掉装爽”。

**风险与对策**：
- 多人平衡：单人基准+动态缩放；所有Boss单人可打。
- 内容量不足：房间模板组合+词条+无尽层。
- 存档兼容：版本迁移+双备份。
- 同屏镜头：共享镜头+玩家靠近自动缩放，掉队3秒传送。
- 刷装枯燥：保底掉落+委托+图鉴+重铸。

---

**最终结论**：以单人离线完整通关为第一优先级，本地同屏为差异化卖点，局域网联机为进阶；用横版房间制迷宫承接4399冒险岛的怀旧感，用轻刷装和短会话适配20-40岁用户。MVP先做“单人+本地双人+第一章+存档+掉装强化”，验证“单人能玩、朋友能来、掉落有反馈”三件事，再扩多人联机和内容量。

# 当前角色
qa · 测试计划与用例
先读实际 game/js 模块并运行测试；测试失败必须写入 findings/反馈，不能只写计划；新增可运行的 game/tests/qa_*.mjs 并列出证据。

# 游戏项目约束（必须遵守）
- 交付物是 **可运行的游戏**，入口为 `game/index.html`，不是 Web API/React 后台。
- 技术栈固定为 HTML5 Canvas + 原生 ES Modules（模板已提供）；不要生成 Python Web 服务、Flask、React 工程或 Unity/Godot 代码。
- 代码角色只写 `game/js/gameplay/` 或 `game/js/ui/` 下的增量 `.js` 模块；不要覆盖基座文件 `game/js/core.js`、`game/js/main.js`、`game/index.html`、`game/tests/game_logic.test.mjs`、`game/tests/smoke.mjs`。
- QA 只新增 `game/tests/qa_*.mjs`；基座逻辑测试与 smoke 是验收基线，不得修改。
- 必须保持 `node --test game/tests/game_logic.test.mjs` 与 `node game/tests/smoke.mjs` 通过。

# 项目模板
web-2d-game (hash 22ecf6be0c109f09)
脚手架不是完成品；必须用本次需求替换 TODO。期望交付物：tests/test-plan.md

# 前置产物摘要
- pm: 产出 docs/plan/project-plan.md：以单人离线完整第一章为第一优先级，按 8 个切片（S0 基座校验→S1 房间制迷宫→S2 横版战斗→S3 装备掉落强化→S4 存档→S5 本地双人→S6 五层章节+Boss→S7 QA/验收）给出目标、范围、依赖、交付文件前缀与逐项验收命令；明确代码只写 game/js/gameplay|ui 增量模块、QA 只加 qa_*.mjs、基座测试与 smoke 为不可改基线；多人仅动态缩放且所有内容单人可完成；信息缺口（基座接口、输入层、存储方案、局域网范围）写入 open_questions，不编造证据。 | gate=pass
- pm 文档 `docs/plan/project-plan.md` 摘要：
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
- 验
- product: 产出 docs/product/product-baseline.md：以单人离线第一章为基准，定义主菜单→选职业/难度→5层房间→战斗/掉落/商店/篝火/事件→Boss→结算→存档/读档→双人复活 的逐状态产品流程，每状态含输入、失败恢复、非目标与量化验收；明确非目标清单（不做交易行/云存档/远程同乐/必须多人机关/内购），多人仅动态缩放与扶起、独立掉落，所有内容单人可完成；给出可量化验收指标（首蓝装≤10min、首精英/Boss≤30min、单局15-30min、读档成功率>99.5%、崩溃率<0.5%、本地多人使用率>25%）与 MVP 范围边界。信息缺口写入 open_questions，未编造证据。 | gate=fail
- product 文档 `docs/product/product-baseline.md` 摘要：
# 迷宫冒险家 · 产品基准（Product Baseline）

> 角色：product · 产品架构师。本文是范围与验收基准，不做技术选型。
> 上游：docs/plan/project-plan.md（PM 切片 S0~S7）。交付物为可运行游戏，入口 game/index.html。
> 定位：2D 横版房间制迷宫动作冒险 + 轻刷装 + 本地同屏。单人离线为完整主模式，多人仅动态缩放增强。

---

## 0. 非目标清单（先写非目标，防止范围蔓延）

以下内容明确不在 MVP / 本基准范围内，任何“用户可能需要”都不作为纳入理由：

| 非目标 | 说明 |
|---|---|
| 交易行 / 玩家间交易 | 单机不做经济外部循环，仅 NPC 商店回收。 |
| 云存档 / Steam Cloud | MVP 不做，后续可选。 |
| 远程同乐 / 在线匹配 | 不纳入 MVP；局域网联机为 P1，EA 前补。 |
| 必须多人才能开的门 / 机关 / 专属剧情 | 违反“单人完整可通关”原则，一律禁止。 |
| 内购 / 付费点 | 买断制，无内购。 |
| 第 2、3 章、无尽迷宫、图鉴、成就 | 属 EA 范围，MVP 只做第一章 5 层。 |
| 局域网 4 人 | MVP 只做本地同屏 2 人；局域网 2-4 人为 P1。 |
| 职业/章节 DLC | 正式版后内容。 |
| 高难度硬核平衡 | 三档难度 + 动态缩放，以休闲可通关为基准。 |

范围红线：单人模式是平衡基准；多人只做动态缩放与协作（扶起、独立掉落），不新增单人不可达内容。

---

## 1. 主流程状态机（逐状态：输入 / 失败恢复 / 验收）

主流程：主菜单 → 选职业/难度 → 5 层房间循环 → Boss → 结算 → 存档/读档 → 双人复活。
每个状态给出：进入条件、玩家输入、系统行为、失败/异常恢复、量化验收、非目标。

### S-MAIN · 主菜单
- 进入：启动游戏。
- 输入：继续 / 新游戏 / 多人 / 设置 / 退出（键盘方向键+确认，手柄 A/十字键）。
- 系统行为：读取 3 个世界槽摘要（章节、层数、角色等级、最后存档时间）；无存档时“继续”置灰。
- 失败恢复：存档损坏 → 提示“存档损坏，已回退到备份”，加载备份槽；双备份均损坏 → 该槽标记不可用，允许新游戏，不阻塞其他槽。
- 量化验收：主菜单到可操作 ≤ 3 秒；损坏槽不导致整体崩溃（崩溃率<0.5% 口径内）。
- 非目标：不做账号登录、不做在线大厅。

### S-CLASS · 选职业 / 难度
- 进入：新游戏 或 新开世界槽。
- 输入：三职业（剑士/法师/游侠）单选；三档难度（休闲/标准/挑战）单选；确认。
- 系统行为：展示职业定位与单人友好度；难度影响怪物血量/伤害系数与掉落权重微调（口径见 §4）；写入世界槽初始状态。
- 失败恢复：未选职业/难度时确认置灰；中途返回主菜单不产生半成品存档。
- 量化验收：选择到进入第一层 ≤ 5 秒；三职业均可单人通关第一章（QA 冒烟各职业跑通 1 层）。
- 非目标：不做职业自定义捏脸、不做难度中途切换（仅回城可改，见 S-SETTLE）。

### S-ROOM · 5 层房间循环（核心）
每层 = 8-12 房间 + 1 Boss 房；固定 1 篝火、1 商店；精英房概率 60%；宝箱房 2-4；钥匙门每层 ≤1。
房间类型：战斗房 / 平台跳跃房 / 宝箱房 / 商店房 / 篝火房 / 事件房 / 精英房 / Boss 房。

- 进入：从门进入房间（或读档恢复到已探索房间）。
- 输入：移动、跳跃、普攻、重击、闪避、2 技能、喝药、交互（开门/开箱/对话/存档）。
- 系统行为：
  - 战斗房：2-4 波怪，清怪开门；掉落光柱即时反馈。
  - 平台跳跃房：跳台+宝箱，轻解谜，无死亡惩罚性陷阱秒杀。
  - 宝箱房：1-3 宝箱，概率陷阱（扣血不致死）。
  - 商店房：买药/钥匙/随机装备。
  - 篝火房：回血、存档、复活队友、快速回城。
  - 事件房：赌装备、诅咒/祝福、NPC 委托。
  - 精英房：精英怪 + 高品质掉落。
  - 钥匙门：钥匙由精英怪/事件房给，保证不卡死（无钥匙时主路径仍可通 Boss）。
- 失败恢复：
  - 单人死亡 → 回最近篝火，消耗复活币（无币则回城结算，不丢已获装备）。
  - 掉队（同屏）→ 3 秒自动传送到队友身边。
  - 房间加载失败 → 回退到上一个已存档房间，不丢档。
- 量化验收：
  - 同种子生成一致、主路径存在、篝火/商店各 1、钥匙门 ≤1（QA 地图生成测试）。
  - 单层通关时长落在单局 15-30 分钟区间内（第一章 5 层合计 2-4 小时）。
  - 前 3 分钟必出首次掉落；5-8 分钟遇精英；10-15 分钟遇 Boss（情绪节奏验收）。
- 非目标：不做必须多人协作的机关；不做房间内实时 PVP。

### S-COMBAT · 战斗与掉落（房间内子状态）
- 输入：普攻/重击/闪避/技能/喝药；手柄键盘混用（本地同屏）。
- 系统行为：受击闪白、顿帧 80ms、轻震、掉
- ui: 以单人离线第一章为基准，产出 docs/design/ui-spec.md：定义 Design Token（色彩/品质色/间距/字号/层级/动效时长）、HUD（血蓝、技能CD、金币、小地图、队友血条、Boss 条）、主菜单、背包（品质色+对比箭头+一键分解白绿）、商店、篝火、小地图、多人状态（本地同屏/局域网加入、独立掉落光柱、扶起提示）的交互规范；覆盖空/加载/错误/暂停四类状态与失败恢复文案；给出 game/css 增量样式建议（不覆盖基座），并标注可落地尺寸与状态机。多人仅动态缩放与扶起、独立掉落，不新增单人不可达 UI。信息缺口写入 open_questions，未编造证据。 | gate=pass
- ui 文档 `docs/design/ui-spec.md` 摘要：
# 迷宫冒险家 · UI/UX 设计规范（UI Spec）

> 角色：ui · UI/UX 设计师。上游：docs/product/product-baseline.md、docs/plan/project-plan.md。
> 交付物为可运行游戏，入口 game/index.html；技术栈 HTML5 Canvas + 原生 ES Modules。
> 本文只定义信息架构、交互流程、Design Token 与可落地标注，不改变产品功能与核心流程。
> 硬约束：单人基准平衡；所有 Boss/装备/剧情单人可获取；不设必须多人才能开的门/机关；多人仅动态缩放与协作（扶起、独立掉落）。

---

## 0. 设计原则

1. **单人优先**：所有界面在 1 人状态下信息完整、无空位占位；多人元素（队友血条、扶起提示）仅在人数≥2 时出现。
2. **掉落有反馈**：品质色 + 光柱 + 拾取飘字，前 3 分钟必出首次掉落（对齐产品验收）。
3. **低门槛**：主菜单到可操作 ≤3 秒；新手 10 分钟内教会移动/打怪/捡装/回城/存档。
4. **低配可跑**：动效以 CSS/Canvas 轻量实现，无重滤镜；60 帧目标下 UI 不阻塞渲染。
5. **可落地**：每个界面给出尺寸、层级、状态与交互标注，前端可直接实现。

---

## 1. Design Token

### 1.1 色彩

| Token | 值 | 用途 |
|---|---|---|
| `--c-bg-0` | `#0e1116` | 最底层背景 |
| `--c-bg-1` | `#161b22` | 面板背景 |
| `--c-bg-2` | `#1f2630` | 卡片/行背景 |
| `--c-border` | `#2d3644` | 面板描边 |
| `--c-text-1` | `#e6edf3` | 主文字 |
| `--c-text-2` | `#9aa7b4` | 次要文字 |
| `--c-text-disabled` | `#5a6673` | 置灰文字 |
| `--c-accent` | `#f2b544` | 主强调（金币/选中） |
| `--c-hp` | `#e5484d` | 生命条 |
| `--c-mp` | `#3b82f6` | 法力条 |
| `--c-xp` | `#22c55e` | 经验条 |
| `--c-danger` | `#ef4444` | 危险/错误 |
| `--c-success` | `#22c55e` | 成功/可交互 |
| `--c-warning` | `#f59e0b` | 警告/诅咒 |

### 1.2 品质色（装备）

| 品质 | Token | 值 | 光柱 |
|---|---|---|---|
| 白 | `--q-white` | `#c9d1d9` | 无 |
| 绿 | `--q-green` | `#3fb950` | 弱 |
| 蓝 | `--q-blue` | `#58a6ff` | 中 |
| 紫 | `--q-purple` | `#bc8cff` | 强 |
| 橙 | `--q-orange` | `#f0883e` | 最强 + 脉冲 |

### 1.3 间距 / 圆角 / 字号

| Token | 值 |
|---|---|
| `--sp-1` | 4px |
| `--sp-2` | 8px |
| `--sp-3` | 12px |
| `--sp-4` | 16px |
| `--sp-6` | 24px |
| `--sp-8` | 32px |
| `--radius-s` | 4px |
| `--radius-m` | 8px |
| `--radius-l` | 12px |
| `--fs-xs` | 12px |
| `--fs-s` | 14px |
| `--fs-m` | 16px |
| `--fs-l` | 20px |
| `--fs-xl` | 28px |
| `--font-ui` | `system-ui, "Microsoft YaHei", sans-serif` |
| `--font-num` | `ui-monospace, monospace` |

### 1.4 层级（z-index）

| 层 | 值 | 内容 |
|---|---|---|
| 世界 | 0 | Canvas 游戏世界 |
| HUD | 100 | 血蓝/技能/金币/小地图 |
| 提示 | 200 | 飘字/拾取提示/扶起提示 |
| 面板 | 300 | 背包/商店/篝火/暂停 |
| 弹窗 | 400 | 确认框/错误框 |
| 加载 | 500 | 加载遮罩 |

### 1.5 动效时长

| Token | 值 | 用途 |
|---|---|---|
| `--t-fast` | 120ms | 按钮反馈/悬停 |
| `--t-mid` | 200ms | 面板开合 |
| `--t-slow` | 320ms | 结算/过场 |
| `--t-toast` | 
- arch: 产出第一章架构文档与契约：确定 Canvas+ESM 分层（core 基座 / gameplay 逻辑 / ui 表现），定义房间生成（种子可复现、主路径、篝火商店各1、钥匙门≤1）、战斗（伤害公式、闪避无敌帧、技能CD、精英词缀）、装备（5品质权重、Boss保底蓝、2-4词条、强化+1~+9不掉级、重铸保底）、存档（版本号+双备份+CRC、异常回退篝火）、双人（动态缩放系数、扶起3秒、独立掉落）五类契约与不变量；给出测试入口 game/tests/qa_*.mjs 与基线命令；不引入 React/Python/引擎重写，代码仅落 game/js/gameplay|ui 增量模块。信息缺口写入 open_questions。 | gate=fail
- arch 文档 `docs/architecture/architecture.md` 摘要：
# 迷宫冒险家 · 第一章技术架构（ADR 汇总）

> 角色：arch。上游：docs/plan/project-plan.md、docs/product/product-baseline.md、docs/design/ui-spec.md。
> 交付物：可运行游戏，入口 game/index.html；技术栈固定 HTML5 Canvas + 原生 ES Modules。
> 硬约束：不引入 React / Python Web 服务 / Unity·Godot；不覆盖基座 game/js/core.js、game/js/main.js、game/index.html、game/tests/game_logic.test.mjs、game/tests/smoke.mjs；代码只写 game/js/gameplay|ui 增量模块；QA 只加 game/tests/qa_*.mjs。

---

## ADR-001 技术栈与分层

- 决策：HTML5 Canvas 2D 渲染 + 原生 ES Modules 逻辑；无构建步骤，浏览器直接加载。
- 分层：
  - 基座层（只读）：`game/js/core.js`（循环/注册/渲染钩子）、`game/js/main.js`（启动）、`game/index.html`。
  - 逻辑层 `game/js/gameplay/`：纯函数 + 状态对象，不直接触碰 DOM/Canvas，可被 node --test 导入。
  - 表现层 `game/js/ui/`：读取逻辑层状态渲染到 Canvas/DOM，不反向修改逻辑。
- 理由：逻辑与渲染解耦，使 `node --test` 可无浏览器测试；符合“不重写引擎”约束。
- 后果：所有 gameplay 模块必须无副作用导入（不访问 window/document），随机数通过注入 seed 的 PRNG。

## ADR-002 模块边界（第一章）

| 模块 | 路径 | 职责 | 依赖 |
|---|---|---|---|
| mapgen | game/js/gameplay/mapgen.js | 种子→房间图（类型/连接/主路径/钥匙门） | prng |
| rooms | game/js/gameplay/rooms.js | 房间状态机（进入/清怪/开门/宝箱/篝火） | mapgen |
| combat | game/js/gameplay/combat.js | 伤害公式、无敌帧、顿帧、命中判定 | classes |
| player | game/js/gameplay/player.js | 玩家状态、输入意图→动作 | combat, classes |
| enemies | game/js/gameplay/enemies.js | 普通怪4类+精英词缀+Boss三阶段骨架 | combat |
| classes | game/js/gameplay/classes.js | 剑士/法师/游侠数值与技能表 | — |
| items | game/js/gameplay/items.js | 部位/品质/词条生成与强化重铸 | prng |
| loot | game/js/gameplay/loot.js | 掉落权重、Boss保底、独立掉落分配 | items |
| inventory | game/js/gameplay/inventory.js | 背包60/仓库200、分解、装备对比 | items |
| save | game/js/gameplay/save.js | 存档序列化/版本迁移/双备份/CRC | — |
| coop | game/js/gameplay/coop.js | 人数缩放、扶起、掉队传送 | combat |
| hud | game/js/ui/hud.js | 血蓝/CD/金币/小地图/队友血条 | 逻辑层只读 |
| inventory_ui | game/js/ui/inventory_ui.js | 背包/商店/篝火面板 | inventory |
| menu_ui | game/js/ui/menu_ui.js | 主菜单/选职业难度/暂停 | save |

- 禁止：gameplay 模块 import ui 模块；ui 模块不得写 gameplay 状态（只读+派发意图事件）。

## ADR-003 房间生成契约（S1）

不变量（可测试）：
1. 同 seed + 同层号 → 完全相同的房间图（确定性）。
2. 房间数 ∈ [8,12]，另有 1 个 Boss 房。
3. 入口到 Boss 存在唯一主路径（连通性检查通过）。
4. 每层恰好 1 个篝火房、1 个商店房。
5. 宝箱房数量 ∈ [2,4]；精英房概率 60%（由 seed 决定）。
6. 钥匙门 ≤1；且无钥匙时主路径仍可达 Boss（钥匙门只锁支路）。

接口（纯函数）：
```js
// mapgen.js
generateFloor({ seed, floorIndex, chapter }) -> FloorGraph
// FloorG
- arch 文档 `contracts/openapi.yaml` 摘要：
# 说明：本项目为离线单机游戏，无 HTTP 服务。
# 本文件以 OpenAPI 3.0 结构描述“模块间契约”（逻辑层纯函数接口），
# 供代码角色与 QA 对齐签名；不表示存在网络 API。
openapi: 3.0.3
info:
  title: Maze Adventurer - Module Contracts (in-process, no HTTP)
  version: 1.0.0
  description: >
    第一章逻辑层契约。所有接口为 ES Module 纯函数，可在 node --test 下直接导入。
    不引入任何 Web 服务；此文件仅作接口契约文档。
paths: {}
components:
  schemas:
    FloorGraph:
      type: object
      required: [seed, floorIndex, rooms, mainPath, bossRoomId]
      properties:
        seed: { type: integer }
        floorIndex: { type: integer, minimum: 1, maximum: 5 }
        rooms:
          type: array
          items:
            type: object
            required: [id, type, doors, cleared]
            properties:
              id: { type: string }
              type:
                type: string
                enum: [combat, platform, treasure, shop, campfire, event, elite, boss]
              doors: { type: array, items: { type: string } }
              cleared: { type: boolean }
        mainPath: { type: array, items: { type: string } }
        bossRoomId: { type: string }
        keyDoor:
          type: object
          nullable: true
          properties:
            roomId: { type: string }
            keySourceRoomId: { type: string }
    Item:
      type: object
      required: [id, slot, quality, affixes, enhanceLevel]
      properties:
        id: { type: string }
        slot:
          type: string
          enum: [weapon, helmet, armor, boots, accessory]
        quality:
          type: string
          enum: [white, green, blue, purple, orange]
        affixes:
          type: array
          minItems: 2
          maxItems: 4
          items:
            type: object
            properties:
              key: { type: string }
              value: { type: number }
        enhanceLevel: { type: integer, minimum: 0, maximum: 9 }
        classRestrict:
          type: string
          nullable: true
          enum: [warrior, mage, ranger, null]
    SaveData:
      type: object
      required: [version, worldSlot, seed, floorIndex, player, inventory, gold, crc]
      properties:
        version: { type: integer }
        worldSlot: { type: integer, minimum: 1, maximum: 3 }

- backend: 按 arch 契约实现第一章玩法逻辑增量：combat.js（伤害公式含攻防/暴击/品质系数、闪避无敌帧、技能CD、顿帧标记）、classes.js（剑士/法师/游侠数值与技能表）、player.js（输入意图→动作状态机）、enemies.js（4类普通怪+精英词缀+Boss三阶段骨架+仇恨选择）、items.js（5部位/5品质/2-4词条生成、强化+1~+9失败不掉级、重铸保底）、loot.js（白40/绿30/蓝20/紫8/橙2权重、Boss保底蓝+紫20/橙5、独立掉落分配）、inventory.js（背包60/仓库200/分解/对比）、save.js（版本号+CRC+双备份+异常回退篝火）、coop.js（2/3/4人缩放系数与Boss+10%血、扶起3秒、掉队传送）。全部为无副作用纯逻辑模块，不触碰 DOM/Canvas，不修改基座与契约；接入与落盘方式列入 open_questions。 | gate=pass
- frontend: 代码文件已生成：src/frontend/game/js/ui/hud.js | gate=fail
- review: 以 review 角色对第一章前置产物做静态评审，不签发门禁结论。关键发现：(1) 交付路径违规——frontend 产物落在 src/frontend/game/js/ui/hud.js，违反“代码只写 game/js/gameplay|ui 增量模块”的硬约束，且无法被 game/index.html 的 ESM 加载；(2) 集成断裂风险——arch 契约要求 gameplay 为无副作用纯函数、ui 只读派发意图，但当前 ui 产物路径与契约模块表（game/js/ui/hud.js）不一致，需确认是否迁移；(3) 证据缺口——无任何产物 sha256、无基线测试运行输出，无法确认 game_logic.test.mjs 与 smoke.mjs 仍通过，故不将任何 Agent 自述计为证据；(4) 上游 product/arch/frontend 均 gate=fail，说明范围与契约尚未收口，评审结论需待其修复后复评。整改方向：将 hud.js 迁至 game/js/ui/ 并核对 import 路径；补齐 gameplay 模块落盘清单与导出签名；提供基线两条命令的实际运行记录；修复 product/arch 门禁失败项后重新提交评审。所有结论仅为 findings，不构成门禁判定。 | gate=pass

# 知识库引用
（未启用或无命中）

# 调整要求
（无特别调整）

# 输出要求
只输出符合 `specs/agent-output.schema.json` 的 JSON 对象。
如需写文件，增加 `"files":[{"path":"game/tests/, tests/, docs/qa/, artifacts/qa/...","content":"..."}]`；
只能写这些前缀：game/tests/, tests/, docs/qa/, artifacts/qa/；不得写项目目录之外；不得写密钥。
摘要必须包含本角色的关键决策与可验证内容，claims 不能当作证据。

