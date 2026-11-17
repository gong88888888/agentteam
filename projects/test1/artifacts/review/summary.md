# review · 代码评审

- 状态：done
- 摘要：以 review 角色对前置产物做静态评审：产品/计划/UI/架构/backend/frontend 六份产物在范围与契约上基本自洽，MVP 边界（第一章5层、3职业、20怪、1Boss、50装备、单人+本地双人）一致，多人缩放数值与产品表一致，掉落权重与 Boss 保底一致，房间生成不变量定义清晰。主要待验证风险：(1) 增量模块与基座 core/main 的接口边界未实证，存在隐式耦合破坏基线测试的风险；(2) 浏览器存档介质降级与 SaveEnvelope 双备份+CRC 的落地方式未验证；(3) 局域网 UDP 在 Canvas 栈不可行，P1 需明确降级；(4) frontend 未运行基线测试即交付，需 QA 补跑。整改方向：由 QA 新增 qa_*.mjs 覆盖战斗缩放查表、掉落分桶、房间生成不变量、存档 CRC/迁移与异常退出回篝火；由集成方在 smoke 中验证 game/index.html 可加载增量模块且不触碰基座文件。本评审不签发门禁结论，最终以工具与裁判判定为准。

- 门禁：pass · G-TEST1-review

## Claims（不参与门禁）

- 评审基于前置产物摘要与需求文档，未读取实际源码，因此所有 findings 均为待验证项，不构成门禁结论。
- 主要风险集中在：基座文件不可覆盖约束与 gameplay/ui 增量模块的集成边界、存档介质在浏览器环境的降级、局域网 UDP 在 Canvas 栈不可行、以及基线测试是否被增量模块破坏。

## 写入文件

- `docs/reviews/review.md` · 869ae4ea535a · role

## 未决问题

- 无法访问 game/js/core.js 与 game/js/main.js 的实际导出接口，无法确认 gameplay/ui 增量模块是否真的只通过事件总线与只读快照交互。
- 未运行 node --test game/tests/game_logic.test.mjs 与 node game/tests/smoke.mjs，无法确认基线是否仍通过。
- 浏览器无 SQLite，存档介质降级方案（localStorage/IndexedDB）是否已在 backend 模块中落地未验证。
- 局域网 UDP 在纯 Canvas/浏览器栈不可行，P1 联机方案是否已明确降级或推迟未确认。
- frontend 声明未运行基线测试，UI 模块是否引入对基座文件的隐式依赖未知。

## 门禁检查

- 全部通过
