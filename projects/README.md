# Projects

这里是由 `start_project.py` 生成的角色工作记录示例。每个项目目录都包含：

- `artifacts/<role>/`：prompt、request、output.json、summary.md、meta.json（含 gate/tools/quality）
- `evidence/tool-ledger.jsonl`：HMAC 签名工具证据 + 哈希链
- `quality/history.jsonl`：角色质量分历史
- `logs/events.jsonl`：role/tool/gate/quality 事件
- `state/roles.json`：角色状态、模型、prompt hash、门禁与质量
- `src/`、`tests/`、`contracts/`、`docs/`：模板与角色写出文件
- `README.md`：角色/门禁/质量执行记录表

| 项目 | 模式 | 角色 | 说明 |
|---|---|---|---|
| `example-csv-export` | 离线 stub | 12 | 模板 + 门禁 + 工具证据 + 质量分全链路；无真实模型内容 |
| `example-csv-export-real` | 本地 Qwen 3.6 | pm, product, arch, backend, frontend | 真实角色输出；backend/frontend 通过 code pass 写出代码文件 |

重新运行（模板、沙箱、证据 profile 可选）：

```bash
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export-real \
  --real --roles pm,product,arch,backend,frontend --kb \
  --template minimal-api --force
```

```bash
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/secure-run \
  --offline --template minimal-api --sandbox \
  --tool-profile standard --stop-on-gate
```

生产使用前请按 [PROJECT_PLAYBOOK.md](../PROJECT_PLAYBOOK.md) 接入真实测试/契约/扫描证据；`minimal-api` 只是脚手架，TODO 不算交付物。
