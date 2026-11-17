# arch · 架构与契约

- 状态：done
- 摘要：作为架构角色，基于已批准的产品基准、项目计划与 UI 规范，产出 docs/architecture/architecture.md 与 contracts/openapi.yaml（作为模块间 JSON 契约文档，非 Web 服务）。关键决策：(1) 分层为 core 基座 / gameplay 增量模块 / ui 增量模块，gameplay 与 ui 仅通过事件总线与只读状态快照交互，禁止跨层直接引用内部实现，保证基座文件不被覆盖且 node --test game_logic.test.mjs 与 smoke.mjs 基线可继续通过；(2) 定义房间契约 RoomSpec 与生成不变量（主路径连通、每层1篝火1商店、钥匙门≤1且钥匙可达、种子+已探索可恢复）；(3) 定义战斗契约（固定步长确定性 tick、伤害管线顺序、多人缩放查表、Boss+10%、装备独立掉落分桶）；(4) 定义存档契约 SaveEnvelope（版本号、双备份+CRC、迁移链、异常退出回篝火快照）；(5) 明确非目标：不引入 React、Python Web 服务、Unity/Godot，不重写引擎。信息缺口（基座 API 细节、浏览器无 SQLite 的存档介质降级、局域网 UDP 在 Canvas 栈不可行）已写入 open_questions，未编造证据。

- 门禁：pass · G-TEST1-arch

## Claims（不参与门禁）

- 以 Canvas + 原生 ES Modules 定义垂直切片模块边界：core(基座)/gameplay(房间、战斗、掉落、存档)/ui(HUD、面板)，gameplay 与 ui 通过事件总线与只读状态快照解耦，禁止互相直接引用内部实现。
- 房间契约：RoomSpec{id,type,seed,exits[],spawns[],lootTable}，生成器保证入口到Boss主路径连通、每层1篝火1商店、钥匙门最多1且钥匙可达；读档按种子+已探索集合恢复。
- 战斗契约：确定性 tick(固定步长) + 伤害管线(基础→词条→暴击→减伤)，多人缩放系数按人数查表(1/1.6/2.1/2.6 血量等)，Boss额外+10%；掉落独立按玩家ID分桶。
- 存档契约：SaveEnvelope{version,worldSeed,roomsExplored,player,stash,quests,settings,crc}，双备份+CRC校验，版本迁移函数链，异常退出回最近篝火快照。
- contracts/openapi.yaml 以 OpenAPI 3.0 形式描述本地存档/房间/战斗事件的消息契约（作为模块间 JSON 契约文档，不引入任何 Web 服务运行时）。

## 写入文件

- `docs/architecture/architecture.md` · eeecff685ea6 · role
- `contracts/openapi.yaml` · 3821d40cdc91 · role

## 未决问题

- 基座 game/js/core.js 与 main.js 暴露的现有 API（事件总线名、状态容器、tick 入口）未在需求中给出，需在实现前读取确认，避免契约与基座冲突。
- 存档介质：需求写 JSON/SQLite，但浏览器环境无 SQLite，MVP 采用 localStorage/IndexedDB 需产品确认降级方案。
- 局域网 P1 的 UDP 同步在浏览器 Canvas 栈下不可行，需确认 P1 是否改为 WebRTC/或明确不在本技术栈内实现。

## 门禁检查

- 全部通过
