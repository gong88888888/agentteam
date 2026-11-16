# backend · 后端实现

- 状态：done
- 摘要：代码文件已生成：src/backend/ledger/export.py

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-REAL-backend

## Claims（不参与门禁）

- 实现了 GET /api/v1/ledger/export 接口，支持按月份导出 CSV。
- 强制校验 owner_id，确保用户只能导出自己的记录。
- 实现了 10 万行硬限制和空月份合法返回逻辑。
- 输出文件使用 UTF-8 with BOM 编码以兼容 Excel。

## 写入文件

- `src/backend/ledger/export.py` · 72ce2939be44 · role

## 未决问题

- 无

## 门禁检查

- 全部通过
