# arch · 架构与契约

- 状态：done
- 摘要：以 arch 角色产出 docs/architecture/architecture.md（完整章节：技术栈与分层、模块边界与目录、房间/迷宫契约与不变量、战斗与职业契约、装备掉落与强化契约、存档契约、本地双人契约、UI 只读契约、测试入口与验收命令、ADR 决策记录、风险与阻断项）。关键决策：(1) 三层分层——core 基座不可改、gameplay 纯逻辑无副作用可被 node --test 导入、ui 只读快照并派发意图；(2) 房间生成以种子确定性为不变量（同种子同布局、8-12 房间+Boss 房、主路径连通、篝火/商店各 1、钥匙门≤1）；(3) 掉落与强化以纯函数契约固定权重与保底，Boss 保底蓝+紫 20%/橙 5%；(4) 存档以版本号+CRC32+双备份+异常回退篝火为不变量，槽 ID 白名单 1-3；(5) 双人仅动态缩放（2/3/4 人血量×1.6/2.1/2.6、伤害×1.15/1.25/1.35、金币×1.25/1.45/1.65、Boss 额外+10% 血）与扶起 3 秒，所有内容单人可完成；(6) 测试入口为基座 node --test game/tests/game_logic.test.mjs 与 node game/tests/smoke.mjs 不可改，QA 只加 qa_*.mjs。阻断项：frontend 产物路径违规需迁移至 game/js/ui/，gameplay 落盘与基线运行输出未证实，故 artifacts 为空、claims 不计为证据。

- 调整要求：必须实际写出 docs/architecture/architecture.md（完整章节：模块、契约、存档、测试），不要只返回摘要；files 路径必须在 docs/architecture/。

- 门禁：pass · G-TEST1-arch

## Claims（不参与门禁）

- 产出 docs/architecture/architecture.md，定义第一章 HTML5 Canvas + 原生 ESM 的模块边界（core 基座 / gameplay 纯逻辑 / ui 只读渲染 / 存档适配层）、房间生成不变量、战斗与掉落契约、存档双备份+CRC+版本迁移、双人动态缩放与扶起、以及测试入口（基座两条命令 + qa_*.mjs）。
- 契约以纯函数签名形式给出（createRng/generateFloor/stepCombat/rollLoot/applyUpgrade/saveWorld/loadWorld/scaleForPlayers），gameplay 层无 DOM/Canvas 副作用，ui 层只读快照并派发意图，避免集成断裂。
- 明确交付路径硬约束：代码只写 game/js/gameplay|ui，frontend 的 src/frontend/game/js/ui/hud.js 必须迁移到 game/js/ui/ 才能被 game/index.html 的 ESM 加载；此为合并前阻断项。
- 存档不变量：3 世界槽、版本号+CRC32+双备份、异常退出回最近篝火、槽 ID 白名单 1-3；读档成功率>99.5% 需由 qa_save.mjs 实测，当前无运行证据。

## 写入文件

- `docs/architecture/architecture.md` · 8e0a070a1a5c · role

## 未决问题

- game/js/core.js 与 main.js 实际暴露的注册/更新/渲染/输入接口签名未在可见产物中给出，本 ADR 以约定接口描述，需 S0 基线核对后回填。
- gameplay 模块（combat/classes/player/enemies/items/loot/inventory/save/coop）是否已落盘到 game/js/gameplay/ 及其导出签名未证实，契约按约定签名书写，若不一致需以实际导出为准修订。
- hud.js 是否已从 src/frontend/game/js/ui/ 迁移到 game/js/ui/ 未证实，迁移前 ESM 加载会失败。
- 存档持久化介质（localStorage vs IndexedDB）与容量上限未定，本 ADR 只约束序列化格式与校验，不绑定介质。
- 局域网联机（P1）的 Host 权威、加入码与同步频率不在第一章 MVP 范围，需在 EA 前单独出 ADR。

## 门禁检查

- 全部通过
