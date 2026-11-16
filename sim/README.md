# 预演器说明（v4.1）

两个脚本都是**确定性编排层演练**，不调用真实 LLM；Agent 产出与裁判结论由脚本化 rubric 桩生成，用于验证调度、证据、裁决协议是否自洽，不代表模型真实能力。

## 运行

```bash
# v4.1：工具签名证据 + 外部模型裁判（deepseekharness），无人工审批
python -I sim/dryrun.py

# v3：人审批基线（用于对比）
python -I sim/_baseline_v3.py

# 规格书/契约校验
python -I specs/validate_specs.py

# 编排协议回归自检（正常/无故障/重复ID/DAG环/重试上限/预算）
python -I sim/selfcheck.py
```

## 输出

| 路径 | 内容 |
|---|---|
| `sim/out/v4/events.jsonl` | v4.1 完整事件账本 |
| `sim/out/v4/timeline.md` | v4.1 时间线 |
| `sim/out/v4/metrics.json` | v4.1 指标 |
| `sim/out/v4/auto-report.md` | v4.1 自动报告 |
| `sim/out/human/...` | v3 人审批基线的同名产物 |

`sim/dryrun_v4.0.py` 保留为上一版对照：它的裁判在机器检查之前批准，门禁仍读 Agent 自述，无故障注入会死锁。不要把它当作正确实现。

## v4.1 覆盖的协议

- 切片 DAG、4 并发、任务卡状态机、条件依赖 `deps_any`；
- **门禁顺序**：机器确定性检查 → 组装决策包 → 外部裁判 → 签发凭证；
- **工具签名证据**：`tool_check` 生成 `subject_hash` + `baseline_fp` + `signed_by`；Agent 自述只进 `worker_claims`；
- **六维缓存指纹**：kind + subject + baseline_fp + tool/version + rule + env；复用按事件计数；
- **证据失效**：内容哈希、基线升级、代码变更、裁决失效自动传播；`s2_gate` 被置为 SUPERSEDED，强制 `s2_regate`；
- 裁判 J1/J2/J3、双裁判分歧、超时失败关闭、schema 校验、`need_evidence` 最小补证；
- 金丝雀校准（漏判 20% 触发保守模式）、提示词注入隔离；
- 范围变更自动 defer；
- 预算 80% 预警、100% 硬停；重试硬上限；非 0 退出码。

## 当前结果（单项目、3 切片、4 并发）

| 指标 | v3 人审批 | v4.1 |
|---|---|---|
| 状态 | completed | completed |
| 虚拟工期 | 1,910 min | 1,252 min |
| 人决策 / 人等待 | 7 / 1,545 min | 0 / 0 |
| 裁判次数 / 等待 | — | 20 / 82 min |
| 门禁首过 | 6/7 | 3/8 |
| 返工 | 4 | 6 |
| 任务 | 52 | 59（成功 56 / 失败 2 / 被取代 1） |
| 证据 | 34 | 80（复用 9 / 失效 3） |
| 裁决 | — | 9 份（1 份失效后复评） |
| 缺陷 | 2（致命 1） | 2（致命 1，全部闭环） |

**首过率 38% 不是质量下降**：产品/架构/验收门禁被裁判要求补证，发布门禁超时后重试，S2 在缺陷修复后强制复评。详见 `agentteam-v4-外部模型裁判.md` §7。

## 口径

任务时长、Token、费用为设定/估算值；单项目、3 切片，不能外推为所有项目的工期。真实接入 DeepSeek 前，必须用金标准集测出裁判漏判率与误批率，并用真实 `JudgeBackend` 替换脚本化 rubric 桩。
