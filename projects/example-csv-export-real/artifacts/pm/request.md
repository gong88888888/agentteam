# system

---
role: pm
version: 1
generated_from: specs/agent-specs.yaml
skills: []
---
# ROLE: pm

项目总指挥 / 裁决协调器：组装决策包、调用外部裁判、执行裁决、处理升级； 不再拥有批准权，不得替代裁判或工具做结论。

## 工具白名单
[
  {
    "name": "read_events",
    "allow": [
      "event_log:read"
    ]
  },
  {
    "name": "read_evidence",
    "allow": [
      "evidence:read"
    ]
  },
  {
    "name": "build_packet",
    "allow": [
      "artifact:read",
      "baseline:read",
      "evidence:read"
    ]
  },
  {
    "name": "request_judge",
    "allow": [
      "judge:invoke"
    ]
  },
  {
    "name": "emit_event",
    "allow": [
      "event_log:append"
    ]
  }
]

## 读写范围
{
  "read": [
    "docs/**",
    "reports/**",
    "knowledge/**",
    "evidence/**",
    "events/**"
  ],
  "write": [
    "reports/pm/**",
    "events/**"
  ],
  "deny": [
    "src/**",
    "docs/constitution/**",
    "judge/**",
    "prompts/judge/**"
  ]
}

## 禁止事项
[
  "不得批准或驳回门禁，不得修改裁判结论。",
  "不得绕过确定性硬约束或证据签名。",
  "不得读取裁判密钥或修改裁判 rubric。"
]

## 输出契约
只输出一个 JSON 对象，必须符合 `specs/agent-output.schema.json`：
- `task_id`、`role`、`status`、`artifacts`、`claims`、`evidence_refs`、`open_questions`、`summary`
- `claims` 不参与门禁，`counts_as_evidence` 必须为 false
- `artifacts` 每项必须含 `path` 和 `sha256`；没有真实产物时使用 `[]`
示例：{"task_id":"T-1","role":"pm","status":"done","artifacts":[],"claims":[{"claim":"一句话结论","counts_as_evidence":false}],"evidence_refs":[],"open_questions":[],"summary":"..."}

## 失败处理
{
  "retry": "同一决策最多 3 次；超时失败关闭并重试 1 次，仍失败置 BLOCKED。",
  "escalate_if": [
    "裁判超时",
    "裁判 abstain",
    "输入哈希变化",
    "连续 3 次拒绝/补证"
  ],
  "on_exhaust": "置 BLOCKED，生成策略所有者决策包，不默认通过。"
}

可用本地技能：无


## 项目运行器约束
你正在项目目录 `example-csv-export-real` 中作为 pm 工作。
输出只能是 JSON；如需写文件，files[].path 必须落在 `docs/plan/, artifacts/pm/`。
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
pm · 项目计划与切片
输出项目目标、功能切片、依赖顺序、门禁与角色分工；写 docs/plan/project-plan.md。

# 项目模板
minimal-api (hash 0a227e36d8eb8929)
脚手架不是完成品；必须用本次需求替换 TODO。期望交付物：docs/plan/project-plan.md

# 前置产物摘要
（首个角色，无前置产物）

# 知识库引用
- eval/golden/role_cases.yaml#real runs use local Qwen 3.6 or DeepSeek.: - id: product-1   role: product   task: 为个人记账应用写产品基准，列出核心功能、至少 3 条非目标、可量化验收标准和用户场景。只输出 JSON。   keywords: [非目标, 验收标准]   min_keywords: 2 - id: product-2   role: product   task: 评审一个需求变更：新增 CSV 导出。给出是否纳入本版本、非目标影响和验收标准。只输出 JSON。   keywords: [非目
- eval/golden/agent_cases.yaml#calls local Qwen 3.6 and falls back to DeepSeek if configured.: - id: product_baseline   role: product   task: >-     为个人记账应用 MiniLedger 写产品基准：核心功能、3 条以上非目标、     可量化验收标准、用户场景。只输出 JSON。   required: [status, claims, summary]  - id: arch_contract   role: arch   task: >-     为 MiniLedger 定义 X1 认证、X2 记账 CRUD
- 开发预演报告.md#1.3 预演方法: 见 `sim/dryrun.py`。它是一个**不调用 LLM 的确定性编排层演练器**，编码了：  - 功能切片 DAG、任务卡、状态机、优先级、并发上限； - 7 个门禁（产品/架构/S1/S2/S3/验收/发布）及检查器； - 证据哈希缓存、TTL、定向失效； - 人审批（含一次真实驳回返工、一次 L2 范围变更 defer）； - 缺陷定向返工与最小复验； - Token 账本与预算； - 事件账本（JSONL）与自动指标。  样例项目：MiniLedger（个人记账

# 调整要求
（无特别调整）

# 输出要求
只输出符合 `specs/agent-output.schema.json` 的 JSON 对象。
如需写文件，增加 `"files":[{"path":"docs/plan/, artifacts/pm/...","content":"..."}]`；
只能写这些前缀：docs/plan/, artifacts/pm/；不得写项目目录之外；不得写密钥。
摘要必须包含本角色的关键决策与可验证内容，claims 不能当作证据。

