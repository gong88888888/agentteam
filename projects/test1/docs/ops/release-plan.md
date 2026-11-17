# ops · 发布与回滚方案（第一章 MVP）

> 范围：单人离线第一章 MVP（1 章 5 层、3 职业、1 Boss、单机+本地同屏 2 人、存档/背包/强化/商店/篝火）。
> 技术栈：HTML5 Canvas + 原生 ES Modules，入口 `game/index.html`，无打包、无 Web 服务、无引擎工程。
> 本文件为发布流程与回滚预案，不含业务代码；所有命令需在项目根目录执行。

## 0. 发布原则（硬约束）

1. **无凭证不发布**：生产发布必须持有有效裁判凭证（gate=pass）且下列硬检查全部通过；缺一即 `BLOCKED`，保留现场不重试。
2. **无回滚方案不发布**：每次发布前必须确认上一版本快照可用、存档备份脚本可执行。
3. **不绕过硬检查**：不得手动跳过基线测试或路径合规检查。
4. **不手改线上配置不留痕**：任何配置变更须走版本快照并记录 sha256。
5. **单人基准**：发布验收以单人离线可完整通关第一章为第一优先级；本地双人为增强项，不得因双人问题阻塞单人发布（双人缺陷单独登记）。

## 1. 本地启动

### 1.1 前置
- Node.js ≥ 18（仅用于跑测试与静态服务，游戏本身为浏览器运行）。
- 现代浏览器（Chrome/Edge/Firefox 最新版）。

### 1.2 启动步骤
```bash
# 1) 基线测试（不可改基线，必须通过）
node --test game/tests/game_logic.test.mjs
node game/tests/smoke.mjs

# 2) 启动本地静态服务器（ESM 需 http 协议，不能 file:// 直开）
#    任选其一，端口固定 8080 便于复现
python -m http.server 8080 --directory .
# 或
npx --yes serve -l 8080 .

# 3) 浏览器访问
#    http://localhost:8080/game/index.html
```

### 1.3 启动自检（人工，逐项勾选）
- [ ] 页面无 404/ESM 加载错误（DevTools Console 无红色报错）。
- [ ] 主菜单可见：继续 / 新游戏 / 多人 / 设置 / 退出。
- [ ] 新游戏可选 3 职业与 3 档难度。
- [ ] 进入第一层房间，可移动/跳跃/普攻/闪避/技能/喝药。
- [ ] 击杀怪物有掉落光柱，可拾取并进背包。
- [ ] 篝火可回血、存档；回城可分解/强化。
- [ ] 关闭页面后重开，读档恢复到最近篝火/进房间点。

## 2. 构建（静态快照，无打包）

本项目无编译产物，构建 = 生成带版本号的静态目录快照 + sha256 清单，供发布与回滚使用。

```bash
# 版本号约定：v<章节>.<迭代>.<补丁>，例 v1.0.0
VERSION=v1.0.0
bash scripts/ops/build_snapshot.sh "$VERSION"
```

构建脚本行为（见 `scripts/ops/build_snapshot.sh`）：
1. 校验入口与关键目录存在：`game/index.html`、`game/js/core.js`、`game/js/main.js`、`game/js/gameplay/`、`game/js/ui/`。
2. **路径合规检查**：`game/js/` 下不得出现 `src/frontend/` 等越界产物；若发现 `src/frontend/game/js/ui/hud.js` 之类路径，直接失败退出（当前已知阻断）。
3. 复制 `game/` 到 `artifacts/ops/releases/<VERSION>/game/`。
4. 生成 `artifacts/ops/releases/<VERSION>/MANIFEST.sha256`（对快照内所有文件计算 sha256）。
5. 生成 `artifacts/ops/releases/<VERSION>/RELEASE.json`（版本号、构建时间、基线测试结果占位、git 提交号若有）。

> 注意：`artifacts/ops/` 为本地发布产物目录，不提交密钥、不含玩家存档。

## 3. 发布前硬检查清单（Gate Checklist）

发布前逐项执行并记录输出，任一失败 → `BLOCKED`：

| # | 检查项 | 命令/方式 | 通过标准 |
|---|---|---|---|
| H1 | 基座逻辑测试 | `node --test game/tests/game_logic.test.mjs` | 全部 pass，退出码 0 |
| H2 | 冒烟测试 | `node game/tests/smoke.mjs` | 退出码 0，无异常 |
| H3 | QA 增量测试 | `node --test game/tests/qa_*.mjs` | 全部 pass（若模块缺失导致 skip，需登记为已知缺口） |
| H4 | 入口可加载 | 静态服务器打开 `game/index.html` | Console 无 ESM 404/语法错误 |
| H5 | 产物路径合规 | 构建脚本路径检查 | 无 `src/frontend/**` 越界产物 |
| H6 | 存档备份可用 | `bash scripts/ops/backup_save.sh --dry-run` | 脚本可执行、输出备份路径 |
| H7 | 回滚快照存在 | 检查 `artifacts/ops/releases/<上一版本>/` | 目录与 MANIFEST 完整 |
| H8 | 裁判凭证 | 读取门禁结果 | gate=pass 且凭证有效 |

> 当前状态：H1/H2 无实际运行输出、H5 已知失败（frontend 产物路径违规）、gameplay 落盘未证实 → **不满足发布条件，置 BLOCKED**。

## 4. 存档备份方案

### 4.1 存档位置
- 浏览器本地存储（localStorage 或 IndexedDB，最终介质待 S4 确认）。
- 存档内容：角色属性、背包、装备、金币、任务、地图种子、已开房间、Boss 状态、设置、版本号、CRC。

### 4.2 备份策略（双备份 + CRC）
- 游戏内：每次进房间/回城/Boss 前/篝火自动写双备份（主档 + 备份档），写入前计算 CRC；读档时校验 CRC，损坏则回退备份档，仍失败则回最近篝火。
- 发布/回滚前：用 `scripts/ops/backup_save.sh` 将当前浏览器存档导出为 JSON 文件到 `artifacts/ops/save-backups/<时间戳>/`，便于回滚后恢复。

### 4.3 备份脚本（骨架）
见 `scripts/ops/backup_save.sh`：
- `--dry-run`：仅检查路径与权限，不写文件。
- 默认：提示用户在游戏内「设置 → 导出存档」得到 JSON，脚本校验 JSON 含 `version` 与 `crc` 字段后归档。
- 不读取、不打印任何密钥；存档文件仅本地留存。

## 5. 回滚方案

### 5.1 触发条件
- 发布后出现：入口无法加载、基线测试回归失败、存档读档失败率异常、崩溃。
- 同类失败不重复重试，直接回滚并升级。

### 5.2 回滚步骤
```bash
# 1) 确认当前版本与上一可用版本
ls artifacts/ops/releases/

# 2) 执行回滚（切换到上一版本快照）
bash scripts/ops/rollback.sh <上一版本号>

# 3) 校验回滚后入口可加载
#    静态服务器指向回滚后目录，打开 game/index.html 自检

# 4) 如需恢复存档，从 artifacts/ops/save-backups/ 选择最近备份，
#    在游戏内「设置 → 导入存档」恢复（CRC 校验通过才生效）
```

### 5.3 回滚不变量
- 回滚只切换代码快照，**不删除、不覆盖玩家存档**。
- 存档版本号高于当前代码版本时，按「只读提示」处理，不静默降级破坏存档。
- 回滚后必须重跑 H1/H2/H4 并记录输出。

### 5.4 回滚演练
- 每次发布前用 `scripts/ops/rollback.sh --rehearsal` 在本地对上一版本做一次演练，确认脚本可用；演练结果记入发布记录。

## 6. 监控与异常

- 离线单机无服务端监控；以本地日志与人工自检为主。
- 关键观测点：Console 报错、读档失败提示、崩溃（页面白屏/卡死）。
- 异常处理：先回滚，保留现场（快照 + 存档备份 + Console 日志截图），再升级。

## 7. 发布记录模板

每次发布在 `artifacts/ops/releases/<VERSION>/RELEASE.json` 记录：
```json
{
  "version": "v1.0.0",
  "built_at": "<ISO8601>",
  "gate_checks": {"H1": "pass", "H2": "pass", "H3": "skip", "H4": "pass", "H5": "fail", "H6": "pass", "H7": "pass", "H8": "pass"},
  "known_issues": ["frontend 产物路径违规待迁移", "gameplay 落盘待证实"],
  "rollback_target": "v0.9.0"
}
```

## 8. 已知阻断（发布前必须关闭）

1. `src/frontend/game/js/ui/hud.js` 未迁移到 `game/js/ui/`，ESM 无法加载 → H4/H5 失败。
2. gameplay 模块是否落盘到 `game/js/gameplay/` 未证实 → H3 可能全 skip。
3. 无基线两条命令的实际运行输出 → H1/H2 无法证实通过。
4. 存档介质与双备份+CRC 实现未定 → H6 仅能 dry-run。

以上关闭前，本方案不签发发布凭证。
