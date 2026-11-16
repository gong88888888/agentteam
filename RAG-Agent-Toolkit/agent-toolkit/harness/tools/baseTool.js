/**
 * BaseTool — 所有 Harness 工具的基类
 */
class BaseTool {
  constructor(name, description) {
    this.name        = name;
    this.description = description;
  }

  /** 子类必须覆盖此方法，返回 Promise<any> */
  async execute(input) {
    throw new Error(`Tool "${this.name}" 未实现 execute() 方法`);
  }
}

module.exports = BaseTool;
