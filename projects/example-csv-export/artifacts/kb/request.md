# system

---
role: kb
version: 1
generated_from: specs/agent-specs.yaml
skills: []
---
# ROLE: kb

知识库运维：归档产出、索引证据、提炼可复用资产、维护版本与过期； 不修改资产业务内容，不覆盖权威基准。

## 工具白名单
[
  {
    "name": "read_artifacts",
    "allow": [
      "artifact:read",
      "evidence:read",
      "docs:read"
    ]
  },
  {
    "name": "index_knowledge",
    "allow": [
      "knowledge:write",
      "search:index"
    ]
  },
  {
    "name": "write_archive",
    "allow": [
      "knowledge/**",
      "reports/kb/**"
    ]
  }
]

## 读写范围
{
  "read": [
    "docs/**",
    "reports/**",
    "evidence/**",
    "knowledge/**"
  ],
  "write": [
    "knowledge/**",
    "reports/kb/**"
  ],
  "deny": [
    "src/**",
    "docs/constitution/**",
    "docs/product/**"
  ]
}

## 禁止事项
[
  "不得修改基准条款或业务资产内容。",
  "不得把候选知识提升为权威知识。",
  "不得删除审计记录。"
]

## 输出契约
只输出一个 JSON 对象，必须符合 `specs/agent-output.schema.json`：
- `task_id`、`role`、`status`、`artifacts`、`claims`、`evidence_refs`、`open_questions`、`summary`
- `claims` 不参与门禁，`counts_as_evidence` 必须为 false
- `artifacts` 每项必须含 `path` 和 `sha256`；没有真实产物时使用 `[]`
示例：{"task_id":"T-1","role":"kb","status":"done","artifacts":[],"claims":[{"claim":"一句话结论","counts_as_evidence":false}],"evidence_refs":[],"open_questions":[],"summary":"..."}

## 失败处理
{
  "retry": "索引失败最多 2 次；仍失败保留原始归档。",
  "escalate_if": [
    "基准冲突",
    "知识来源不可信",
    "过期资产影响活跃任务"
  ],
  "on_exhaust": "置 BLOCKED，不写权威层。"
}

可用本地技能：无


## 项目运行器约束
你正在项目目录 `example-csv-export` 中作为 kb 工作。
输出只能是 JSON；如需写文件，files[].path 必须落在 `knowledge/, artifacts/kb/`。
不得写项目目录之外，不得写密钥；不确定时写 open_questions，不要编造证据。


# user

# 项目需求
# 需求：月度记录 CSV 导出

- ID：REQ-CSV
- 项目：MiniLedger
- 评分：10.0/10（now）
- 目标用户：个人用户, 小型团队
- 标签：export, csv, reporting

## 目标

用户可以按月份把记账记录导出为 CSV，用于个人归档和二次分析。 导出内容包含日期、金额、分类、备注；只允许导出当前用户自己的记录。

## 非目标

- 不支持 Excel 公式、图表或多 sheet。
- 不做定时/邮件自动导出。
- 不引入新的导出服务或消息队列。

## 验收标准

- 导出文件包含所选月份全部记录，字段为 date, amount, category, note。
- 导出接口必须校验 owner，不能导出其他用户记录。
- 单次导出 1 万行时 P95 < 2s；超过 10 万行返回明确错误。
- 空数据月份导出合法空 CSV，不报错。

## 约束

- 复用现有认证与记录查询接口。
- 导出文件使用 UTF-8 + BOM，兼容 Excel。
- 不改变现有记录数据结构。



# 当前角色
kb · 知识沉淀
把本次需求的可复用资产、决策、踩坑与失效条件写成知识条目；写 knowledge/project-notes.md。

# 项目模板
minimal-api (hash 0a227e36d8eb8929)
脚手架不是完成品；必须用本次需求替换 TODO。期望交付物：knowledge/project-notes.md

# 前置产物摘要
- pm: # pm · 项目计划与切片

- 状态：done
- 摘要：stub pm: 决策包 选项 证据 风险 升级 裁决协调 切片 依赖 门禁

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-pm

## Claims（不参与门禁）

- stub pm: 决策包 选项 证据 风险 升级 裁决协调 切片 依赖 门禁

## 写入文件

- `docs/plan/project-plan.md` · f300ac815727 · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- product: # product · 产品基准

- 状态：done
- 摘要：stub product: 非目标 验收标准 用户场景 范围

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-product

## Claims（不参与门禁）

- stub product: 非目标 验收标准 用户场景 范围

## 写入文件

- `docs/product/product-baseline.md` · 5124562668b7 · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- ui: # ui · UI/UX 设计规范

- 状态：done
- 摘要：stub ui: 信息架构 交互状态 深色模式 可访问性 设计规范

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-ui

## Claims（不参与门禁）

- stub ui: 信息架构 交互状态 深色模式 可访问性 设计规范

## 写入文件

- `docs/design/ui-spec.md` · bcf6faf8334a · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- arch: # arch · 架构与契约

- 状态：done
- 摘要：stub arch: 接口契约 不变量 状态机 错误码 架构

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-arch

## Claims（不参与门禁）

- stub arch: 接口契约 不变量 状态机 错误码 架构

## 写入文件

- `docs/architecture/architecture.md` · ef8275d5bae4 · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- backend: # backend · 后端实现

- 状态：done
- 摘要：stub backend: 参数校验 状态机 日志 错误码 单元测试 接口

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-backend

## Claims（不参与门禁）

- stub backend: 参数校验 状态机 日志 错误码 单元测试 接口

## 写入文件

- `src/backend/service.py` · 5ba5df067fbc · role

## 未决问题

- 无

## 门禁检查

- 全部通过

- frontend: # frontend · 前端实现

- 状态：done
- 摘要：stub frontend: 加载 错误 空状态 可访问性 深色模式 组件

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-frontend

## Claims（不参与门禁）

- stub frontend: 加载 错误 空状态 可访问性 深色模式 组件

## 写入文件

- `src/frontend/app.js` · 7996d33b4576 · role

## 未决问题

- 无

## 门禁检查

- 全部通过

- review: # review · 代码评审

- 状态：done
- 摘要：stub review: 评审 证据引用 整改方向 契约漂移 findings

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-review

## Claims（不参与门禁）

- stub review: 评审 证据引用 整改方向 契约漂移 findings

## 写入文件

- `docs/reviews/review.md` · 2fde581a7d3d · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- qa: # qa · 测试计划与用例

- 状态：done
- 摘要：stub qa: 正常 异常 边界 权限 回归 证据 用例

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-qa

## Claims（不参与门禁）

- stub qa: 正常 异常 边界 权限 回归 证据 用例

## 写入文件

- `tests/test-plan.md` · 4e419d915b1c · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- security: # security · 安全与合规

- 状态：done
- 摘要：stub security: 威胁 缓解 高危 权限 依赖 合规

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-security

## Claims（不参与门禁）

- stub security: 威胁 缓解 高危 权限 依赖 合规

## 写入文件

- `docs/security/threat-model.md` · e90bf048a2b5 · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- ops: # ops · 发布与回滚

- 状态：done
- 摘要：stub ops: 回滚 演练 监控 灰度 发布 告警

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-ops

## Claims（不参与门禁）

- stub ops: 回滚 演练 监控 灰度 发布 告警

## 写入文件

- `docs/ops/release-plan.md` · 10e88ffdaaeb · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过

- retro: # retro · 复盘与改进

- 状态：done
- 摘要：stub retro: 时间线 根因 行动项 owner deadline verification 验证 残余风险

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-retro

## Claims（不参与门禁）

- stub retro: 时间线 根因 行动项 owner deadline verification 验证 残余风险

## 写入文件

- `docs/retro/retro.md` · 4c8cc23e2754 · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过


# 知识库引用
（未启用或无命中）

# 调整要求
（无特别调整）

# 输出要求
只输出符合 `specs/agent-output.schema.json` 的 JSON 对象。
如需写文件，增加 `"files":[{"path":"knowledge/, artifacts/kb/...","content":"..."}]`；
只能写这些前缀：knowledge/, artifacts/kb/；不得写项目目录之外；不得写密钥。
摘要必须包含本角色的关键决策与可验证内容，claims 不能当作证据。

