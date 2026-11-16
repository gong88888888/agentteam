# retro · 复盘与改进

- 状态：done
- 摘要：本次复盘识别出三大关键风险：1. 技术栈冲突（React vs Unity/Godot）需立即决策；2. 存档原子性写入需跨平台验证；3. 多人数值缩放需固定系数表。行动项已分配至Arch/Backend/Product角色，deadline为2024-06-15。

- 门禁：pass · G-TEST1-retro

## Claims（不参与门禁）

- 技术栈冲突（React vs Unity/Godot）是MVP阶段最高风险，需立即决策集成方案或废弃React代码。
- 存档系统的WAL原子性写入在架构层已定义，但后端实现尚未验证跨平台一致性（Windows/Linux/macOS）。
- 多人动态难度缩放公式需固定系数表以避免数值爆炸，目前仅有线性描述，缺乏明确阈值。

## 写入文件

- `docs/retro/retro.md` · 0efe9f144bcb · runner-summary

## 未决问题

- Q-001: Unity/Godot引擎选型最终确认时间？决定React代码是否废弃及集成方式。Owner: Arch, Deadline: 2024-06-15
- Q-002: 存档WAL实现是否需支持Linux/macOS路径分隔符差异？需Backend确认跨平台一致性。Owner: Backend, Deadline: 2024-06-15
- Q-003: 多人掉落金币缩放公式是否采用固定系数表？需Product确认数值平衡以避免非线性爆炸。Owner: Product, Deadline: 2024-06-15

## 门禁检查

- 全部通过
