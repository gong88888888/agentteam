# 迷宫冒险家 · 架构与契约（垂直切片）

> 角色：arch。范围：HTML5 Canvas + 原生 ES Modules 垂直切片。不引入 React / Python Web 服务 / Unity / Godot，不重写引擎。
> 上游：docs/plan/project-plan.md、docs/product/product-baseline.md、docs/design/ui-spec.md。

## 1. 目标与非目标

### 目标
- 交付可运行 `game/index.html`，单人完整第一章 + 本地同屏 2 人 + 存档/背包/强化/商店/篝火。
- 定义 gameplay 与 ui 的模块边界、房间/战斗/存档契约与不变量。
- 保持基座 `game/js/core.js`、`game/js/main.js`、`game/index.html`、`game/tests/game_logic.test.mjs`、`game/tests/smoke.mjs` 不被修改，且 `node --test game/tests/game_logic.test.mjs` 与 `node game/tests/smoke.mjs` 通过。

### 非目标
- 不生成 Web API / React 工程 / 引擎工程。
- 不在本切片实现局域网联机（P1）；不实现远程同乐。
- 不修改产品验收标准与非目标。

## 2. 分层与模块边界

```
game/
  index.html            # 基座，不改
  js/core.js            # 基座：循环/输入/渲染上下文/事件总线，不改
  js/main.js            # 基座：启动装配，不改
  js/gameplay/          # 增量：纯逻辑模块（可被 node 测试直接 import）
    rooms.mjs           # 房间生成与状态机
    combat.mjs          # 战斗 tick、伤害管线、缩放
    loot.mjs            # 掉落表与独立掉落分桶
    inventory.mjs       # 背包/仓库/强化/重铸
    save.mjs            # 存档封装、CRC、迁移
    progression.mjs     # 等级/任务/委托
  js/ui/                # 增量：渲染与输入适配（依赖 gameplay 只读快照）
    hud.mjs
    panels.mjs
    screens.mjs
  tests/
    game_logic.test.mjs # 基座，不改
    smoke.mjs           # 基座，不改
    qa_*.mjs            # QA 新增
```

### 依赖规则（强制）
1. `gameplay/*` 不得 import `ui/*`，不得访问 DOM。
2. `ui/*` 只消费 gameplay 导出的**只读状态快照**与事件，不直接改 gameplay 内部对象。
3. 跨模块通信只经 `core.js` 提供的事件总线（事件名见 §6）。
4. 所有 gameplay 模块导出纯函数或 `createXxx()` 工厂，便于 node 测试无 DOM 运行。
5. 禁止新增未登记依赖；MVP 零第三方运行时依赖。

## 3. 房间契约

```ts
type RoomType = 'combat'|'platform'|'treasure'|'shop'|'campfire'|'event'|'elite'|'boss';

interface RoomSpec {
  id: string;            // 层内唯一
  type: RoomType;
  seed: number;          // 派生自世界种子 + 房间序号
  exits: Exit[];         // {to: roomId, door: 'normal'|'key', locked: boolean}
  spawns: SpawnSpec[];   // 怪物/宝箱/陷阱
  lootTableId: string;
}

interface FloorSpec {
  worldSeed: number;
  floorIndex: number;
  rooms: RoomSpec[];     // 8-12 + 1 boss
  entryRoomId: string;
  bossRoomId: string;
}
```

### 生成不变量（必须由 rooms.mjs 保证并可测试）
- I1 主路径：`entryRoomId` 到 `bossRoomId` 存在至少一条连通路径。
- I2 每层恰好 1 个 `campfire`、1 个 `shop`。
- I3 `elite` 房概率 60%（按种子确定性）。
- I4 `treasure` 房数量 ∈ [2,4]。
- I5 钥匙门 ≤ 1，且钥匙来源（精英/事件）在钥匙门之前可达；无钥匙门时不得生成 `locked` 出口。
- I6 同种子 + 同 floorIndex ⇒ 同 FloorSpec（确定性）。
- I7 读档：`worldSeed + roomsExplored + bossDefeated` 可完整恢复房间状态。

### 房间状态机
`unvisited → active → cleared`；`boss` 房 `active → cleared` 触发结算事件。

## 4. 战斗契约

### 4.1 确定性 tick
- 固定步长 `DT = 1/60`，逻辑与渲染解耦；渲染可插值。
- `stepCombat(state, input, dt)` 纯函数，同输入序列 ⇒ 同结果（可测试）。

### 4.2 伤害管线（顺序固定）
1. 基础伤害（武器 + 等级）
2. 词条加成（加法区）
3. 暴击（暴击率/暴击伤害）
4. 目标减伤/护盾
5. 取整（向下取整，最小 1）

### 4.3 多人缩放（以单人基准）
| 人数 | 怪物血量 | 怪物伤害 | 金币 |
|---|---|---|---|
| 1 | ×1.0 | ×1.0 | ×1.0 |
| 2 | ×1.6 | ×1.15 | ×1.25 |
| 3 | ×2.1 | ×1.25 | ×1.45 |
| 4 | ×2.6 | ×1.35 | ×1.65 |

Boss 额外 +10% 血量。缩放只作用于怪物侧，玩家数值不变。

### 4.4 掉落
- 金币/材料共享拾取；装备**按玩家 ID 独立分桶**，每人只见自己的光柱。
- 品质权重：白40/绿30/蓝20/紫8/橙2；Boss 保底蓝、紫20%、橙5%。
- 掉落随机源必须由 `worldSeed + roomId + killIndex` 派生，保证可复现。

## 5. 存档契约

```ts
interface SaveEnvelope {
  version: number;          // 迁移用
  slot: 0|1|2;
  worldSeed: number;
  floorIndex: number;
  roomsExplored: string[];
  bossDefeated: string[];
  player: PlayerSave;       // 属性/背包/装备/金币/技能点
  stash: ItemSave[];        // 仓库 200 格
  quests: QuestSave[];
  settings: SettingsSave;
  crc: string;              // 对除 crc 外字段的校验
}
```

### 不变量
- S1 双备份：主档 + 备份档，写入后校验 CRC，失败回退备份。
- S2 版本迁移：`migrate(env)` 链式升级，未知高版本只读提示。
- S3 自动存档点：进房间、回城、Boss 前、篝火；手动存档仅篝火/回城。
- S4 异常退出：回最近篝火快照（不丢已确认的强化/购买）。
- S5 客机角色独立档，主机世界档独立；切回单人不得锁内容。

## 6. 事件总线契约（经 core.js）

| 事件 | 方向 | 载荷 |
|---|---|---|
| `room:enter` | gameplay→ui | `{roomId, type}` |
| `room:cleared` | gameplay→ui | `{roomId}` |
| `combat:hit` | gameplay→ui | `{targetId, dmg, crit}` |
| `loot:drop` | gameplay→ui | `{playerId, itemId, quality}` |
| `save:written` | gameplay→ui | `{slot, ok}` |
| `ui:intent` | ui→gameplay | `{action, payload}` |

事件名与载荷为契约，变更需走契约评审。

## 7. 与基座/测试的兼容
- gameplay 模块为 `.mjs` 纯逻辑，可被 `node --test` 直接 import，不依赖 DOM。
- 不修改基座测试；QA 仅新增 `game/tests/qa_*.mjs`。
- smoke 通过条件：`game/index.html` 可加载、无未捕获异常、首帧渲染成功。

## 8. ADR

### ADR-001 逻辑与渲染分离
- 决策：gameplay 纯逻辑 + 固定步长，ui 只读快照。
- 理由：可测试、可复现、满足基座 node 测试。
- 代价：需维护快照序列化。

### ADR-002 确定性随机
- 决策：所有随机由 `worldSeed` 派生（房间/掉落/精英概率）。
- 理由：读档恢复与可复现测试。

### ADR-003 存档介质降级
- 决策：浏览器环境用 localStorage/IndexedDB 承载 SaveEnvelope，保留 JSON 结构。
- 理由：需求写 JSON/SQLite，但 Canvas 栈无 SQLite；结构不变便于后续迁移。
- 待确认：见 open_questions。

### ADR-004 局域网 P1 不在本栈实现
- 决策：MVP 只做本地同屏单进程；UDP 联机在浏览器栈不可行，P1 需另议（WebRTC 或独立方案）。
- 理由：遵守技术栈约束，不引入服务端。

## 9. 风险
- 基座 API 未确认 → 实现前先读 core.js/main.js。
- 存档介质降级 → 需产品确认。
- 多人缩放与掉落分桶需在本地同屏下验证不串档。
