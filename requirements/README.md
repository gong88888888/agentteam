# Requirements

需求选择的唯一目的是**防止范围蔓延**：先出题（backlog），再按策略评分选一个可验收的需求，最后才启动项目。

## 选择规则

评分是策略所有者设定的确定性规则，不由执行 Agent 自由扩范围：

```
评分 = (价值×2 + 战略×2 + (2-工作量) + (2-风险) + (2-依赖)) / 12 × 10
```

- `now`：≥8，且没有未满足依赖
- `next`：6-8，或有未满足依赖
- `later`：<6

每个需求必须写清：目标用户、非目标、可量化验收标准、约束、依赖。缺验收标准直接拒绝。

## 示例

```bash
python -m orchestrator.requirements select \
  --backlog requirements/backlog.example.yaml \
  --out requirements/examples/csv-export
```

输出：

- `selection.md`：所有需求评分表、选中项与选择规则
- `selected.yaml`：机器可读的选中需求
- `selected.md`：项目启动脚本使用的需求文件

示例 backlog 中，`REQ-CSV` 得分 10/10 进入 now；多币种 5.0 进入 later；家庭共享 5.8 进入 later。

## 启动项目

```bash
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export \
  --offline
```

`--offline` 用确定性 stub 走通角色流水线；`--real` 用本地 Qwen 3.6（DeepSeek 补充）实际生成。每个角色的 prompt、输出、meta、日志和 artifact 都会落到项目目录。
