# specs：机器可校验的契约层

对应《修复建议1.md》P0-4 / P1-2。这里不是提示词文档，而是编排器与 Agent、裁判之间的硬接口。

## 文件

| 文件 | 用途 |
|---|---|
| `agent-spec.schema.json` | Agent 规格书的 9 字段约束（角色、工具、权限、输入输出、正反例、失败处理、预算、禁令） |
| `agent-specs.yaml` | 12 个 Agent 的规格书实例 |
| `task-card.schema.json` | 任务卡：依赖、条件依赖、预算、重试、锁、幂等、prompt 版本、回滚范围 |
| `evidence.schema.json` | 工具/裁判签名证据：`subject_hash` + `baseline_fp` + 签名者 |
| `decision-packet.schema.json` | 裁判唯一输入：确定性检查、缺失证据、claims、内容隔离 |
| `verdict.schema.json` | 六态裁决：approve / conditions / need_evidence / reject / defer / abstain |
| `agent-output.schema.json` | 创作型 Agent 的统一输出包；claims 明确 `counts_as_evidence=false` |
| `contracts/miniledger.openapi.yaml` | 契约优先示例：X1 认证、X2 记账、X3 报表 |
| `validate_specs.py` | 结构性校验脚本（不依赖第三方 jsonschema） |

## 和预演器的对应关系

`sim/dryrun.py` 当前用 Python dataclass 实现同一组约束：

| Schema | 预演器 |
|---|---|
| `task-card.schema.json` | `Task` |
| `evidence.schema.json` | `Evidence`；`signed_by` 只允许 `tool:` / `judge:` |
| `decision-packet.schema.json` | `build_packet()` |
| `verdict.schema.json` | `Decision` + `resolve_decisions()` |
| `agent-output.schema.json` | `produce()` 的产物与 `claims` |

真实实现应把预演器里的 dataclass 替换为这些 Schema 的运行时校验；**Schema 不通过不得进入下一环节**。

## 关键约束

1. Agent 只能写 `scope.write` 下的路径；越界写由 diff 工具签名为 `out_of_scope` 证据，门禁硬拦。
2. Agent 输出里的 `claims` 不参与门禁；门禁只查询 `evidence` 账本。
3. `approve` 必须引用至少一条工具签名证据；`need_evidence` 必须列出具体检查名/输入/命令。
4. 任务卡必须带 `budget`、`retry.max_attempts`、`idempotency_key`、`prompt_version`；缺项拒绝分发。
5. 条件依赖用 `deps_any`，避免「无故障路径死锁」。

## 校验

```bash
python -I specs/validate_specs.py
```
