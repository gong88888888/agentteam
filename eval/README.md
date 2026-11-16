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

真实 DeepSeek（`deepseek-key1` 自动识别，J1/J3=DeepSeek，J2=本地 Qwen）：judge 11/11，canary 7/7，agents 6/6，revalidation 4/4；约 14 次调用（DeepSeek 3 / 本地 11），55 秒，19.6K Token，$0.0039，`family_collisions=0`。

> `family_collisions` 表示裁判是否因 DeepSeek 不可用降级到本地 Qwen。生产环境使用 `deepseek-key1`/`DEEPSEEK_API_KEY` 时 J1/J3 是 DeepSeek、J2 是本地 Qwen，不同家族；`--allow-local-judge` 仅用于无 Key 预演。


## W4：角色 golden set / prompt 回归 / 知识库召回

```bash
python prompts/build_prompts.py
python eval/role_eval.py --offline
python eval/role_eval.py --real --roles product,review --limit 2
python eval/prompt_regression.py --offline
python eval/prompt_regression.py --real --roles product --limit 1
python eval/kb_eval.py
python eval/kb_eval.py --real   # 使用 data/knowledge.db (bge-m3)
```

- `role-eval.md/json`：12 角色 × 2 用例；schema/required/keyword 通过率。
- `prompt-regression.md/json`：baseline `prompts/roles` vs candidate `prompts/candidates/strict-json`，delta、regressed/improved、prompt hash。
- `kb-eval.md/json`：recall@5 与 source_type filter。

当前结果：离线 role 24/24；真实 product 子集 1/1；prompt 回归无退化；知识库 recall@5 7/7（hash 与 bge-m3 均通过）。
