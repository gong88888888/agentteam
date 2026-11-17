# 迷宫冒险家 · 第一章技术架构（ADR）

- 角色：arch
- 范围：第一章「蘑菇林迷宫」5 层 + 单人离线 + 本地同屏 2 人 + 存档 + 掉装强化
- 技术栈：HTML5 Canvas + 原生 ES Modules（模板 web-2d-game，hash d80fc29ef44836ac）
- 非目标：React、Python/Flask Web 服务、Unity/Godot 引擎重写、服务端权威、交易行、云存档、远程同乐

> 本文只定义架构与契约，不改变产品验收标准。所有数值口径来自 product-baseline 与 ui-spec，冲突时以产品基准为准并回写本文。

---

## 1. 技术栈与分层

### 1.1 分层

| 层 | 目录 | 职责 | 可改 |
|---|---|---|---|
| 基座 | `game/js/core.js`、`game/js/main.js`、`game/index.html` | 画布、主循环、输入采集、模块注册 | 否（不可覆盖） |
| 逻辑层 | `game/js/gameplay/**` | 纯函数/纯状态机，无 DOM/Canvas 副作用，可被 node --test 导入 | 是（增量） |
| 表现层 | `game/js/ui/**`、`game/css/**` | 只读逻辑层快照并绘制，派发意图事件 | 是（增量） |
| 测试 | `game/tests/game_logic.test.mjs`、`game/tests/smoke.mjs` | 验收基线 | 否 |
| 测试 | `game/tests/qa_*.mjs` | QA 增量用例 | 是（仅新增） |

### 1.2 依赖方向（单向，禁止反向）

```
core/main (基座)
   └─> ui (表现层)  ──只读──> gameplay (逻辑层)
   └─> gameplay (逻辑层) ──不依赖──> ui / DOM / Canvas
```

- `gameplay/**` 禁止 `import` 任何 DOM、Canvas、window、localStorage 直接调用；持久化通过注入的 `storage` 适配器。
- `ui/**` 禁止修改 gameplay 内部状态，只能调用 gameplay 导出的意图函数（`dispatchIntent`）。
- 基座文件不得被覆盖；如需挂载点，由基座暴露的注册接口接入（见 §9 开放问题）。

### 1.3 目录约定（第一章）

```
game/
  index.html                # 基座，不可改
  js/
    core.js                 # 基座，不可改
    main.js                 # 基座，不可改
    gameplay/
      rng.js                # 种子随机（mulberry32）
      mapgen.js             # 房间/楼层生成
      combat.js             # 伤害/闪避/技能CD/顿帧标记
      classes.js            # 三职业数值与技能表
      player.js             # 输入意图 -> 动作状态机
      enemies.js            # 普通怪/精英词缀/Boss 三阶段/仇恨
      items.js              # 装备生成/强化/重铸
      loot.js               # 掉落权重与分配
      inventory.js          # 背包/仓库/分解/对比
      save.js               # 存档序列化/CRC/双备份/迁移
      coop.js               # 人数缩放/扶起/掉队传送
    ui/
      hud.js                # HUD 绘制
      inventory_ui.js       # 背包 UI
      menu_ui.js            # 主菜单/暂停/结算
      ui_state.js           # 只读快照适配 + 意图派发
  css/
    ui.css                  # 增量样式（Design Token）
  tests/
    game_logic.test.mjs     # 基线，不可改
    smoke.mjs               # 基线，不可改
    qa_*.mjs                # QA 增量
```

---

## 2. 房间/迷宫契约与不变量

### 2.1 契约（纯函数）

```js
// game/js/gameplay/rng.js
export function createRng(seed: number): { next(): number, int(maxExclusive: number): number }

// game/js/gameplay/mapgen.js
export function generateFloor(input: {
  seed: number,
  chapter: 1,
  floor: 1..5,
  roomCount?: 8..12
}): Floor

export function isReachable(floor: Floor, fromRoomId: string, toRoomId: string): boolean
```

`Floor` 结构：

```ts
Floor = {
  seed: number,
  chapter: number,
  floor: number,
  rooms: Room[],          // 长度 ∈ [8,12]
  bossRoomId: string,     // 独立 Boss 房，不计入 rooms
  entranceRoomId: string,
  keyDoor: { roomId: string, keySource: 'elite' | 'event' } | null, // ≤1
  mainPath: string[]      // 入口 -> Boss 的连通路径
}
Room = {
  id: string,
  type: 'combat'|'platform'|'treasure'|'shop'|'campfire'|'event'|'elite',
  doors: { to: string, locked: boolean }[],
  waves?: number,         // combat: 2..4
  chests?: number,        // treasure: 1..3
  explored: boolean
}
```

### 2.2 不变量（QA 断言目标）

1. **确定性**：同 `seed + chapter + floor` 生成完全相同的 `Floor`（含房间顺序与门连接）。
2. **房间数**：`rooms.length ∈ [8,12]`，另有且仅有 1 个 Boss 房。
3. **主路径连通**：`mainPath` 从 `entranceRoomId` 到 `bossRoomId` 全程可达（`isReachable` 为真）。
4. **固定设施**：每层恰好 1 个 `campfire`、1 个 `shop`。
5. **精英房**：概率 60%（由种子决定，可复现）。
6. **宝箱房**：2-4 个。
7. **钥匙门**：`keyDoor` 至多 1 个；若存在，钥匙来源为 `elite` 或 `event`，且该来源在主路径或可达支路上，保证不卡死。
8. **读档恢复**：存档记录 `seed` 与 `explored` 房间集合，读档后布局与已探索状态一致。

---

## 3. 战斗与职业契约

### 3.1 契约

```js
// game/js/gameplay/combat.js
export function computeDamage(input: {
  attacker: { atk: number, critRate: number, critMult: number, qualityMult: number },
  defender: { def: number },
  rng: Rng
}): { damage: number, isCrit: boolean }

export function stepCombat(state: CombatState, dtMs: number): CombatState
export function tryDodge(state: CombatState): { ok: boolean, invulnUntilMs: number }
export function tickSkillCooldowns(state: CombatState, dtMs: number): CombatState
```

### 3.2 不变量

1. 伤害 = `max(1, floor(atk * qualityMult * critMult - def * k))`，`k` 为防御系数常量，暴击由 `rng` 决定且 `critRate ∈ [0,1]`。
2. 闪避成功后进入无敌帧，无敌帧内 `computeDamage` 结果被 `stepCombat` 忽略。
3. 技能 CD 单调递减至 0，不可为负。
4. 受击顿帧标记 `hitStopMs = 80`，仅表现层消费，逻辑层只置标记。
5. 三职业（剑士/法师/游侠）数值与技能表集中在 `classes.js`，不得散落在 ui 层。
6. 精英词缀（护盾/加速/分裂/吸血）为数据驱动，1-2 条。
7. Boss 三阶段，阶段切换有明确前摇；多人仇恨选择「最近或伤害最高」，不得只追主机。

---

## 4. 装备掉落与强化契约

### 4.1 契约

```js
// game/js/gameplay/loot.js
export function rollLoot(input: {
  source: 'normal'|'elite'|'boss',
  rng: Rng,
  playerCount: 1..4
}): LootResult[]   // 每人一份独立掉落

// game/js/gameplay/items.js
export function generateItem(input: { slot, quality, rng }): Item
export function applyUpgrade(item: Item, materialCount: number): { item: Item, consumed: number }
export function rerollAffix(item: Item, rng: Rng): Item
```

### 4.2 不变量

1. 品质权重：白 40% / 绿 30% / 蓝 20% / 紫 8% / 橙 2%（普通与精英）。
2. Boss 保底：至少 1 件蓝；紫 20%、橙 5%。
3. 部位 5 种（武器/头盔/衣服/鞋子/饰品）；武器按职业独立，防具通用。
4. 词条 2-4 条，取自固定词条池（攻击/暴击/攻速/生命/移速/技能冷却/金币获取）。
5. 强化 +1~+9：失败不掉级，仅消耗材料。
6. 重铸：随机重掷 1 条词条，带保底（连续 N 次未提升则必出不低于当前档位）。
7. 多人掉落独立：每人只看到自己的光柱，金币/材料共享拾取。

---

## 5. 存档契约

### 5.1 契约

```js
// game/js/gameplay/save.js
export function serializeWorld(world: WorldState): string      // JSON + version + crc32
export function deserializeWorld(raw: string): { ok: boolean, world?: WorldState, reason?: string }
export function saveWorld(storage: StorageAdapter, slot: 1|2|3, world: WorldState): SaveResult
export function loadWorld(storage: StorageAdapter, slot: 1|2|3): LoadResult
export function migrate(raw: object, fromVersion: number): object
```

`StorageAdapter` 由基座注入（localStorage 或 IndexedDB 均可），逻辑层不直接触碰浏览器 API。

### 5.2 不变量

1. 3 个世界槽，槽 ID 白名单 `1|2|3`，非法槽 ID 直接拒绝（防路径穿越）。
2. 存档内容：角色属性、背包、装备、金币、任务、地图 `seed`、已探索房间、Boss 状态、设置、版本号。
3. 双备份：主档 + 备份档；写入先写备份再写主档，读取主档 CRC 失败时回退备份。
4. CRC32 校验失败或版本不可迁移 → `ok:false`，UI 提示并回最近篝火，不静默覆盖。
5. 自动存档点：进房间、回城、Boss 前、篝火；手动存档仅篝火/回城。
6. 版本迁移：`migrate` 逐版本升级，未知高版本只读提示。
7. 客机角色单独档，加入时按主机世界难度校验，版本不匹配只读提示。

---

## 6. 本地双人契约

### 6.1 契约

```js
// game/js/gameplay/coop.js
export function scaleForPlayers(base: { hp, dmg, gold }, playerCount: 1|2|3|4): { hp, dmg, gold }
export function reviveTick(state: CoopState, dtMs: number): CoopState
export function teleportIfLeftBehind(state: CoopState, dtMs: number): CoopState
```

### 6.2 不变量

1. 缩放系数：2 人 hp×1.6/dmg×1.15/gold×1.25；3 人 ×2.1/×1.25/×1.45；4 人 ×2.6/×1.35/×1.65；Boss 额外 +10% 血。
2. 单人基准：`playerCount=1` 时系数恒为 1，所有内容单人可完成。
3. 扶起：倒地队友被扶 3 秒（3000ms）后复活；全员倒地回城。
4. 掉队：玩家离镜头超过阈值 3 秒自动传送至队友附近。
5. 共享镜头，玩家靠近自动缩放；键盘+手柄混用由基座输入层提供。

---

## 7. UI 只读契约

```js
// game/js/ui/ui_state.js
export function snapshot(gameplayState): UiSnapshot   // 只读投影
export function dispatchIntent(intent: Intent): void  // 派发给 gameplay
```

- `UiSnapshot` 只含渲染所需字段（血蓝、技能 CD、金币、小地图、队友血条、Boss 条、背包、品质色）。
- 缺失字段做防御性默认值，避免集成断裂时崩溃。
- UI 不得写入 gameplay 状态；所有变更走 `dispatchIntent`。

---

## 8. 测试入口与验收命令

### 8.1 不可改基线

```bash
node --test game/tests/game_logic.test.mjs
node game/tests/smoke.mjs
```

### 8.2 QA 增量（只新增 `game/tests/qa_*.mjs`）

| 文件 | 断言目标 |
|---|---|
| `qa_mapgen.mjs` | 同种子确定性、房间数 [8,12]+Boss 房、主路径连通、篝火/商店各 1、钥匙门≤1 |
| `qa_combat.mjs` | 伤害公式、闪避无敌帧、技能 CD、精英词缀 |
| `qa_loot.mjs` | 5 品质权重、Boss 保底蓝+紫 20%/橙 5%、2-4 词条、强化 +1~+9 不掉级 |
| `qa_save.mjs` | 版本号+CRC+双备份、损坏回退、槽 ID 白名单 |
| `qa_coop.mjs` | 2/3/4 人缩放系数、Boss+10% 血、扶起 3 秒、掉队传送 |

### 8.3 合并前硬检查

1. 基线两条命令通过。
2. `game/index.html` 可被静态服务器加载，ESM 路径全部可解析。
3. 代码产物全部位于 `game/js/gameplay/` 或 `game/js/ui/`。
4. 无新增未登记依赖。

---

## 9. ADR 决策记录

### ADR-001 逻辑层纯函数化
- 决策：`gameplay/**` 全部为无副作用纯函数/纯状态机，持久化与渲染通过注入适配器。
- 理由：可被 `node --test` 直接导入，满足基线测试与 QA 增量测试；避免 DOM 依赖导致测试不可运行。
- 后果：UI 必须通过 `ui_state.js` 适配，增加一层投影成本。

### ADR-002 种子确定性生成
- 决策：楼层生成以 `seed + chapter + floor` 为唯一输入，使用 mulberry32。
- 理由：读档可恢复、QA 可复现、避免随机不可测。
- 后果：所有随机（掉落、词条、精英概率）必须走同一 `rng` 实例或派生实例。

### ADR-003 存档双备份 + CRC + 版本迁移
- 决策：主档+备份档，CRC32 校验，版本号逐级迁移，失败回最近篝火。
- 理由：读档成功率 >99.5% 的验收指标需要可恢复机制；单机不做反作弊，只保证损坏可恢复。
- 后果：存储介质由基座注入，逻辑层不绑定 localStorage/IndexedDB。

### ADR-004 多人仅动态缩放
- 决策：不设计人数专属门/剧情；多人只做缩放、扶起、独立掉落、掉队传送。
- 理由：单人基准平衡是硬约束，所有内容单人可完成。
- 后果：局域网联机（P1）不在第一章 MVP，需单独 ADR。

### ADR-005 交付路径硬约束
- 决策：代码只写 `game/js/gameplay/` 或 `game/js/ui/`；`src/frontend/**` 产物必须迁移。
- 理由：`game/index.html` 的 ESM 加载路径固定，路径违规导致加载失败。
- 后果：frontend 的 `src/frontend/game/js/ui/hud.js` 为合并前阻断项。

---

## 10. 风险与阻断项

| 项 | 级别 | 状态 | 关闭条件 |
|---|---|---|---|
| frontend 产物路径违规（`src/frontend/game/js/ui/hud.js`） | 阻断 | 未关闭 | 迁移至 `game/js/ui/hud.js` 并核对 import |
| gameplay 模块落盘与导出签名未证实 | 阻断 | 未关闭 | 提供 `game/js/gameplay/**` 落盘清单与导出签名 |
| 基线两条命令无运行输出 | 阻断 | 未关闭 | 提供实际运行记录 |
| 存档介质未定 | 中 | 开放 | 基座注入 `StorageAdapter` 后确认 |
| 局域网联机范围 | 低（P1） | 开放 | EA 前单独 ADR |

> 本文所有结论为架构决策，不构成运行证据；`artifacts` 为空，`claims` 不计为证据。
