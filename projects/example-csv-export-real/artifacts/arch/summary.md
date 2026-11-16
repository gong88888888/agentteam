# arch · 架构与契约

- 状态：done
- 摘要：完成 MiniLedger CSV 导出功能的架构设计与接口契约。核心决策包括：1) 接口规范：定义 GET /api/v1/ledger/export 端点，参数 month (YYYY-MM)，响应为 application/csv；2) 安全约束：强制复用现有认证中间件，服务端查询时注入 owner_id 过滤条件，严禁前端控制可见性；3) 性能与边界：设定 10 万行硬限制以保护内存，空月份返回合法空 CSV（仅 Header）；4) 编码规范：明确 UTF-8 with BOM 以兼容 Excel。未引入新服务或消息队列，完全复用现有记录查询接口。

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-REAL-arch

## Claims（不参与门禁）

- 导出接口采用 GET /api/v1/ledger/export?month=YYYY-MM，复用现有认证中间件校验 owner。
- 服务端强制过滤非当前用户记录，确保数据隔离。
- 导出格式为 UTF-8 + BOM CSV，字段顺序固定为 date, amount, category, note。
- 定义 10 万行硬限制，超限返回 413 Payload Too Large 或自定义错误码。

## 写入文件

- `docs/architecture/architecture.md` · 6df9b5693fe3 · runner-summary

## 未决问题

- 无

## 门禁检查

- 全部通过
