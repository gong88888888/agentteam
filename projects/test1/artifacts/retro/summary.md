# retro · 复盘与改进

- 状态：done
- 摘要：以 retro 角色对第一章前置产物做复盘，产出 docs/retro/retro.md（时间线、偏差、根因、行动项含 owner/deadline/verification）。关键决策：(1) 将 frontend 产物路径违规定为最高优先级系统性根因，因其同时触发 ESM 加载失败与契约不一致；(2) 将无 sha256、无基线运行输出定为证据链缺口，坚持不把任何 Agent 自述计为证据；(3) 根因归纳为交付路径校验缺失、证据链强制缺失、契约-实现对齐缺失三类，均给出可验证行动项与验证标准；(4) 不追责个人、不修改基准与职责，仅提流程/规则优化建议。信息缺口写入 open_questions，未编造证据。

- 门禁：pass · G-TEST1-retro

## Claims（不参与门禁）

- 第一章前置链路存在系统性交付路径违规：frontend 产物落在 src/frontend/game/js/ui/hud.js，违反代码只写 game/js/gameplay|ui 硬约束，且无法被 game/index.html 的 ESM 加载，是当前最高优先级根因。
- product、arch、frontend、ops 四个角色 gate=fail，说明范围/契约/落盘/发布门禁尚未收口；review 与 qa 已识别同一路径违规，属跨角色重复暴露的流程缺口而非单点失误。
- 全链路无任何产物 sha256 与基线两条命令的实际运行输出，导致基线仍通过无法被证实，所有 Agent 自述均不可计为证据。
- 根因归为三类：交付路径校验缺失、证据链缺失、契约与实现对齐缺失。

## 写入文件

- `docs/retro/retro.md` · 15dfac2dd5a4 · role

## 未决问题

- 基座 game/js/core.js 暴露的模块注册/更新/渲染接口具体签名未知，无法验证 ui 模块接入方式。
- gameplay 模块是否已实际落盘、导出签名是否与 contracts/openapi.yaml 一致，无产物可核。
- 基线 game_logic.test.mjs 与 smoke.mjs 最近一次运行结果与时间戳缺失。
- 存档双备份+CRC+版本迁移的实际实现与 qa_save.mjs 通过情况未证实。
- 本地同屏 2 人动态缩放与扶起 3 秒是否已在可运行版本中生效，无运行证据。

## 门禁检查

- 全部通过
