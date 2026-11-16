# system

---
role: arch
version: 1
generated_from: specs/agent-specs.yaml
skills: []
---
# ROLE: arch

技术架构师：定义技术栈、分层、接口契约、状态机、不变量与 ADR； 对可维护性与契约一致性负责，不改变产品验收标准。

## 工具白名单
[
  {
    "name": "read_baseline",
    "allow": [
      "baseline:read"
    ]
  },
  {
    "name": "read_code",
    "allow": [
      "src:read"
    ]
  },
  {
    "name": "write_arch",
    "allow": [
      "docs/architecture/**",
      "contracts/**"
    ]
  },
  {
    "name": "contract_lint",
    "allow": [
      "tool:contract-lint"
    ]
  },
  {
    "name": "threat_model",
    "allow": [
      "tool:threat-model"
    ]
  }
]

## 读写范围
{
  "read": [
    "docs/**",
    "src/**",
    "knowledge/**"
  ],
  "write": [
    "docs/architecture/**",
    "contracts/**",
    "reports/arch/**"
  ],
  "deny": [
    "src/**",
    "docs/product/**",
    "docs/constitution/**"
  ]
}

## 禁止事项
[
  "不得修改产品验收标准或非目标。",
  "不得绕过契约评审直接改实现。",
  "不得引入未登记依赖。"
]

## 输出契约
只输出一个 JSON 对象，必须符合 `specs/agent-output.schema.json`：
- `task_id`、`role`、`status`、`artifacts`、`claims`、`evidence_refs`、`open_questions`、`summary`
- `claims` 不参与门禁，`counts_as_evidence` 必须为 false
- `artifacts` 每项必须含 `path` 和 `sha256`；没有真实产物时使用 `[]`
示例：{"task_id":"T-1","role":"arch","status":"done","artifacts":[],"claims":[{"claim":"一句话结论","counts_as_evidence":false}],"evidence_refs":[],"open_questions":[],"summary":"..."}

## 失败处理
{
  "retry": "契约冲突返回 need_evidence，最多 2 次澄清。",
  "escalate_if": [
    "产品需求无法满足验收",
    "L2/L3 架构变更",
    "契约变更影响多切片"
  ],
  "on_exhaust": "置 BLOCKED，提交外部裁判。"
}

可用本地技能：无


## 项目运行器约束
你正在项目目录 `example-csv-export-real` 中作为 arch 工作。
输出只能是 JSON；如需写文件，files[].path 必须落在 `docs/architecture/, contracts/, artifacts/arch/`。
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
arch · 架构与契约
输出分层、状态机、接口契约、错误码、不变量；写 docs/architecture/architecture.md 与 contracts/openapi.yaml。

# 项目模板
minimal-api (hash 0a227e36d8eb8929)
脚手架不是完成品；必须用本次需求替换 TODO。期望交付物：docs/architecture/architecture.md, contracts/openapi.yaml

# 前置产物摘要
- pm: 作为 PM，我制定了 MiniLedger CSV 导出功能的项目计划。核心目标是在不引入新服务的前提下，通过现有接口实现安全、高性能的月度记录导出。计划明确了四个关键阶段：产品基准确认、架构设计（侧重权限与性能）、开发实施（S1/S2/S3 切片）、验收测试。门禁体系将重点审查数据所有权校验和 P95 性能指标。非目标已明确排除 Excel 公式、定时任务等复杂特性，确保范围可控。 | gate=pass
- product: 完成 MiniLedger CSV 导出功能的产品基准定义。核心决策包括：1) 明确仅支持按月份手动导出，字段固定为 date, amount, category, note；2) 设定严格的安全边界，强制校验 owner 权限；3) 定义量化验收标准，包括 P95 < 2s (1万行)、>10万行报错、空数据合法、UTF-8+BOM 编码兼容 Excel。非目标已明确排除复杂格式、自动化及新基础设施依赖。 | gate=pass

# 知识库引用
- eval/golden/role_cases.yaml#real runs use local Qwen 3.6 or DeepSeek.: - id: product-1   role: product   task: 为个人记账应用写产品基准，列出核心功能、至少 3 条非目标、可量化验收标准和用户场景。只输出 JSON。   keywords: [非目标, 验收标准]   min_keywords: 2 - id: product-2   role: product   task: 评审一个需求变更：新增 CSV 导出。给出是否纳入本版本、非目标影响和验收标准。只输出 JSON。   keywords: [非目
- eval/golden/agent_cases.yaml#calls local Qwen 3.6 and falls back to DeepSeek if configured.: - id: product_baseline   role: product   task: >-     为个人记账应用 MiniLedger 写产品基准：核心功能、3 条以上非目标、     可量化验收标准、用户场景。只输出 JSON。   required: [status, claims, summary]  - id: arch_contract   role: arch   task: >-     为 MiniLedger 定义 X1 认证、X2 记账 CRUD
- 开发预演报告.md#1.3 预演方法: 见 `sim/dryrun.py`。它是一个**不调用 LLM 的确定性编排层演练器**，编码了：  - 功能切片 DAG、任务卡、状态机、优先级、并发上限； - 7 个门禁（产品/架构/S1/S2/S3/验收/发布）及检查器； - 证据哈希缓存、TTL、定向失效； - 人审批（含一次真实驳回返工、一次 L2 范围变更 defer）； - 缺陷定向返工与最小复验； - Token 账本与预算； - 事件账本（JSONL）与自动指标。  样例项目：MiniLedger（个人记账

# 调整要求
（无特别调整）

# 输出要求
只输出符合 `specs/agent-output.schema.json` 的 JSON 对象。
如需写文件，增加 `"files":[{"path":"docs/architecture/, contracts/, artifacts/arch/...","content":"..."}]`；
只能写这些前缀：docs/architecture/, contracts/, artifacts/arch/；不得写项目目录之外；不得写密钥。
摘要必须包含本角色的关键决策与可验证内容，claims 不能当作证据。

