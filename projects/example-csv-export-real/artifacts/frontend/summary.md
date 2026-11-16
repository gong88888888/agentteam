# frontend · 前端实现

- 状态：done
- 摘要：代码文件已生成：src/frontend/hooks/useExport.ts

## Claims（不参与门禁）

- 实现了 ExportModal 组件，支持月份选择、导出按钮及加载/错误状态反馈。
- 实现了 useExport hook，处理 API 调用、Blob 下载逻辑及错误边界。
- 实现了 csvExport 工具函数，确保 UTF-8 BOM 编码以兼容 Excel。

## 写入文件

- `src/frontend/hooks/useExport.ts` · e3f3e7c41626

## 未决问题

- 确认后端导出接口路径（如 GET /api/exports/csv?year=2023&month=10）及响应头 Content-Disposition 格式。
- 确认前端是否已有通用的 FileDownload 组件，若无则当前实现为独立逻辑。
