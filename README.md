# AgentTeam

一人公司主导的全栈交付 Agent 集群。当前仓库包含 **v4.1 编排协议**、**W1/W2 真实适配层**、**W3 三切片并行/共享文件/契约影响/Serial Baseline** 与 **W4 角色 golden set/prompt 回归、混合检索知识库、决策收件箱**：本地 Qwen 3.6 负责执行 Agent，DeepSeek（deepseekharness）负责裁判或作为补充；门禁只接受工具签名证据，裁决和证据失效可审计、可复评；W3 监控工作台在 `dashboard/`。

## 先看这几份

| 文档 | 作用 |
|---|---|
| [agentteam-v4-外部模型裁判.md](agentteam-v4-外部模型裁判.md) | v4 目标架构：外部模型裁判 J1/J2/J3 |
| [agentteam-评审报告-2026-11-16.md](agentteam-评审报告-2026-11-16.md) | 独立评审：问题清单与改进方向 |
| [修复实施记录.md](修复实施记录.md) | 对照《修复建议1.md》逐项修复与验证 |
| [specs/README.md](specs/README.md) | 任务卡/证据/决策包/裁决/Agent 规格 |
| [eval/README.md](eval/README.md) | W2 评测集、金丝雀与阈值 |

## 快速运行

```bash
# 编排层预演（无真实 LLM）
python -I sim/dryrun.py
python -I sim/selfcheck.py

# W1：检查本地模型/账本/技能
python -m orchestrator.cli check-env
python -m orchestrator.cli demo --offline
python -m orchestrator.cli skills --role ui

# W1/W2：离线评测（CI）
python eval/run_eval.py --offline

# W1/W2：真实本地模型（Qwen 3.6；无 DeepSeek Key 时裁判显式降级）
python eval/run_eval.py --real --allow-local-judge

# 配置 DEEPSEEK_API_KEY 或 Windows 用户变量 deepseek-key1 后：
# J1/J3 走 DeepSeek，J2 走本地 Qwen
python eval/run_eval.py --real

# W3：3 切片并行 / 共享文件冲突 / 契约变更影响图 / serial baseline
python sim/w3.py --mode both
python sim/w3_selfcheck.py

# W3 监控工作台（静态 HTML，可离线打开）
python dashboard/build.py
# open dashboard/index.html，或 python dashboard/serve.py --port 8765

# W4：角色 golden set + prompt 回归
python prompts/build_prompts.py
python eval/role_eval.py --offline
python eval/prompt_regression.py --offline

# W4：知识库混合检索（bge-m3 + FTS5）
python -m orchestrator.cli kb-index
python eval/kb_eval.py

# W4：决策收件箱
python dashboard/serve.py --port 8765
# open http://localhost:8765/decisions.html
```

## 结果

| 指标 | v3 人审批 | v4.1 编排预演 |
|---|---|---|
| 虚拟工期 | 1,910 min | 1,252 min（-34%） |
| 人决策 / 人等待 | 7 / 1,545 min | 0 / 0 |
| 裁判调用 / 等待 | — | 20 / 82 min |
| 门禁首过 | 6/7 = 86% | 3/8 = 38%（口径更严） |
| 返工 | 4 | 6（含 2 次补证） |
| 任务 | 52 | 59（成功 56 / 失败 2 / 被取代 1） |
| 证据 | 34 | 80（复用 9 / 失效 3） |
| 缺陷 | 2（致命 1） | 2（致命 1，全部闭环） |

W2 评测：

| 模式 | Judge | Canary | Agents | Revalidation | 模型调用 |
|---|---|---|---|---|---|
| `--offline` | 11/11 | 7/7 | 6/6 schema | 4/4 | stub |
| `--real --allow-local-judge` | 11/11 | 7/7 | 6/6 schema | 4/4 | 13 次 / 49s / 17.2K Token / $0（本地） |
| `--real`（DeepSeek J1/J3 + 本地 J2） | 11/11 | 7/7 | 6/6 schema | 4/4 | 约 14 次 / 55s / 19.6K Token / $0.0039，family=0 |

> `deepseek-key1` / `DEEPSEEK_API_KEY` 会自动识别，无需手动 export。真实 DeepSeek 模式下 J1/J3 与 J2（本地 Qwen）不同家族，`family_collisions=0`。`--allow-local-judge` 仅在无 Key 或离线预演时显式降级，会产生 family collision。

W3 结果（3 切片、共享 package.json/ui-tokens、X1 契约变更）：

| 指标 | Parallel | Serial baseline |
|---|---|---|
| 虚拟工期 | 1,302 min | 2,815 min |
| 平均排队等待 | 12.8 min | 60.7 min |
| 峰值并发 | 4 | 1 |
| 共享文件冲突 / 锁等待 | 3 / 85 min | 0 / 0 |
| 契约变更 / 影响任务 | 1 / 6（3 切片） | 1 / 6（3 切片） |
| 门禁首过 | 38% | 50% |
| 返工 | 7 | 6 |
| 裁判调用 / 成本 | 24 / $0.27 | 23 / $0.266 |

**并行加速比 2.16x**。共享文件冲突与锁等待是并行带来的真实成本；契约变更会失效 3 个切片的旧证据并强制 3 个复评门禁。

## W4 结果

| 能力 | 结果 |
|---|---|
| 角色 golden set（12 角色 × 2 用例，离线） | schema 24/24 · required 24/24 · keyword 24/24 |
| 真实子集（product，1 用例） | schema/required/keyword 1/1 |
| Prompt 回归（offline baseline vs strict-json） | delta 0 · regressed=false |
| Prompt 回归（real product 1 用例） | schema/required/keyword 均 1.0；tokens 1,113 → 1,053，无回归 |
| 知识库（bge-m3 + FTS5） | 61 docs / 735 chunks；kb recall@5 **7/7**；source filter 2/2 |
| 决策收件箱 | 3 个示例决策；approve / conditions / reject / defer / request evidence；审计持久化 |

角色提示词由 `specs/agent-specs.yaml` + 本地技能生成，版本和 hash 见 `prompts/registry.yaml`；知识库对应 RAGFlow 的解析/切块/embedding/混合检索/引用思想，但不引入其重型运行时；决策收件箱只处理升级、审计与 L3 策略变更，不把常规门禁退回人工。

## 模型路由

| 角色 | 主模型 | 补充 |
|---|---|---|
| 产品/UI/架构/前端/后端/评审/QA/安全/运维/知识库/复盘 | 本地 `qwen3.6:35b-a3b-mtp-q4_K_M` | DeepSeek `deepseek-chat` |
| 裁判 J1 | DeepSeek `deepseek-chat` | 本地 Qwen（仅 `--allow-local-judge`） |
| 裁判 J2 | 本地 Qwen（不同家族） | DeepSeek |
| 裁判 J3 | DeepSeek `deepseek-reasoner` | 本地 Qwen（仅显式降级） |

本地 Qwen 3.x 是推理模型；`ollama.think=false` 关闭 thinking，直接输出 JSON。配置见 [config/config.example.yaml](config/config.example.yaml)，密钥从 `.env`、环境变量或 Windows 用户变量 `deepseek-key1` 读取。

## 目录

```
orchestrator/          W1/W2：模型路由、裁判、证据账本、裁决账本、技能、CLI
  models/              Ollama(qwen3.6) / DeepSeek / Stub / Router
  judge/               packet / verdict / panel / canary / revalidation / rubric
  evidence/            evidence store / verdict store / dependency graph / signing
eval/                  W2/W4 评测：金丝雀、role golden set、prompt 回归、知识库召回
dashboard/             W3 监控工作台 + W4 决策收件箱（静态 HTML + API）
prompts/               12 角色版本化提示词 + 候选 v2 + registry
knowledge/             RAGFlow 风格混合检索说明（FTS5 + bge-m3 + RRF）
skills/                本地技能注册表（引用 RAG-Agent-Toolkit 的 4 个技能）
specs/                 任务卡、证据、决策包、裁决、Agent 规格
rubrics/               产品/架构/代码/验收/发布/复核 rubric
sim/                   编排协议预演（v4.1 + W3），v4.0 备份在 dryrun_v4.0.py
config/                配置示例（只放环境变量名）
```

## 当前边界

- 裁判真实调用依赖 DeepSeek Key；没有 Key 时默认失败关闭，`--allow-local-judge` 是显式降级并记录 family collision。
- 本地 Qwen 输出通过 Schema 校验与少量“格式修复”（只修 severity/line/额外字段，不改 decision/evidence），修复次数记录在 `schema_repairs`。
- 机械硬约束先于裁判执行：确定性失败、缺证据、未签名证据、越界写、高危漏洞、无回滚发布、指令性文本，裁判无权批准。
- 医疗、金融持牌等要求人工签核的场景不适用本方案。
- W3 的共享文件锁是内存租约模型；真实仓库的 worktree/锁文件/合并冲突仍需执行层。
- W4 的 role eval 默认全量离线、真实只跑子集；全量 12 角色真实评测需按预算单独跑。
- 知识库未直接运行 RAGFlow（依赖 Elasticsearch/MySQL/Redis），复用其检索概念；`data/knowledge.db` 可重建。
- 决策收件箱是策略所有者/审计入口；常规门禁仍由 J1/J2/J3 裁决，不逐次人工审批。
- 尚未实现：真实 CI/测试工具签名、容器沙箱、工作树租约、进程崩溃恢复、完整 MCP 服务端；W1/W2/W3 的评测、账本与工作台是本地可运行版本。
- 监控工作台读取 `sim/out/w3`；重新跑 W3 后执行 `python dashboard/build.py` 刷新。
