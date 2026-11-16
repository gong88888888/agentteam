# example-csv-export-real

- 状态：**completed**
- 需求：`requirements/input.md`
- 模板：`minimal-api` · 工具证据 profile：`basic`
- 角色记录：`artifacts/<role>/{output.json,summary.md,meta.json,prompt.md,request.md}`
- 工具证据账本：`evidence/tool-ledger.jsonl`
- 质量历史：`quality/history.jsonl`
- 事件账本：`logs/events.jsonl`
- 状态：`state/roles.json`

## 角色执行记录

| 角色 | 标题 | 状态 | 门禁 | 质量 | 模型 | Prompt | 文件 |
|---|---|---|---|---|---|---|---|
| pm | 项目计划与切片 | done | pass | 100 | qwen3.6:35b-a3b-mtp-q4_K_M | 1 / 11bdc73b9f9e300c | docs/plan/project-plan.md |
| product | 产品基准 | done | pass | 94 | qwen3.6:35b-a3b-mtp-q4_K_M | 1 / 3e6de06e4795901a | docs/product/product-baseline.md |
| arch | 架构与契约 | done | pass | 94 | qwen3.6:35b-a3b-mtp-q4_K_M | 1 / fb5584fc4cae3222 | docs/architecture/architecture.md |
| backend | 后端实现 | done | pass | 99 | qwen3.6:35b-a3b-mtp-q4_K_M | 1 / c57160acc7ae1330 | src/backend/ledger/export.py |
| frontend | 前端实现 | done | pass | 99 | qwen3.6:35b-a3b-mtp-q4_K_M | 1 / e03e38f7405c7201 | src/frontend/hooks/useExport.ts |

> 这是角色产出记录，不是生产验收；代码/文档仍需门禁、证据与裁判。
