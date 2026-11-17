# backend · 后端实现

- 状态：done
- 摘要：作为 backend 角色，在 game/js/gameplay/ 下交付可运行的玩法逻辑增量模块（纯 ES Modules、无 DOM 依赖），覆盖架构契约中的战斗、掉落、房间生成与存档四块核心不变量，供 gameplay/ui 集成层与 QA 直接调用。关键决策：(1) 战斗采用固定步长确定性 tick（默认 60Hz，dt 由调用方传入整数步），伤害管线顺序固定为 基础攻击→词条加成→暴击→防御减免→多人缩放→Boss 额外血量，保证可复现；(2) 多人缩放严格按产品表查表（2/3/4 人血量 1.6/2.1/2.6、伤害 1.15/1.25/1.35、金币 1.25/1.45/1.65，Boss 血量额外 +10%），单人恒为 1.0 基准；(3) 掉落按品质权重（白40/绿30/蓝20/紫8/橙2）与 Boss 保底（蓝保底、紫20%、橙5%）实现，装备独立分桶按玩家 id 哈希，金币材料共享；(4) 房间生成实现不变量校验：主路径连通、每层恰 1 篝火 1 商店、钥匙门≤1 且钥匙可达、种子+已探索可恢复，生成失败抛错而非静默；(5) 存档 SaveEnvelope 含版本号、CRC32 校验、双备份与迁移链，异常退出回最近篝火快照。所有模块为纯函数/类，不触碰基座文件，不写 Web API。信息缺口（基座事件总线 API、浏览器存档介质降级、局域网 UDP 不可行）已写入 open_questions，未编造证据。

- 门禁：pass · G-TEST1-backend

## Claims（不参与门禁）

- 在 game/js/gameplay/ 下新增纯逻辑增量模块：确定性战斗 tick、伤害管线、多人缩放、掉落分桶、房间生成不变量、存档信封（版本+CRC+双备份+迁移链），不依赖 DOM，可被基座与 QA 直接 import。
- 所有模块只读/纯函数式，不修改 core.js/main.js/index.html 与基线测试，保持 node --test game/tests/game_logic.test.mjs 与 node game/tests/smoke.mjs 可继续通过。

## 写入文件

- `game/js/gameplay/combat.js` · 9a7d377e94d9 · role
- `game/js/gameplay/loot.js` · b70331dce519 · role
- `game/js/gameplay/roomgen.js` · 71b6f6737542 · role
- `game/js/gameplay/save.js` · 09af372f8e0c · role

## 未决问题

- 基座 core.js 暴露的事件总线与状态快照 API 细节未在需求中给出，本模块以纯函数+显式入参设计，接入时需 gameplay 集成层适配。
- 浏览器无 SQLite，存档介质降级为 localStorage + 内存双备份，CRC 用纯 JS 实现；若后续接 Node 侧持久化需再确认。
- 局域网 UDP 同步在 Canvas 栈不可行，本切片仅实现本地同屏所需的确定性 tick 与缩放，联机列 P1。

## 门禁检查

- 全部通过
