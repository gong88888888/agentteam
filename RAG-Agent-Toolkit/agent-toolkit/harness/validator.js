/**
 * Harness 验证器注册表
 * 内置：textValidator / jsonValidator / fileValidator
 */

class ValidatorRegistry {
  constructor() {
    this.validators = new Map();
    this._registerBuiltins();
  }

  register(name, fn) {
    this.validators.set(name, fn);
  }

  validate(name, value) {
    const fn = this.validators.get(name);
    if (!fn) return { valid: true }; // 无验证器视为通过
    try {
      return fn(value);
    } catch (e) {
      return { valid: false, message: e.message };
    }
  }

  _registerBuiltins() {
    // 文本非空校验
    this.register('textValidator', (v) => {
      const text = typeof v === 'string' ? v : (v?.text || v?.content || '');
      if (!text || text.trim().length < 10)
        return { valid: false, message: '输出文本为空或过短（< 10 字符）' };
      return { valid: true };
    });

    // JSON 结构校验（至少是有效 JSON 对象/数组）
    this.register('jsonValidator', (v) => {
      if (v && typeof v === 'object') return { valid: true };
      try { JSON.parse(v); return { valid: true }; }
      catch { return { valid: false, message: '输出不是合法 JSON' }; }
    });

    // 文件路径校验（路径字符串非空）
    this.register('fileValidator', (v) => {
      const p = v?.filePath || v?.path || (typeof v === 'string' ? v : '');
      if (!p) return { valid: false, message: '未返回文件路径' };
      return { valid: true };
    });
  }
}

module.exports = new ValidatorRegistry();
