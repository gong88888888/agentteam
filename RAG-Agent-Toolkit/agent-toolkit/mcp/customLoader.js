/**
 * 自定义 MCP 工具加载器
 * - 从 backend/mcp/custom/*.js 加载用户自定义工具
 * - 每个文件 export 一个标准 MCP 工具对象 { name, description, inputSchema, handler, ... }
 * - 安全：require 在主进程，但 handler 调用时仍走 sandbox.run()
 */
const fs   = require('fs');
const path = require('path');
const registry = require('./registry');

const CUSTOM_DIR = path.join(__dirname, 'custom');
if (!fs.existsSync(CUSTOM_DIR)) fs.mkdirSync(CUSTOM_DIR, { recursive: true });

function loadAllCustom() {
  let count = 0;
  for (const f of fs.readdirSync(CUSTOM_DIR)) {
    if (!f.endsWith('.js')) continue;
    const fp = path.join(CUSTOM_DIR, f);
    try {
      // 清缓存以便热重载
      delete require.cache[require.resolve(fp)];
      const tool = require(fp);
      if (!tool || !tool.name || typeof tool.handler !== 'function') {
        console.warn(`[MCP/custom] 跳过 ${f}：未导出标准工具对象`);
        continue;
      }
      registry.register({ ...tool, source: 'custom' });
      count++;
    } catch (e) {
      console.warn(`[MCP/custom] 加载 ${f} 失败: ${e.message}`);
    }
  }
  console.log(`[MCP] 自定义工具加载完成: ${count} 个`);
  return count;
}

/** 通过上传的代码字符串新增工具（仅 admin 可调用） */
function installFromCode(filename, code) {
  if (!filename.endsWith('.js')) throw new Error('文件名必须以 .js 结尾');
  if (filename.includes('..') || filename.includes('/') || filename.includes('\\'))
    throw new Error('非法文件名');
  if (!/module\.exports\s*=/.test(code)) throw new Error('代码必须用 module.exports 导出工具');
  const fp = path.join(CUSTOM_DIR, filename);
  fs.writeFileSync(fp, code, 'utf-8');
  // 立即加载
  delete require.cache[require.resolve(fp)];
  const tool = require(fp);
  if (!tool || !tool.name || typeof tool.handler !== 'function') {
    fs.unlinkSync(fp);
    throw new Error('代码加载成功但未导出标准 MCP 工具');
  }
  registry.register({ ...tool, source: 'custom' });
  return { ok: true, name: tool.name };
}

function uninstallCustom(name) {
  const file = path.join(CUSTOM_DIR, `${name}.js`);
  if (fs.existsSync(file)) {
    try { fs.unlinkSync(file); } catch {}
  }
  return registry.unregister(name);
}

module.exports = { loadAllCustom, installFromCode, uninstallCustom };
