# QA Findings · 第一章

> 只记录可复现缺陷与证据缺口，不修改产品需求与业务代码。

## F-01 交付路径违规（阻塞集成）
- 现象：frontend 产物落在 `src/frontend/game/js/ui/hud.js`，不在 `game/js/ui/`。
- 影响：`game/index.html` 的 ESM 无法加载该 UI，HUD 不显示。
- 复现：检查文件路径；`game/index.html` 中 import 路径为 `./js/ui/hud.js`。
- 期望：迁移至 `game/js/ui/hud.js` 并核对 import。
- 证据：路径对比（无 sha256，待产物落盘后补）。

## F-02 gameplay 模块落盘未证实
- 现象：backend 自述已实现 combat/classes/player/enemies/items/loot/inventory/save/coop，但无文件清单与 sha256。
- 影响：qa_*.mjs 无法确认导入成功；测试以契约纯函数为断言目标，模块缺失时显式失败。
- 复现：`node --test game/tests/qa_mapgen.mjs` 若报“模块缺失”即为缺口。
- 期望：提供 `game/js/gameplay/` 文件清单与导出签名。

## F-03 无基线运行证据
- 现象：无 `game_logic.test.mjs` 与 `smoke.mjs` 的实际运行输出。
- 影响：读档成功率>99.5%、崩溃率<0.5% 无法量化。
- 期望：提供两条命令的运行记录。

## F-04 存档介质未定
- 现象：localStorage / 文件未定，save.js CRC 与双备份实现细节未确认。
- 影响：端到端读档测试无法编写。
- 期望：arch 确认存储方案。
