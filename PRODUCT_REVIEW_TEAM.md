# Product Review & Upgrade Reference Team

面向**产品文档深析、应用流程细化、版本升级预演**的固定 AgentTeam。以后每次发版/升级，先用这个团队产出参考方案，再进入开发队伍。

## 什么时候使用

- 新产品文档评审；
- 版本升级（补丁/小版本/大版本）前的方案细化；
- 大改版、数据迁移、兼容性/回滚风险评审；
- 需要把产品文档转成可执行流程、验收、发布预演时。

**不用于**直接写产品代码；它输出的是参考方案和门禁结论。

## 团队角色

| 角色 | 职责 | 交付 |
|---|---|---|
| product-lead | 目标、范围、成功指标、非目标、决策问题 | `00-brief.md` |
| doc-analyst | 来源地图、主张、歧义、缺口、覆盖率 | `01-document-map.md` |
| user-researcher | 用户、场景、旅程、痛点、假设 | `02-users-journeys.md` |
| flow-architect | 状态机、事件、转移、失败恢复 | `03-product-flows.md` |
| feature-designer | 功能切片、依赖、非目标、验收 | `04-feature-spec.md` |
| ux-reviewer | 信息架构、状态、错误、可访问性 | `05-ux-review.md` |
| tech-feasibility | 技术栈、依赖、性能、安全、风险 | `06-tech-feasibility.md` |
| release-strategist | 版本、兼容、迁移、灰度、回滚 | `07-upgrade-plan.md` |
| qa-rehearsal | 补丁/小版本/大版本预演、Go/No-Go | `08-rehearsal.md` |
| red-team | 矛盾、遗漏、范围膨胀、升级破坏 | `09-red-team.md` |
| knowledge-curator | 下一次升级的复用清单/模板/门禁 | `10-playbook.md` |

最终由 runner 汇总成：

- `REFERENCE-PLAN.md`：下一次发版/升级的参考方案；
- `state/gates.json`：11 个角色门禁、来源覆盖率；
- `README.md`：角色/门禁表。

## 运行

```bash
# 真实模型：本地 Qwen 3.6，DeepSeek fallback
python start_product_review.py \
  --doc projects/test1/docs/product/product-baseline.md \
  --out reviews/test1-product \
  --real --kb

# 离线验证流程（stub）
python start_product_review.py \
  --doc <产品文档.md> --out reviews/<version> --offline
```

参数：

- `--doc`：产品文档，当前版或下一版；
- `--out`：参考方案输出目录；
- `--real` / `--offline`：真实模型或 stub；
- `--roles`：只跑子集（用于修复单个角色）；
- `--kb`：注入知识库引用；
- `--note`：给全团队的调整要求；
- `--force`：允许写入非空目录。

## 门禁

- 每个角色必须落盘自己的 artifact，不能只返回摘要；
- 必须引用 `SRC-###`；来源覆盖率缺失则失败；
- 产品文档必须有目标/非目标/流程/验收；
- 流程必须有状态、事件、失败/恢复；
- 发布方案必须有版本、兼容、迁移、特性开关、灰度、回滚；
- 预演必须有至少 3 个升级场景、基线、指标、回滚时间、Go/No-Go；
- 红队至少 5 条带来源的矛盾/缺口；
- 任一角色门禁失败，最终 `REFERENCE-PLAN.md` 标记 fail，退出码非零。

## 以后发版的推荐流程

1. 准备新版本产品文档。
2. 先跑本团队，输出 `reviews/<version>/REFERENCE-PLAN.md`。
3. 与上一版 `REFERENCE-PLAN.md` 做差异：
   - 新增/删除功能；
   - 流程/状态变化；
   - 数据/契约迁移；
   - 回滚与兼容风险。
4. 用 `08-rehearsal.md` 的补丁/小版本/大版本场景做 Go/No-Go。
5. 方案通过后，再把 `04-feature-spec.md` / `03-product-flows.md` 交给开发团队（`start_project.py`）。
6. 发版后把实际结果回填到 `10-playbook.md`，形成下一次的基线。

## 示例

`reviews/test1-product/REFERENCE-PLAN.md` 已对 `test1` 产品基准跑完：

- 11/11 角色门禁通过；
- 22/22 来源章节覆盖；
- 输出补丁/小版本/大版本预演、兼容/迁移/回滚方案、红队问题和升级清单。

## 与交付团队的关系

| 团队 | 目的 | 输出 |
|---|---|---|
| Product Review Team | 产品文档深析、流程细化、升级预演 | 参考方案、门禁、Go/No-Go |
| Delivery Team (`start_project.py`) | 把方案做成可运行产品 | 代码、测试、项目 acceptance |

**先评审，再开发**：发版/升级场景不允许跳过 Product Review Team 直接进入实现。
