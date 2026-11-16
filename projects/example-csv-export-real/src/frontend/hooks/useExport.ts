import { useState, useCallback } from 'react';
import { exportMonthlyRecords } from '@/utils/csvExport';
import { useAuth } from '@/hooks/useAuth'; // 假设已有认证 Hook

interface UseExportOptions {
  year: number;
  month: number;
}

interface UseExportReturn {
  isExporting: boolean;
  error: string | null;
  exportRecords: () => Promise<void>;
}

/**
 * useExport Hook
 * 处理月度 CSV 导出的业务逻辑：
 * 1. 校验参数范围 (year, month)
 * 2. 调用后端 API 获取 Blob
 * 3. 触发浏览器下载
 * 4. 处理加载与错误状态
 */
export function useExport(): UseExportReturn {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // 假设通过上下文或独立 hook 获取当前用户 ID，用于前端初步校验或日志
  const { user } = useAuth(); 

  const exportRecords = useCallback(async (options: UseExportOptions) => {
    const { year, month } = options;

    // 1. 前置校验
    if (!user) {
      setError('用户未登录，无法导出记录');
      return;
    }
    
    if (year < 2000 || year > 2100) {
      setError('不支持的年份范围');
      return;
    }
    if (month < 1 || month > 12) {
      setError('无效的月份');
      return;
    }

    // 重置状态
    setIsExporting(true);
    setError(null);

    try {
      // 2. 调用导出工具函数
      // csvExport 内部会处理：
      // - 构建 URL: /api/exports/csv?year=YYYY&month=MM
      // - 添加认证 Header (Bearer Token)
      // - 校验响应状态码
      // - 检查 Content-Disposition 文件名
      // - 触发 Blob 下载
      await exportMonthlyRecords(year, month);
      
    } catch (err: any) {
      // 3. 错误处理
      if (err.name === 'AbortError') {
        setError('导出已取消');
      } else if (err.response?.status === 403) {
        setError('权限不足，无法导出该月份记录');
      } else if (err.response?.status === 413 || err.message?.includes('too large')) {
        setError('数据量过大（超过 10 万行），请缩小时间范围或联系管理员');
      } else if (err.response?.status === 500) {
        setError('服务器内部错误，请稍后重试');
      } else {
        setError(`导出失败: ${err.message || '未知错误'}`);
      }
    } finally {
      setIsExporting(false);
    }
  }, [user]);

  return {
    isExporting,
    error,
    exportRecords,
  };
}