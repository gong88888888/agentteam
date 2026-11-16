import { useState, useCallback } from 'react';

// Types for the export hook state and API response handling
export type ExportStatus = 'idle' | 'loading' | 'success' | 'error';

export interface ExportError {
  message: string;
  code?: string;
}

interface UseExportOptions {
  onProgress?: (status: ExportStatus, message?: string) => void;
}

/**
 * Hook to handle CSV export logic for MiniLedger.
 * 
 * Responsibilities:
 * 1. Construct the API request with authentication headers.
 * 2. Fetch the CSV blob from the backend.
 * 3. Handle UTF-8 BOM and file download in the browser.
 * 4. Manage loading, success, and error states.
 * 
 * Constraints:
 * - Does not handle owner_id logic (backend handles via auth middleware).
 * - Handles >100k row errors if returned by backend.
 */
export function useExport(options: UseExportOptions = {}) {
  const [status, setStatus] = useState<ExportStatus>('idle');
  const [error, setError] = useState<ExportError | null>(null);

  const triggerExport = useCallback(async (month: string) => {
    // Validate month format YYYY-MM
    if (!/^\d{4}-\d{2}$/.test(month)) {
      const err: ExportError = { message: 'Invalid month format. Expected YYYY-MM.', code: 'INVALID_INPUT' };
      setError(err);
      options.onProgress?.('error', err.message);
      return;
    }

    setStatus('loading');
    setError(null);
    options.onProgress?.('loading', `Exporting records for ${month}...`);

    try {
      // Use relative path to respect proxy/base URL configurations
      const url = `/api/v1/ledger/export?month=${encodeURIComponent(month)}`;
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'text/csv,application/octet-stream',
          // Auth token is typically injected via a global interceptor or context.
          // If using cookies for auth, credentials: 'include' handles it automatically.
          // If using Bearer tokens, ensure they are attached here or via fetch wrapper.
        },
        credentials: 'include', // Ensure cookies/session are sent if applicable
      });

      if (!response.ok) {
        let errorMsg = `Export failed with status ${response.status}`;
        try {
          const errorData = await response.json();
          if (errorData.message) {
            errorMsg = errorData.message;
          }
        } catch {
          // Ignore JSON parse errors for non-JSON responses
        }
        
        throw new Error(errorMsg);
      }

      const contentType = response.headers.get('content-type') || '';
      
      // Backend should return application/csv or application/octet-stream with UTF-8 BOM.
      // We assume the backend handles the BOM injection as per contract.
      
      const blob = await response.blob();
      
      // Create a download link and trigger it
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.setAttribute('download', `ledger_export_${month}.csv`);
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(downloadUrl);

      setStatus('success');
      options.onProgress?.('success', 'Export completed successfully.');
      
      // Reset status after a short delay to allow user to see success message if needed
      setTimeout(() => {
        setStatus('idle');
      }, 3000);

    } catch (err) {
      const exportError: ExportError = {
        message: err instanceof Error ? err.message : 'An unknown error occurred during export.',
        code: 'EXPORT_FAILED',
      };
      
      // Check for specific backend constraints like row limits if present in message
      if (exportError.message.includes('100000') || exportError.message.includes('limit')) {
        exportError.code = 'ROW_LIMIT_EXCEEDED';
      }

      setError(exportError);
      setStatus('error');
      options.onProgress?.('error', exportError.message);
    }
  }, [options]);

  return {
    status,
    error,
    triggerExport,
    resetStatus: () => setStatus('idle'),
  };
}