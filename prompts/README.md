# Role Prompts & Regression

版本化角色提示词。提示词不是手写散的 Markdown，而是从 `specs/agent-specs.yaml` + 本地技能注册表生成，可复现、可哈希、可回归。

## 结构

```
prompts/
├── build_prompts.py                 # 从 specs + skills 生成
├── registry.yaml                    # 12 角色 × 2 版本的 hash
├── roles/<role>.md                 # baseline v1
└── candidates/strict-json/<role>.md # candidate v2（严格 JSON 契约）
```

每个提示词包含：

- `ROLE:` 标记（stub/路由识别用）
- 角色定位、工具白名单、读写范围、禁止事项
- 输出契约（`agent-output.schema.json` + JSON 示例）
- 失败处理（重试/升级/阻塞）
- 适用本地技能（ui/frontend/qa/retro/review）

## 生成

```bash
python prompts/build_prompts.py
```

生成后 `prompts/registry.yaml` 记录每个 role/version 的 SHA256 前 16 位；Agent 输出和评测行会带上 `prompt.version/hash`。

## 评测

```bash
# 12 角色 × 2 用例，离线 stub
python eval/role_eval.py --offline

# 真实本地 Qwen，限定角色/用例控制成本
python eval/role_eval.py --real --roles product,review --limit 2

# 基线 vs 候选提示词回归
python eval/prompt_regression.py --offline
python eval/prompt_regression.py --real --roles product --limit 1
```

输出：

- `eval/out/role-eval.md/json`：schema / required / keyword 通过率、按角色统计
- `eval/out/prompt-regression.md/json`：baseline vs candidate 的 delta、regressed/improved、prompt hash

回归阈值：schema/required 下降 >2pp 或 keyword 下降 >5pp 判为 regression。离线模式使用 role-aware stub，提示词不影响输出，delta 为 0；真实回归必须加 `--real`。

## 注意

- 候选 v2 只是示例变体（更严格的 JSON 契约）；真实调参请在 `build_prompts.py` 中改候选模板并重新生成。
- 生产使用前必须用真实模型跑全量 12 角色 golden set；当前仓库默认只做离线全量 + 真实子集，避免评测成本失控。
