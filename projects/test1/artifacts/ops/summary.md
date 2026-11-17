# ops · 发布与回滚

- 状态：done
- 摘要：以 ops 角色产出第一章 MVP 的发布与回滚方案，写入 docs/ops/release-plan.md 与 scripts/ 下的启动/构建/备份/回滚脚本骨架。关键决策：(1) 技术栈为 HTML5 Canvas + 原生 ESM，无打包步骤，构建=静态目录快照+版本号+sha256 清单；(2) 发布硬检查为基线两条命令通过 + game/index.html 可加载 + 产物路径合规（game/js/gameplay|ui 下），任一失败置 BLOCKED 并保留现场；(3) 回滚采用上一版本静态目录快照切换，玩家存档独立于代码目录，回滚不触碰存档，存档侧用双备份+CRC+异常回退篝火；(4) 发布前必须持有裁判凭证与硬检查通过，无凭证不发布生产。已知阻断：frontend 产物路径违规、gameplay 落盘未证实、无基线运行输出，故本次不签发发布凭证，artifacts 为空，缺口写入 open_questions，未编造证据。

- 门禁：pass · G-TEST1-ops

## Claims（不参与门禁）

- 产出 docs/ops/release-plan.md：定义本地启动、构建（无打包，静态 ESM 直出）、存档备份与回滚方案，覆盖单人离线第一章 MVP 的发布前硬检查清单。
- 发布门禁硬检查：基线两条命令（node --test game/tests/game_logic.test.mjs、node game/tests/smoke.mjs）必须通过，且 game/index.html 可被静态服务器加载；任一失败即 BLOCKED，不发布。
- 回滚方案为版本化静态目录快照 + 存档双备份（localStorage/IndexedDB 导出 JSON + CRC 校验），回滚不触碰玩家存档，异常退出回最近篝火。
- 已知阻断：frontend 产物路径违规（src/frontend/game/js/ui/hud.js 不在 game/js/ui/）、gameplay 模块落盘未证实、无基线运行输出，故本次不签发发布凭证，artifacts 为空。

## 写入文件

- `docs/ops/release-plan.md` · 48020f3e12b4 · role
- `scripts/ops/build_snapshot.sh` · 397fafe01c0d · role
- `scripts/ops/backup_save.sh` · c8ab57e9ad71 · role
- `scripts/ops/rollback.sh` · 246d540029f5 · role

## 未决问题

- game/js/core.js 与 main.js 的模块注册/更新/渲染接口签名未提供，无法确认 game/index.html 的 ESM 加载链是否完整。
- gameplay 模块（combat/classes/player/enemies/items/loot/inventory/save/coop）是否已实际落盘到 game/js/gameplay/ 未证实，构建前需核实。
- hud.js 是否已从 src/frontend/game/js/ui/ 迁移到 game/js/ui/ 未证实，未迁移则 ESM 加载失败，发布硬检查不通过。
- 存档持久化介质（localStorage vs IndexedDB）与双备份+CRC 具体实现未定，备份/回滚脚本需据此对齐。
- 基线两条命令与 qa_*.mjs 的实际运行输出未提供，读档成功率>99.5%、崩溃率<0.5% 无法量化验证。
- 本地静态服务器端口与启动方式（如 python -m http.server 或 node 静态服务）未在模板中确认，需 S0 校验后回填。
- 局域网联机（P1）不在本次发布范围，其 Host 权威与加入码防爆破是否纳入 EA 前未最终确认。

## 门禁检查

- 全部通过
