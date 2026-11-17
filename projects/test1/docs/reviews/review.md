# 代码评审报告（review）

> 本报告只输出 findings、证据引用与整改方向，不判定门禁通过。所有结论以工具与裁判判定为准。

## 1. 评审范围与方法

- 输入：需求文档（迷宫冒险家产品设计）、pm 项目计划、product 产品基准、ui 设计规范、arch 架构与 contracts/openapi.yaml、backend 玩法模块、frontend UI 模块。
- 方法：基于前置产物摘要做静态一致性评审；**未读取实际源码、未运行基线测试**，因此下列 findings 均为待验证项。
- 约束核对：交付形态为 game/index.html（Canvas + 原生 ES Modules），禁止 React/Python Web/Unity/Godot；代码只写 game/js/gameplay|ui 增量模块；QA 只新增 qa_*.mjs；基线 `node --test game/tests/game_logic.test.mjs` 与 `node game/tests/smoke.mjs` 必须通过。

## 2. Findings

### F1（高）增量模块与基座接口边界未实证
- 现象：arch 声明 gameplay/ui 仅通过事件总线与只读状态快照交互，但未提供 core.js/main.js 的实际导出清单；backend/frontend 均声明“不触碰基座文件”，但无证据表明其 import 路径与基座导出匹配。
- 风险：隐式耦合或循环依赖可能使 smoke 加载失败，破坏基线。
- 证据引用：arch 摘要“分层为 core 基座 / gameplay 增量模块 / ui 增量模块”；backend 摘要“不触碰基座文件”；frontend 摘要“未运行 node 基线测试”。
- 整改方向：由集成方在 smoke 中验证 index.html 能加载全部增量模块；QA 新增 qa_integration.mjs 断言模块导出形状与事件总线契约。

### F2（高）浏览器存档介质降级未验证
- 现象：arch 与 backend 均将“浏览器无 SQLite 的存档介质降级”列入 open_questions；SaveEnvelope 含版本号、CRC32、双备份与迁移链，但落地介质（localStorage/IndexedDB）未确认。
- 风险：读档成功率 >99.5% 的验收指标无法保证；异常退出回篝火快照可能失效。
- 证据引用：arch 摘要“浏览器无 SQLite 的存档介质降级”；backend 摘要“SaveEnvelope 含版本号、CRC32 校验、双备份与迁移链”。
- 整改方向：QA 新增 qa_save.mjs 覆盖 CRC 校验失败回退、双备份切换、版本迁移链、异常退出回篝火快照。

### F3（中）局域网 UDP 在 Canvas 栈不可行
- 现象：产品将局域网联机列 P1，arch 指出“局域网 UDP 在 Canvas 栈不可行”，但 P1 降级方案（WebRTC/WebSocket 或推迟）未明确。
- 风险：P1 范围承诺与可实现性不一致，影响 EA 排期。
- 证据引用：arch 摘要“局域网 UDP 在 Canvas 栈不可行”；product 摘要“局域网联机列 P1”。
- 整改方向：由 pm/arch 在 P1 计划中明确降级路径，MVP 不阻塞。

### F4（中）多人缩放与掉落分桶需回归覆盖
- 现象：backend 声明严格按产品表查表（2/3/4 人血量 1.6/2.1/2.6、伤害 1.15/1.25/1.35、金币 1.25/1.45/1.65，Boss +10%），掉落按玩家 id 哈希分桶、金币材料共享；但无测试证据。
- 风险：数值漂移或分桶错误导致“防抢”失效。
- 证据引用：backend 摘要“多人缩放严格按产品表查表”“装备独立分桶按玩家 id 哈希”。
- 整改方向：QA 新增 qa_combat_scaling.mjs 与 qa_loot.mjs 做表驱动断言与分桶确定性断言。

### F5（中）房间生成不变量需失败路径测试
- 现象：backend 声明生成失败抛错而非静默，不变量含主路径连通、每层恰 1 篝火 1 商店、钥匙门≤1 且钥匙可达、种子+已探索可恢复。
- 风险：边界种子下可能死循环或静默降级。
- 证据引用：backend 摘要“生成失败抛错而非静默”。
- 整改方向：QA 新增 qa_roomgen.mjs 用固定种子集与随机种子批量断言不变量，并覆盖失败抛错路径。

### F6（低）frontend 未运行基线测试即交付
- 现象：frontend 摘要明确“未运行 node 基线测试，故不声明通过”。
- 风险：UI 模块可能引入对基座文件的隐式依赖。
- 证据引用：frontend 摘要“未运行 node 基线测试”。
- 整改方向：QA 补跑基线并新增 qa_ui_contract.mjs 断言 UI 仅消费只读快照。

### F7（低）文档一致性
- 现象：pm/product/arch 对 MVP 范围表述一致（第一章5层、3职业、20怪、1Boss、50装备、单人+本地双人），未见冲突。
- 结论：无整改项，仅记录。

## 3. 证据引用说明

本报告未读取源码、未运行测试，evidence_refs 为空；上述 findings 均引用前置产物摘要文本，属待验证项，不作为已签名证据。

## 4. 整改优先级

1. F1、F2（高）：集成与存档，直接影响基线通过率与读档成功率指标。
2. F4、F5（中）：战斗缩放、掉落分桶、房间生成不变量，直接影响核心玩法正确性。
3. F3（中）：P1 联机降级，不阻塞 MVP。
4. F6、F7（低）：补跑基线与文档记录。

## 5. 声明

本评审不签发门禁结论；最终以 `node --test game/tests/game_logic.test.mjs`、`node game/tests/smoke.mjs` 与裁判判定为准。
