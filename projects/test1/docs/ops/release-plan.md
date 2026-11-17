# 迷宫冒险家 · 发布与回滚方案（ops）

> 角色：ops。范围：本地启动、构建、存档备份、回滚、监控与演练。
> 约束：交付物为可运行游戏，入口 `game/index.html`；技术栈 HTML5 Canvas + 原生 ES Modules；不覆盖基座文件。
> 本文件为方案与流程定义，未在真实环境运行脚本，不声明门禁通过。

## 1. 发布对象与形态

- 交付形态：静态站点目录（`game/`），入口 `game/index.html`，无后端、无强制联网。
- 运行方式：本地静态服务器（`python3 -m http.server` 或 `npx serve`）打开 `game/index.html`；ES Modules 需 HTTP 协议，禁止 `file://` 直接打开。
- 发布单元：`game/` 全量目录 + `docs/` 文档 + `scripts/` 运维脚本。

## 2. 环境与前置

| 项 | 要求 |
|---|---|
| Node | >= 18（运行基线测试） |
| 浏览器 | Chrome/Edge 最新版，支持 ES Modules |
| 静态服务 | 本地 8080 端口 |
| 裁判凭证 | 生产发布必须持有有效裁判凭证（judge 签发），缺失即 BLOCKED |

## 3. 发布门禁（硬检查，任一失败即 BLOCKED）

1. `node --test game/tests/game_logic.test.mjs` 通过。
2. `node game/tests/smoke.mjs` 通过。
3. 基座文件哈希与基线一致（`game/js/core.js`、`game/js/main.js`、`game/index.html`、`game/tests/game_logic.test.mjs`、`game/tests/smoke.mjs` 未被修改）。
4. 增量模块仅位于 `game/js/gameplay/`、`game/js/ui/`、`game/css/`、`game/tests/qa_*.mjs`。
5. 裁判凭证有效。

> 门禁由 `scripts/ops/build.sh` 执行 1-3 项；4-5 项由人工/裁判确认。脚本不绕过裁判凭证。

## 4. 本地启动流程

1. 执行 `scripts/ops/start-local.sh`（启动静态服务并打印入口 URL）。
2. 浏览器打开 `http://localhost:8080/game/index.html`。
3. 冒烟检查：主界面可加载、新游戏可进入、房间可切换、存档可写入。

## 5. 构建流程

1. 执行 `scripts/ops/build.sh`：
   - 校验基座文件哈希基线（`artifacts/ops/baseline.sha256`，首次运行生成）。
   - 运行基线测试（game_logic + smoke）。
   - 打包 `game/` 到 `artifacts/ops/build-<timestamp>/`，生成 `manifest.json`（文件列表+sha256）。
2. 构建失败：保留日志到 `artifacts/ops/logs/`，置 BLOCKED，不发布。

## 6. 存档备份方案

- 存档介质：浏览器 localStorage/IndexedDB（键名待集成确认，见 open_questions）。
- 备份策略：
  1. 导出当前存档 JSON（SaveEnvelope：版本号+CRC32+双备份）。
  2. 双份保存：`artifacts/ops/saves/<slot>-<timestamp>.json` 与 `.bak`。
  3. CRC 校验：导出后重算 CRC32 与存档内记录比对，不一致即告警。
- 异常退出：回最近篝火快照（由 gameplay 存档模块保证，ops 只做导出与校验）。
- 脚本：`scripts/ops/backup-save.sh`（占位实现，键名与导出方式待集成确认）。

## 7. 回滚方案

- 触发条件：发布后出现崩溃、读档失败、基线测试回归、监控越界。
- 回滚步骤：
  1. 执行 `scripts/ops/rollback.sh <target-version>`。
  2. 从 `artifacts/ops/build-<target>/` 恢复 `game/` 目录（按 manifest 校验 sha256）。
  3. 恢复后重跑基线测试，失败则保留现场并升级。
  4. 保留回滚现场日志到 `artifacts/ops/logs/rollback-<timestamp>.log`。
- 回滚不可用：置 BLOCKED，保留现场，升级。

## 8. 监控与演练

- 监控指标（本地/离线，人工观察）：启动成功率、读档成功率（目标 >99.5%）、崩溃率（目标 <0.5%）、房间加载 <2s、60 帧。
- 回滚演练：每次发布前在 `artifacts/ops/` 演练一次回滚（`scripts/ops/rollback.sh --dry-run`），记录耗时与结果。
- 演练失败：不发布，升级。

## 9. 失败处理

- 发布异常：先回滚，同类失败不重复重试。
- 升级条件：发布异常、回滚不可用、监控越界、凭证缺失。
- 耗尽：置 BLOCKED，保留现场。

## 10. 非目标

- 不引入后端服务、React、Unity/Godot。
- 不修改基座文件与业务代码。
- 不写密钥与凭据。
