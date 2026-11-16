/**
 * OfficeCLI MCP 工具集
 * 通过 child_process 调用 officecli 二进制（需预装）
 * 能力：创建/查看/修改 Word/Excel/PPT 文件，模板合并，批量操作
 *
 * 参考：https://github.com/iOfficeAI/OfficeCLI
 * 安装：curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash
 *       或 PowerShell: iex (irm https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1)
 */
const { execFile } = require('child_process');
const path = require('path');
const fs   = require('fs');

const OFFICE_SANDBOX = path.resolve(__dirname, '../../exports/office');
if (!fs.existsSync(OFFICE_SANDBOX)) fs.mkdirSync(OFFICE_SANDBOX, { recursive: true });

let _cliAvailable = null;

function _checkCli() {
  if (_cliAvailable !== null) return _cliAvailable;
  try {
    require('child_process').execFileSync('officecli', ['--version'], { timeout: 5000, stdio: 'pipe' });
    _cliAvailable = true;
  } catch {
    _cliAvailable = false;
  }
  return _cliAvailable;
}

function _run(args, cwd = OFFICE_SANDBOX) {
  if (!_checkCli()) {
    throw new Error(
      'officecli 未安装。安装方法：\n' +
      '  Windows: iex (irm https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1)\n' +
      '  macOS/Linux: curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash'
    );
  }
  return new Promise((resolve, reject) => {
    execFile('officecli', [...args, '--json'], { cwd, timeout: 30000, maxBuffer: 4 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr?.trim() || err.message));
      try {
        resolve(JSON.parse(stdout));
      } catch {
        resolve({ raw: stdout.trim() });
      }
    });
  });
}

function _safePath(filename) {
  const raw = String(filename || '').trim();
  const abs = path.isAbsolute(raw)
    ? path.resolve(raw)
    : path.resolve(OFFICE_SANDBOX, _stripOfficePrefix(raw));
  const rel = path.relative(OFFICE_SANDBOX, abs);
  if (rel.startsWith('..') || path.isAbsolute(rel)) {
    throw new Error('路径越权：仅允许操作 exports/office/ 下的文件');
  }
  return abs;
}

function _stripOfficePrefix(filename) {
  let normalized = String(filename || '').replace(/\\/g, '/').replace(/^\.?\//, '');
  for (const prefix of ['backend/exports/office/', 'exports/office/']) {
    if (normalized.toLowerCase().startsWith(prefix)) {
      normalized = normalized.slice(prefix.length);
      break;
    }
  }
  return normalized;
}

/* ─── office.create — 创建空白文档 ──────────────────────── */
const officeCreate = {
  name: 'office.create',
  description: '创建空白 Office 文档（.docx / .xlsx / .pptx）',
  category: 'office', icon: '📎', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      filename: { type: 'string', description: '文件名（如 report.docx / data.xlsx / deck.pptx）' }
    },
    required: ['filename']
  },
  handler: async (input) => {
    const fp = _safePath(input.filename);
    const result = await _run(['create', fp]);
    return { ...result, path: fp, message: `已创建 ${input.filename}` };
  }
};

/* ─── office.view — 查看文档内容 ────────────────────────── */
const officeView = {
  name: 'office.view',
  description: '查看 Office 文档内容（大纲/文本/HTML）',
  category: 'office', icon: '👀', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      filename: { type: 'string' },
      format:   { type: 'string', enum: ['outline', 'text', 'html'], default: 'outline' }
    },
    required: ['filename']
  },
  handler: async (input) => {
    const fp = _safePath(input.filename);
    if (!fs.existsSync(fp)) throw new Error('文件不存在');
    return _run(['view', fp, '--format', input.format || 'outline']);
  }
};

/* ─── office.add — 添加元素 ─────────────────────────────── */
const officeAdd = {
  name: 'office.add',
  description: '向 Office 文档添加元素（段落/幻灯片/工作表等）',
  category: 'office', icon: '➕', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      filename: { type: 'string' },
      selector: { type: 'string', default: '/', description: 'CSS 选择器路径' },
      type:     { type: 'string', description: '元素类型（heading/paragraph/slide/row/cell 等）' },
      props:    { type: 'object', description: '属性（如 text/title/value 等）' }
    },
    required: ['filename', 'type']
  },
  handler: async (input) => {
    const fp   = _safePath(input.filename);
    const args = ['add', fp, input.selector || '/', '--type', input.type];
    if (input.props) {
      for (const [k, v] of Object.entries(input.props)) {
        args.push('--prop', `${k}=${v}`);
      }
    }
    return _run(args);
  }
};

/* ─── office.set — 修改属性 ─────────────────────────────── */
const officeSet = {
  name: 'office.set',
  description: '修改 Office 文档中元素的属性',
  category: 'office', icon: '✏️', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      filename: { type: 'string' },
      selector: { type: 'string', description: '元素选择器' },
      props:    { type: 'object', description: '要设置的属性键值对' }
    },
    required: ['filename', 'selector', 'props']
  },
  handler: async (input) => {
    const fp   = _safePath(input.filename);
    const args = ['set', fp, input.selector];
    for (const [k, v] of Object.entries(input.props || {})) {
      args.push('--prop', `${k}=${v}`);
    }
    return _run(args);
  }
};

/* ─── office.merge — 模板合并 ───────────────────────────── */
const officeMerge = {
  name: 'office.merge',
  description: '模板合并：将 {{key}} 占位符替换为实际数据',
  category: 'office', icon: '🔗', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      filename: { type: 'string', description: '模板文件路径' },
      data:     { type: 'object', description: '替换数据 {key: value}' },
      output:   { type: 'string', description: '输出文件名（可选）' }
    },
    required: ['filename', 'data']
  },
  handler: async (input) => {
    const fp   = _safePath(input.filename);
    const outFp = input.output ? _safePath(input.output) : null;
    const args = ['merge', fp];
    for (const [k, v] of Object.entries(input.data || {})) {
      args.push('--data', `${k}=${v}`);
    }
    if (outFp) args.push('--output', outFp);
    return _run(args);
  }
};

/* ─── office.batch — 批量操作 ───────────────────────────── */
const officeBatch = {
  name: 'office.batch',
  description: '批量执行多个 Office 操作（原子性）',
  category: 'office', icon: '⚡', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      filename:   { type: 'string' },
      operations: { type: 'array', items: { type: 'object' }, description: '操作列表 [{action, selector, type?, props?}]' }
    },
    required: ['filename', 'operations']
  },
  handler: async (input) => {
    const fp = _safePath(input.filename);
    const ops = input.operations || [];
    const results = [];
    for (const op of ops) {
      const args = [op.action || 'add', fp, op.selector || '/'];
      if (op.type) args.push('--type', op.type);
      if (op.props) {
        for (const [k, v] of Object.entries(op.props)) {
          args.push('--prop', `${k}=${v}`);
        }
      }
      results.push(await _run(args));
    }
    return { results, count: results.length };
  }
};

/* ─── office.info — 检测安装状态 ────────────────────────── */
const officeInfo = {
  name: 'office.info',
  description: '检测 OfficeCLI 安装状态和版本',
  category: 'office', icon: 'ℹ️', source: 'builtin',
  inputSchema: { type: 'object', properties: {} },
  handler: async () => {
    const available = _checkCli();
    if (!available) {
      return {
        installed: false,
        message: 'OfficeCLI 未安装',
        installGuide: {
          windows: 'iex (irm https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1)',
          unix: 'curl -fsSL https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.sh | bash'
        }
      };
    }
    try {
      const ver = require('child_process').execFileSync('officecli', ['--version'], { timeout: 5000, encoding: 'utf-8' }).trim();
      return { installed: true, version: ver, sandboxDir: OFFICE_SANDBOX };
    } catch {
      return { installed: true, version: 'unknown', sandboxDir: OFFICE_SANDBOX };
    }
  }
};

module.exports = {
  ALL_OFFICE_TOOLS: [
    officeCreate, officeView, officeAdd, officeSet,
    officeMerge, officeBatch, officeInfo
  ]
};
