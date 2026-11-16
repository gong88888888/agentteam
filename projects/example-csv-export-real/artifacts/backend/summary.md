# backend · 后端实现

- 状态：done
- 摘要：代码文件已生成：src/backend/mini_ledger/services/export_service.py

## Claims（不参与门禁）

- 实现了 /api/v1/exports/csv 接口，支持按月份导出用户自有记录。
- 导出了 UTF-8 with BOM 格式的 CSV，包含 date, amount, category, note 字段。
- 实现了 owner 校验，确保用户只能导出自己的数据。
- 实现了 10 万行限制，超出返回错误。
- 处理了空数据月份的情况，导出合法空 CSV。

## 写入文件

- `src/backend/mini_ledger/services/export_service.py` · b556ef837416

## 未决问题

- 需要确认数据库查询是否支持流式读取以优化 P95 性能，当前实现假设 ORM 支持分页或流式查询。
