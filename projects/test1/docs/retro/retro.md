# retro · 复盘与改进

> 运行器根据角色结构化输出生成；不是模型直接写入的文件，也不作为工具证据。

- 状态：done
- 摘要：作为 retro，基于前置 pm/product/ui/arch/backend/frontend/review/qa/security/ops/kb 产物做流程复盘，产出 docs/retro/retro.md。关键决策：(1) 时间线按 S0-S8 切片与角色顺序还原，标注每阶段门禁状态均为 pass；(2) 偏差识别三类——集成验证滞后（增量模块与基座接口未实证、frontend 未跑基线）、存档介质降级未验证、P1 局域网 UDP 在 Canvas 栈不可行被延后；(3) 根因归为“契约先行但集成门禁缺失”，非个人问题；(4) 行动项含 owner/deadline/verification：QA 补跑基线并新增集成 smoke 校验增量模块加载且基座哈希不变、arch 明确存档介质降级与 P1 联机降级、ops 在 build.sh 固化基座哈希基线、reviewer 在下一轮评审强制要求测试证据。可验证内容：所有行动项以 node --test game/tests/game_logic.test.mjs、node game/tests/smoke.mjs 通过及基座文件哈希不变为验收标准；多人缩放查表、掉落权重、房间不变量、SaveEnvelope 校验作为回归锚点。未编造证据，信息缺口写入 open_questions。

## Claims（不参与门禁）

- 本次流程整体门禁全绿，但存在三类系统性偏差：增量模块与基座接口未实证、存档介质降级未验证、局域网UDP在Canvas栈不可行被延后。
- 根因集中在“契约先行但集成验证滞后”：架构契约定义了不变量，但缺少在 smoke 中验证增量模块加载与基座不被覆盖的集成门禁。
- 行动项均绑定 owner/deadline/verification，验证标准以可运行测试与哈希基线为准，不以口头结论为准。

## 未决问题

- 基座 game/js/core.js 与 main.js 的实际导出 API 未在产物中给出，无法确认增量模块集成方式。
- 浏览器无 SQLite 时 SaveEnvelope 的存储介质（localStorage/IndexedDB）未定，双备份+CRC 落地方式待验证。
- 局域网 UDP 在 Canvas + 原生 ES Modules 栈不可行，P1 联机降级方案（如 WebRTC/占位）未定。
- frontend 交付未运行基线测试，需 QA 补跑结果作为证据。
- 各角色产物 sha256 未在本次复盘中实际计算，artifacts 中标注 pending，需由工具侧补齐。
