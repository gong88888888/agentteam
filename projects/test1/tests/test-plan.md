# qa · 测试计划与用例

> 运行器根据角色结构化输出生成；不是模型直接写入的文件，也不作为工具证据。

- 状态：done
- 摘要：作为 QA，产出 docs/qa/test-plan.md 测试计划与四组可运行逻辑测试（qa_combat_scaling / qa_loot_bucket / qa_room_invariants / qa_save_envelope），覆盖架构契约中的战斗固定步长与多人缩放查表（2/3/4人血量1.6/2.1/2.6、伤害1.15/1.25/1.35、金币1.25/1.45/1.65、Boss+10%）、掉落品质权重与Boss保底及按玩家id哈希独立分桶、房间生成不变量（主路径连通、每层1篝火1商店、钥匙门≤1且钥匙可达、种子+已探索可恢复）、存档SaveEnvelope版本号+CRC32+双备份+迁移链+异常退出回篝火。测试采用 node:test，对未就绪模块显式 skip 不伪造通过；不修改基座 game_logic.test.mjs 与 smoke.mjs。验收用例矩阵含新手10分钟首蓝装、30分钟首Boss、单局15-30分钟、读档成功率>99.5%等指标的可测化拆解。信息缺口（模块导出路径、事件总线API、存档介质、P1联机降级）已写入 open_questions，未编造证据。

## Claims（不参与门禁）

- 已基于产品基准与架构契约设计测试计划，覆盖战斗缩放查表、掉落分桶、房间生成不变量、存档 CRC/迁移/异常退出回篝火四类核心不变量，并补充冒烟与验收用例矩阵。
- 新增 qa_*.mjs 测试文件，不修改基座 game_logic.test.mjs 与 smoke.mjs；测试对缺失模块做显式 skip 而非伪造通过。

## 未决问题

- game/js/gameplay/ 下 backend 模块的实际导出名与文件路径未在摘要中给出，qa_*.mjs 采用动态 import 探测，若路径不符将 skip 并需集成方确认。
- 基座 core.js/main.js 的事件总线 API 未实证，冒烟用例仅能验证 index.html 可加载，无法断言增量模块挂载成功。
- 浏览器存档介质降级（localStorage vs 内存）未定，SaveEnvelope 双备份+CRC 的持久化断言需介质确认后补。
- 局域网 UDP 在 Canvas 栈不可行，P1 联机验收用例暂标记为 out-of-scope，待架构降级方案。
