# 迷宫冒险家 · 回滚手册（ops）

> 上游：`docs/ops/release-plan.md`。回滚目标：秒级恢复上一可用版本，且不覆盖玩家存档。

## 0. 回滚原则

1. **先止血再定位**：发现异常先回滚，再排查。
2. **不覆盖存档**：回滚只切换程序版本，不动存档目录。
3. **保留现场**：回滚前复制当前版本目录与日志到 `artifacts/ops/incident/<timestamp>/`。
4. **同类失败不重复重试**：同一回滚失败两次即升级。

## 1. 触发条件

- 启动白屏或控制台致命错误。
- 崩溃率 > 0.5%。
- 读档成功率 < 99.5% 或丢档。
- 存档 CRC 校验失败且备份不可用。
- 发布后门禁复跑失败。

## 2. 回滚步骤

```bash
# R1 保留现场
node scripts/ops/snapshot-incident.mjs --out artifacts/ops/incident

# R2 切换指针到上一版本
node scripts/ops/rollback.mjs --to <上一版本目录>

# R3 校验回滚后版本
node scripts/ops/verify-build.mjs --root current

# R4 冒烟：打开 current/index.html，确认主菜单可进入

# R5 记录回滚日志到 artifacts/ops/release/<version>.log
```

## 3. 存档恢复（仅在存档损坏时）

```bash
# 列出备份
node scripts/ops/backup-save.mjs --list

# 从指定备份恢复（先复制到临时目录校验 CRC，再替换）
node scripts/ops/restore-save.mjs --from artifacts/ops/backup/<timestamp>
```

恢复规则：
- 优先使用最近一次 CRC 校验通过的备份。
- 恢复前再次备份当前存档目录。
- 恢复后读档失败仍回最近篝火，不丢档。

## 4. 回滚演练

每次发布前执行一次演练，验证回滚可用：

```bash
node scripts/ops/rollback-rehearsal.mjs
```

演练内容：在临时目录模拟 `releases/vA` → `releases/vB` 发布，再回滚到 `vA`，断言 `current` 指针正确、入口文件存在、存档目录未被修改。演练不触碰真实 `releases/` 与存档目录。

## 5. 升级条件

- 回滚后仍启动失败。
- 存档备份不可用。
- 回滚脚本自身报错且无法人工切换指针。

升级动作：置 **BLOCKED**，保留现场，通知 arch 与代码角色。
