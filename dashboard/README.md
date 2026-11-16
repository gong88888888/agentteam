# W3 Dashboard

Self-contained monitoring page for the W3 run: 3-slice parallel delivery,
shared-file lock conflicts, contract impact graph, judge/evidence metrics, and
parallel vs serial baseline.

## Build

```bash
python sim/w3.py --mode both
python sim/w3_selfcheck.py
python dashboard/build.py
```

`dashboard/build.py` reads `sim/out/w3/{parallel,serial}` and writes
`dashboard/index.html` with embedded JSON. The page opens offline with no CDN
or server. `dashboard/data.json` is also written for inspection.

## Open

Open [index.html](index.html) directly, or serve it:

```bash
python dashboard/serve.py --port 8765
```

## What it shows

- Hero: parallel speedup vs serial baseline.
- KPI row: duration, shared-file conflicts, contract impact, gate first pass.
- Duration comparison and wait/rework/conflict table.
- Task lanes (Gantt) built from `events.jsonl`; switch Parallel/Serial.
- Contract impact graph from `impact.json` (contract → slices → fixes → regates → gates).
- Shared-file conflict table (`shared_file.conflict` / `acquired`).
- Judge and evidence counters, verdict distribution, recent event stream.
- Light/dark theme, responsive layout, hover tooltips, table views.

Palette: dataviz reference palette; categorical slots 1/2/3 validated for light
and dark surfaces. Status colors are reserved for success/failure/blocked.


## W4 Decision Inbox

`decisions.html` 是策略所有者/审计入口，只处理升级、审计与 L3 策略变更；常规门禁仍由 J1/J2/J3 裁决。

```bash
python dashboard/serve.py --port 8765
# http://localhost:8765/decisions.html
```

API：

- `GET /api/decisions?status=pending`
- `GET /api/decisions/{id}`
- `POST /api/decisions/{id}/decision` `{action, reason}`
  - action: approve / approve_with_conditions / reject / defer / request_evidence
- `GET /api/decisions/stats`

决策写入 `data/decisions.db`，审计写入 `decision_audit`；首次启动自动 seed 3 个示例决策。

## W5 Project Role Monitor

`projects.html` 读取 `projects/*/artifacts`，展示每个角色的工作记录，并支持单角色调整重跑；W3 工作台与决策收件箱保留不变。

```bash
python start_project.py \
  --requirements requirements/examples/csv-export/selected.md \
  --project-dir projects/example-csv-export --offline
python dashboard/serve.py --port 8765
# http://localhost:8765/projects.html
```

页面内容：

- 项目列表与状态；需求原文可展开。
- 角色卡片：状态、模型、耗时、Token、写出文件、是否按调整要求重跑。
- 详情页签：摘要、输出 JSON、System Prompt、实际请求（含调整要求与前置摘要）、Meta、文件内容。
- 调整重跑：填写补充要求后只重跑当前角色；默认 stub，取消勾选调用本地 Qwen/DeepSeek。

API：

- `GET /api/projects`
- `GET /api/projects/{name}`
- `GET /api/projects/{name}/roles/{role}`
- `GET /api/projects/{name}/file?path=src/backend/...`
- `POST /api/projects/{name}/roles/{role}/rerun` `{note, offline}`

重跑写入新的 `request.md`、`meta.json`（含 `adjustment`）与 `logs/events.jsonl` 的 `role.started`；已有其他角色记录保留。
