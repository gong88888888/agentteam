/**
 * Harness 执行日志系统
 * 双写：内存（随 task 对象）+ 磁盘（logs/harness/<taskId>.log）
 */
const fs   = require('fs');
const path = require('path');

const LOG_DIR = path.join(__dirname, '../../logs/harness');
if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true });

class HarnessLogger {
  /** 写一条日志到磁盘 */
  write(taskId, level, message) {
    const entry = JSON.stringify({
      taskId,
      level,
      message,
      timestamp: new Date().toISOString()
    });
    try {
      fs.appendFileSync(path.join(LOG_DIR, `${taskId}.log`), entry + '\n', 'utf-8');
    } catch { /* 磁盘写失败不影响主流程 */ }
  }

  /** 读取某任务全部日志 */
  getTaskLogs(taskId) {
    const file = path.join(LOG_DIR, `${taskId}.log`);
    if (!fs.existsSync(file)) return [];
    try {
      return fs.readFileSync(file, 'utf-8')
        .split('\n')
        .filter(Boolean)
        .map(l => JSON.parse(l));
    } catch {
      return [];
    }
  }

  /** 清理 N 天前的日志文件 */
  cleanup(daysOld = 7) {
    const cutoff = Date.now() - daysOld * 86400_000;
    try {
      for (const f of fs.readdirSync(LOG_DIR)) {
        const fp = path.join(LOG_DIR, f);
        if (fs.statSync(fp).mtimeMs < cutoff) fs.unlinkSync(fp);
      }
    } catch { /* 忽略清理错误 */ }
  }
}

module.exports = new HarnessLogger();
