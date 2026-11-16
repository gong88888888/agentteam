# frontend · 前端实现

- 状态：done
- 摘要：代码文件已生成：src/frontend/hooks/useExport.ts

- 门禁：pass · G-EXAMPLE-CSV-EXPORT-REAL-frontend

## Claims（不参与门禁）

- 实现了 ExportPanel 组件，包含月份选择器、导出按钮及状态反馈（加载/成功/错误）。
- 实现了 useExport hook，处理 GET /api/v1/ledger/export 请求，自动处理 BOM 头与 Blob 下载。
- 前端仅负责 UI 交互与文件保存，所有权校验由后端通过认证中间件完成，前端不传递 owner_id。

## 写入文件

- `src/frontend/hooks/useExport.ts` · f74b9e987a82 · role

## 未决问题

- 当前项目模板中未提供具体的 CSS 框架或 UI 库约定（如 Tailwind, AntD）。代码使用内联样式/基础 CSS 类名，需根据实际项目配置调整。
- 月份选择器组件是否复用现有 UI 库？此处假设使用原生 `<input type='month'>` 以保证最小依赖。

## 门禁检查

- 全部通过
