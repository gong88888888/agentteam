# 迷宫冒险家 · 存档备份与恢复（ops）

> 上游：`docs/architecture/architecture.md`（SaveEnvelope 双备份+CRC+版本迁移）、`docs/security/threat-model.md`。

## 0. 存档结构（按 arch 契约）

```
SaveEnvelope {
  version: integer >= 1,
  crc32:   integer,
  payload: object
}
```

- 双槽轮换：主槽 + 备份槽，写入时先写备份槽再写主槽，读档时主槽 CRC 失败回退备份槽。
- 版本迁移：`version` 低于当前版本时按迁移链升级，迁移失败回最近篝火。
- CRC32 仅防意外损坏，不防恶意篡改（见威胁模型残余风险）。

## 1. 备份策略

| 时机 | 动作 |
|---|---|
| 发布前 | 全量备份存档目录到 `artifacts/ops/backup/<timestamp>/` |
| 回滚前 | 全量备份当前存档目录 |
| 存档恢复前 | 再次备份当前存档目录 |
| 日常 | 由游戏内自动存档负责，ops 不介入 |

## 2. 备份脚本

```bash
# 备份
node scripts/ops/backup-save.mjs --out artifacts/ops/backup

# 列出备份
node scripts/ops/backup-save.mjs --list

# 校验备份 CRC
node scripts/ops/verify-save.mjs --dir artifacts/ops/backup/<timestamp>
```

## 3. 恢复脚本

```bash
node scripts/ops/restore-save.mjs --from artifacts/ops/backup/<timestamp>
```

恢复规则：
1. 校验备份目录内每个 SaveEnvelope 的 CRC32。
2. 校验通过才替换；任一失败则中止并保留现场。
3. 替换前备份当前存档目录。
4. 恢复后提示玩家读档失败回最近篝火。

## 4. 目录布局（待 arch 确认）

备份脚本按以下两类目录处理，具体路径以基座 adapter 为准：

- `world/`：主机世界档（世界进度 + 主机角色）。
- `profile/`：角色档（客机角色背包/等级/装备）。

## 5. 信息缺口

存档目录具体路径未在 arch 中明确，脚本以 `--save-root` 参数注入，默认读取环境变量 `MAZE_SAVE_ROOT`，未设置时报错退出，不猜测路径。
