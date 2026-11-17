# frontend · 前端实现

- 状态：done
- 摘要：代码文件已生成：game/js/ui/hud.js

- 调整要求：files[].path 必须以 game/js/ui/ 或 game/css/ 开头；不要加 src/frontend 或 src/backend；写增量模块并保持契约。

- 门禁：pass · G-TEST1-frontend

## Claims（不参与门禁）

- 新增 game/js/ui/ 下增量 UI 模块：hud.js（血蓝/技能CD/金币/小地图/队友血条/Boss条）、inventory_ui.js（品质色+对比箭头+一键分解白绿）、menu_ui.js（主菜单/暂停/结算/多人状态）、ui_state.js（只读状态适配与意图派发），全部为原生 ESM，不触碰基座 core.js/main.js/index.html。
- UI 层遵循 arch 契约：只读 gameplay 状态快照并派发意图事件，不修改契约、不写后端、不引入 React/引擎代码；对缺失字段做防御性默认值，避免集成断裂时崩溃。
- 新增 game/css/ui.css 增量样式，使用 ui-spec 的 Design Token（品质色白/绿/蓝/紫/橙、间距、字号、层级），不覆盖基座样式。
- 未运行基线命令，无 sha256 产物证据；game/js/core.js 实际 UI 钩子签名与 gameplay 模块导出未证实，已写入 open_questions。

## 写入文件

- `game/js/ui/hud.js` · 16efa89862d8 · role

## 未决问题

- game/js/core.js 与 main.js 暴露的 UI 挂载点（HUD 绘制入口、输入事件名、状态快照获取方式）未在可见产物中给出，需 S0 基线说明确认后对齐 ui_state.js 的适配层。
- gameplay 模块（player/combat/items/loot/inventory/save/coop）的实际导出签名未证实，UI 读取的状态字段名可能与实现不一致，需在集成时核对。
- 本地同屏 2 人 HUD 在 1280x720 与 1920x1080 下的最小安全边距需实机确认。
- 字体资源是否随模板提供未确认，当前样式以系统字体回退为主。
- 未运行 node --test game/tests/game_logic.test.mjs 与 node game/tests/smoke.mjs，基线通过性无运行证据。

## 门禁检查

- 全部通过
