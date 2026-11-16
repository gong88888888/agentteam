# W2 Evaluation

评估裁判、金丝雀、执行 Agent 与复核计划。默认离线，不调用网络模型。

## 运行

```bash
# 离线（CI）：stub 裁判 + stub Agent
python eval/run_eval.py --offline
python -m orchestrator.cli eval --offline

# 真实本地模型：Qwen 3.6（执行 Agent + 本地裁判降级）
python eval/run_eval.py --real --allow-local-judge
python eval/run_eval.py --real --allow-local-judge --limit 3

# 真实裁判：设置 DEEPSEEK_API_KEY 后，J1/J3 走 DeepSeek，J2 走本地 Qwen
export DEEPSEEK_API_KEY=...
python eval/run_eval.py --real
```

## 数据集

| 文件 | 内容 |
|---|---|
| `eval/golden/judge_cases.yaml` | 11 个门禁决策包：通过/测试失败/缺证据/未签名/越界/高危漏洞/无回滚/注入/验收缺失 |
| `eval/golden/agent_cases.yaml` | 6 个执行 Agent 场景：产品/架构/后端/评审/QA/复盘 |
| `eval/golden/revalidation_cases.yaml` | 4 个复核计划：只追加/删强制项/哈希不匹配/追加缺 why |

## 指标

- `judge.false_approve`：坏包被批准，必须为 0；
- `judge.errors`：裁判失败（失败关闭），必须为 0；
- `canary.miss_rate`：金丝雀漏判率，阈值 10%；
- `agents.schema_rate`：输出符合 `agent-output.schema.json` 的比例；
- `revalidation.passed`：只加不减、强制项不被删除；
- `models`：调用次数、延迟、Token、费用、family collision。

报告写入 `eval/out/report.md` 与 `eval/out/metrics.json`。

## 当前结果

离线：judge 11/11，canary 7/7，agents 6/6，revalidation 4/4。

真实本地（Qwen 3.6，未配置 DeepSeek Key，`--allow-local-judge`）：judge 11/11，canary 7/7（坏包由机械硬拦），agents 6/6，revalidation 4/4；13 次模型调用，约 49 秒，17.2K Token，$0（本地）；`family_collisions=6`。

> 注意：`family_collisions` 表示 J1/J3 因没有 DeepSeek Key 降级到了本地 Qwen，与 J2 同族。生产环境应配置 `DEEPSEEK_API_KEY`，让 J1/J3 使用 DeepSeek、J2 使用本地 Qwen，避免同族盲点。真实 DeepSeek API 的裁决准确率尚未在本机验证。
