/**
 * MCP 工具沙箱
 * - 统一的执行入口：超时控制、异常捕获、资源限制
 * - 把工具执行包装为 Promise，超时后自动 reject
 */

const DEFAULT_TIMEOUT_MS    = 60_000;
const DEFAULT_MAX_PAYLOAD   = 5 * 1024 * 1024; // 5MB 输入上限

class McpSandbox {
  /**
   * 在沙箱中运行工具
   * @param {Function} handler  — 工具实现函数 (input) => Promise<any>
   * @param {Object}   input
   * @param {Object}   options  — { timeoutMs, maxPayloadBytes }
   */
  async run(handler, input, options = {}) {
    const timeoutMs    = options.timeoutMs    ?? DEFAULT_TIMEOUT_MS;
    const maxPayload   = options.maxPayloadBytes ?? DEFAULT_MAX_PAYLOAD;

    // 输入大小校验
    try {
      const size = Buffer.byteLength(JSON.stringify(input || {}), 'utf-8');
      if (size > maxPayload) {
        throw new Error(`输入数据过大（${size} 字节），超出沙箱限制 ${maxPayload} 字节`);
      }
    } catch (e) {
      if (e.message?.includes('沙箱限制')) throw e;
      // JSON 序列化失败也算非法输入
      throw new Error('沙箱拒绝执行：输入不可序列化');
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        reject(new Error(`沙箱超时：工具执行超过 ${timeoutMs}ms`));
      }, timeoutMs);

      Promise.resolve()
        .then(() => handler(input))
        .then(result => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          resolve(result);
        })
        .catch(err => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          reject(err instanceof Error ? err : new Error(String(err)));
        });
    });
  }
}

module.exports = new McpSandbox();
