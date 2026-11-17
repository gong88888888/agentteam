# kb · 知识沉淀

- 状态：done
- 摘要：以 kb 角色归档第一章需求与各角色决策，产出 knowledge/project-notes.md：含项目定位与硬约束、可复用设计资产（房间生成不变量、战斗/装备/存档/双人缩放数值口径、Design Token 与品质色）、关键决策记录、踩坑与失效条件、验收指标与复用指引。仅写 knowledge/ 前缀，未修改基准条款，未将候选知识提升为权威，未删除审计记录；信息缺口写入 open_questions，未编造证据。

- 门禁：pass · G-TEST1-kb

## Claims（不参与门禁）

- 本次沉淀将第一章需求与各角色决策整理为可复用知识条目，写入 knowledge/project-notes.md。
- 关键阻断为 frontend 产物路径违规、gameplay 模块落盘未证实、无基线运行证据；这些是知识条目的失效条件而非已修复事实。
- 知识条目只做归档与索引，不修改基准条款、不提升候选知识为权威知识、不删除审计记录。

## 写入文件

- `knowledge/project-notes.md` · 2e0c1eb559a6 · role

## 未决问题

- game/js/core.js 实际暴露的模块注册/更新/渲染接口签名未提供，无法核对 S0 接口清单。
- gameplay 模块是否已落盘到 game/js/gameplay/ 未证实。
- hud.js 是否已从 src/frontend/game/js/ui/ 迁移到 game/js/ui/ 未证实。
- 基线两条命令与 qa_*.mjs 的实际运行输出未提供，读档成功率>99.5%、崩溃率<0.5% 无法量化。
- 存档存储介质与双备份+CRC 的具体实现方案未定。
- 局域网联机（P1）范围与 Host 权威、加入码防爆破是否纳入 EA 前未最终确认。

## 门禁检查

- 全部通过
