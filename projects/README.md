# Projects

这里是由 `start_project.py` 生成的角色工作记录示例。每个项目目录都包含：

- `artifacts/<role>/`：prompt、request、output.json、summary.md、meta.json
- `logs/events.jsonl`：role.started / role.finished / file.written
- `state/roles.json`：角色状态与模型/prompt hash
- `src/`：代码角色实际写出的文件（如果有）
- `README.md`：角色执行记录表

| 项目 | 模式 | 角色 | 说明 |
|---|---|---|---|
| `example-csv-export` | 离线 stub | 12 | 验证角色流水线与落盘结构；无真实模型内容 |
| `example-csv-export-real` | 本地 Qwen 3.6 | pm, product, arch, backend, frontend | 真实角色输出；backend/frontend 通过 code pass 写出代码文件 |

重新运行：

```bash
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export-real \
  --real --roles pm,product,arch,backend,frontend --kb --force
```

生产使用前请按 [PROJECT_PLAYBOOK.md](../PROJECT_PLAYBOOK.md) 接入真实工具证据、沙箱与门禁。
