# backend · 后端实现

- 状态：done
- 摘要：代码文件已生成：src/backend/models.py

- 门禁：fail · G-TEST1-backend · 决策 DEC-TEST1-BACKEND

## Claims（不参与门禁）

- 定义了符合MVP范围的装备、角色、房间数据结构，支持品质权重与词条随机化。
- 实现了基于SQLite的轻量级持久层接口，包含双备份机制与CRC校验逻辑。
- 设计了本地同屏（Local Co-op）的状态同步数据结构，支持动态镜头缩放参数计算。
- 完成了核心业务逻辑：掉落概率计算、强化保底算法、背包一键分解逻辑。

## 写入文件

- `src/backend/models.py` · e1b7d222eb9b · role

## 未决问题

- 需要确认具体词条数值表（Affix Table）的配置格式，以便在 `_generate_affixes` 中精确映射。

## 门禁检查

- ❌ evidence:compile：fail
