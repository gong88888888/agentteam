# frontend · 前端实现

- 状态：done
- 摘要：作为 frontend 角色，基于已批准的 ui-spec 与架构契约，在授权路径内交付游戏 UI 增量模块：HUD（血蓝/技能CD/金币/小地图/队友血条）、背包（品质色/对比箭头/一键分解白绿）、地图（已探索/Boss/篝火图标）、商店、篝火、结算、多人面板（本地同屏加入/局域网房间码占位）、设置（关闭震屏/减少粒子）与 10 分钟新手引导步骤条。实现方式为原生 ES Modules + Canvas/DOM 混合渲染，仅通过事件总线与只读状态快照与 gameplay 交互，不覆盖基座文件、不写 React/后端。样式集中在 game/css/ 使用 ui-spec Design Token（16px 网格、2x 整数缩放、品质五色、受击闪白、动效时长与缓动）。所有面板对缺失字段做默认值兜底，异常状态有可见反馈。未运行 node 基线测试，故不声明通过；集成所需接口细节已写入 open_questions，未编造证据。

- 门禁：pass · G-TEST1-frontend

## Claims（不参与门禁）

- 在 game/js/ui/ 下交付了 HUD、背包、地图、商店、篝火、结算、多人面板、设置与新手引导的增量 UI 模块，全部为原生 ES Modules，仅通过事件总线与只读状态快照交互，不触碰基座文件。
- 在 game/css/ 下交付了基于 ui-spec Design Token 的像素卡通样式（16px 网格、2x 整数缩放、品质五色、受击闪白、低配降级开关）。
- UI 模块对缺失字段做防御性默认值，不修改契约与后端数据结构；未运行 node 测试，故未声明基线通过。

## 写入文件

- `game/js/ui/ui-tokens.js` · 06cb5e734915 · role
- `game/js/ui/ui-bus.js` · 04037615a376 · role
- `game/js/ui/ui-dom.js` · c31e493384b3 · role
- `game/js/ui/hud.js` · 0a5fd1380a21 · role
- `game/js/ui/inventory.js` · 2e33e08ac99d · role
- `game/js/ui/map-panel.js` · 44b5b41f024c · role
- `game/js/ui/shop.js` · d7c8e978179a · role
- `game/js/ui/campfire.js` · 336907869219 · role
- `game/js/ui/results.js` · 621355bb0979 · role
- `game/js/ui/multiplayer.js` · 7d30796c1790 · role
- `game/js/ui/settings.js` · c9496878893d · role
- `game/js/ui/tutorial.js` · 9312d44fa6de · role
- `game/js/ui/index.js` · cca0b91fbb70 · role
- `game/css/ui.css` · 87bdbb80744b · role

## 未决问题

- 基座 game/js/core.js 的事件总线 API 名称与状态快照结构未在可见范围内确认，UI 模块采用约定式接口（on/emit、getSnapshot），需集成层对齐。
- game/index.html 的挂载点与样式引入方式未确认，UI 模块以导出 init(rootEl, bus) 形式提供，需集成层调用。
- 本地同屏手柄加入与局域网房间码面板依赖 P1 联机契约，当前仅实现 UI 骨架与占位状态。

## 门禁检查

- 全部通过
