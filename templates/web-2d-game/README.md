# 迷宫冒险家 · MVP 垂直切片

这是《迷宫冒险家》产品设计文档对应的**可运行游戏切片**，不是零散代码片段。

## 运行

```bash
cd game
python -m http.server 8787
# 浏览器打开 http://localhost:8787/
```

Windows 也可以直接双击项目根目录的 `play_game.bat`。

## 已实现（对应设计文档）

- 2D 横版房间制迷宫：4 个房间（战斗/跳台/精英/Boss）。
- 3 职业：剑士、法师、游侠，属性与射程不同。
- 本地双人：P1 WASD + J，P2 方向键 + K。
- 战斗：移动、跳跃、攻击、敌人追击、接触伤害、Boss。
- 掉落：白/绿/蓝/紫/橙 5 品质，加权掉落，金币与装备日志。
- HUD：血条、金币、房间、目标、队友血条、掉落记录。
- 存档：F5 保存、F9 读取，CRC 校验；数据在 localStorage。
- 逻辑测试：`node --test game/tests/game_logic.test.mjs`
- 冒烟：`node game/tests/smoke.mjs`
- 验证：`python -m orchestrator.game_check` 对项目做入口/逻辑/冒烟/渲染验收。

## 与最终产品的差距

- 当前是 HTML5 Canvas 验证切片；正式版按设计文档迁移 Unity/Godot，补美术、音频、5 层章节、局域网联机、完整背包/强化/任务。
- 当前双人为同屏共享镜头；局域网 Host-Client 与远程同乐未实现。
