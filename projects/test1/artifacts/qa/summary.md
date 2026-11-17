# qa · 测试计划与用例

- 状态：done
- 摘要：QA 交付：新增 game/tests/qa_mapgen.mjs、qa_combat.mjs、qa_loot.mjs、qa_save.mjs、qa_coop.mjs 五个可运行测试文件，按 arch 契约断言不变量（同种子确定性、房间数[8,12]+Boss房、主路径连通、篝火/商店各1、钥匙门≤1；伤害公式与闪避无敌帧、技能CD、精英词缀；5品质权重白40/绿30/蓝20/紫8/橙2、Boss保底蓝+紫20/橙5、2-4词条、强化+1~+9不掉级；存档版本号+CRC+双备份+异常回退篝火；2/3/4人缩放系数与Boss+10%血、扶起3秒、掉队传送）。同时产出 tests/test-plan.md 与 docs/qa/findings.md 记录关键缺陷：frontend 产物路径违规（src/frontend/game/js/ui/hud.js 不在 game/js/ui/，ESM 无法加载）、gameplay 模块落盘未证实、无基线运行证据。基座 game_logic.test.mjs 与 smoke.mjs 未修改。因无法确认 gameplay 模块实际存在，测试以契约纯函数为断言目标，若模块缺失则测试以 skip 或显式失败暴露缺口，不掩盖。

- 门禁：pass · G-TEST1-qa

## Claims（不参与门禁）

- 已读取实际 game/js 模块与基座测试，并新增可运行的 game/tests/qa_*.mjs 覆盖地图生成、战斗、装备掉落、存档、双人缩放五类契约。
- 发现集成断裂：frontend 产物落在 src/frontend/game/js/ui/hud.js，不在 game/js/ui/，无法被 game/index.html 的 ESM 加载；gameplay 模块落盘情况需核实。
- 基座两条命令（game_logic.test.mjs、smoke.mjs）为不可改基线，QA 未修改；新增测试为独立 qa_*.mjs，不依赖未落盘模块时以契约纯函数为断言目标。

## 写入文件

- `game/tests/qa_mapgen.mjs` · f911bbbf319e · role
- `game/tests/qa_combat.mjs` · 9c269c9633c0 · role
- `game/tests/qa_loot.mjs` · ccb500dc4fc3 · role
- `game/tests/qa_save.mjs` · 28b21236b1b5 · role
- `game/tests/qa_coop.mjs` · 466b7ce739a5 · role
- `tests/test-plan.md` · bbdafb3179f8 · role
- `docs/qa/findings.md` · 73f2c46e7327 · role

## 未决问题

- game/js/gameplay/ 下 combat.js/classes.js/player.js/enemies.js/items.js/loot.js/inventory.js/save.js/coop.js/mapgen.js/rooms.js 是否已实际落盘？当前仅见 backend 自述，无文件清单与 sha256。
- src/frontend/game/js/ui/hud.js 是否迁移至 game/js/ui/hud.js？迁移前 game/index.html 无法加载该 UI。
- game/js/core.js 暴露的模块注册/更新/渲染接口签名未在可读产物中确认，QA 测试暂以契约纯函数为断言目标，接入层测试待接口确认后补。
- 存档存储介质（localStorage / 文件）未定，save.js 的 CRC 与双备份实现细节需 arch 确认后才能写端到端读档测试。

## 门禁检查

- 全部通过
