# ops · 发布与回滚

- 状态：done
- 摘要：作为 ops，基于已批准的产品基准、架构契约与 QA 计划，产出 docs/ops/release-plan.md（发布/回滚/监控/演练方案）、scripts/ops/start-local.sh（本地启动静态服务并打开 game/index.html）、scripts/ops/build.sh（构建产物打包+基座文件哈希基线校验+基线测试门禁）、scripts/ops/backup-save.sh（存档导出/双备份/CRC 校验占位）、scripts/ops/rollback.sh（按发布清单回滚到上一版本并保留现场）。关键决策：(1) 发布门禁硬检查为 node --test game/tests/game_logic.test.mjs 与 node game/tests/smoke.mjs 通过且基座文件哈希未变，任一失败即 BLOCKED；(2) 生产发布必须持有裁判凭证，脚本不绕过；(3) 存档备份采用导出+双份+CRC 校验，异常退出回最近篝火快照；(4) 回滚以版本清单为准，回滚后保留现场日志。所有脚本仅写 scripts/ 与 artifacts/ops/，不触碰 game/ 基座与业务代码。未实际运行脚本与基线测试，故不声明通过；信息缺口已写入 open_questions，未编造证据。

- 门禁：pass · G-TEST1-ops

## Claims（不参与门禁）

- 交付发布计划、本地启动/构建脚本、存档备份与回滚方案，覆盖单人离线+本地同屏MVP，局域网P1降级说明。
- 生产发布前置硬检查：node --test game/tests/game_logic.test.mjs 与 node game/tests/smoke.mjs 必须通过，且基座文件未被修改；未实际运行，故不声明通过。

## 写入文件

- `docs/ops/release-plan.md` · f4f7fc26fb01 · role
- `scripts/ops/start-local.sh` · 5a478286184c · role
- `scripts/ops/build.sh` · 87b95d8b27ac · role
- `scripts/ops/backup-save.sh` · dad95c648a1b · role
- `scripts/ops/rollback.sh` · b2a809fd2a21 · role

## 未决问题

- 基座 game/js/core.js 与 main.js 的模块加载/事件总线 API 细节未实证，脚本中的静态检查仅做文件存在与哈希比对，无法验证运行时集成。
- 浏览器存档介质（localStorage/IndexedDB）与 SaveEnvelope 双备份+CRC 的落地方式未验证，备份脚本按 localStorage 键名占位，需集成后确认键名。
- 局域网 UDP 在 Canvas 栈不可行，P1 联机发布流程未定义，需架构给出降级方案后再补发布步骤。
- CI/构建环境未提供，scripts/ 下脚本为本地可执行方案，未在真实环境运行，不声明通过。

## 门禁检查

- 全部通过
