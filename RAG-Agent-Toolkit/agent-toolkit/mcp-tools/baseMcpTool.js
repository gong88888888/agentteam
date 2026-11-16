/**
 * BaseMcpTool — MCP 工具基类
 *
 * 所有文档处理 / 知识图谱工具都继承此类。
 * 提供：
 *   - 标准化 call() 包装（计时、异常捕获、日志）
 *   - toMcpDefinition() 生成 MCP 工具描述
 *   - inputSchema 声明（供 AI 调度器理解参数）
 */
class BaseMcpTool {
  /**
   * @param {string} name        工具唯一名称
   * @param {string} description 一句话描述（供 AI 理解）
   * @param {Object} inputSchema JSON Schema 描述入参
   */
  constructor(name, description, inputSchema = {}) {
    this.name        = name;
    this.description = description;
    this.inputSchema = inputSchema;
  }

  /**
   * 子类必须覆盖：实际执行逻辑
   * @param {Object} input — 经过沙箱安全处理的入参
   * @returns {Promise<any>}
   */
  async execute(input) {
    throw new Error(`工具 "${this.name}" 必须实现 execute() 方法`);
  }

  /**
   * 统一调用包装：计时 + 异常捕获 + 日志
   * @param {Object} input
   * @returns {Promise<{success, data, error, durationMs}>}
   */
  async call(input = {}) {
    const t0 = Date.now();
    try {
      const data = await this.execute(input);
      const durationMs = Date.now() - t0;

      // 异步写日志（不阻塞主流程）
      this._log({ tool: this.name, input, output: data, durationMs, success: true });

      return { success: true, data, error: null, durationMs };
    } catch (err) {
      const durationMs = Date.now() - t0;
      this._log({ tool: this.name, input, error: err.message, durationMs, success: false });
      return { success: false, data: null, error: err.message, durationMs };
    }
  }

  /**
   * 生成标准 MCP 工具描述（用于 tools/list 接口）
   */
  toMcpDefinition() {
    return {
      name:        this.name,
      description: this.description,
      inputSchema: this.inputSchema
    };
  }

  _log(entry) {
    try {
      const callLogger = require('./callLogger');
      callLogger.record(entry);
    } catch { /* 日志失败不影响主流程 */ }
  }
}

module.exports = BaseMcpTool;
