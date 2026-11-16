# pm · 项目计划与切片

- 状态：done
- 摘要：已生成《迷宫冒险家》项目计划文档 docs/plan/project-plan.md。核心决策：1. MVP范围锁定为第一章5层、3职业、单机+本地双人同步，排除远程联机；2. 单人模式为基准平衡，多人功能为非侵入式增强；3. 技术栈冲突（React vs Unity/Godot）列为最高风险，需在架构阶段解决；4. 存档系统需实现双备份+CRC校验及版本迁移机制。计划包含12周MVP开发路线、门禁标准及角色分工。

- 门禁：pass · G-TEST1-pm

## Claims（不参与门禁）

- 项目计划已基于产品基准与MVP范围生成，明确以单人离线完整体验为第一优先级。
- 技术栈冲突（React vs Unity/Godot）已被识别为关键风险，计划在架构阶段解决。
- MVP范围锁定为第一章5层、3职业、本地双人同步，排除远程联机以降低风险。

## 写入文件

- `docs/plan/project-plan.md` · a2d81a25e9ef · runner-summary

## 未决问题

- Q-004: Unity或Godot的具体版本选型需技术负责人确认，以决定构建工具链。
- Q-005: React前端代码在MVP中是否废弃？若保留，需明确与引擎的集成协议（如WebView或Native Plugin）。
- Q-006: 存档WAL实现由Backend还是Arch负责？需明确原子性写入的技术细节。

## 门禁检查

- 全部通过
