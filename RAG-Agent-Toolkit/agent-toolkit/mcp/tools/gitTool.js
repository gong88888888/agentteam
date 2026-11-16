/**
 * Git MCP 工具集
 * 通过 child_process 调用本地 git 命令
 * 所有操作限制在 backend/exports/git-repos/ 沙箱目录内
 */
const { execFile } = require('child_process');
const path = require('path');
const fs   = require('fs');

const GIT_SANDBOX = path.resolve(__dirname, '../../exports/git-repos');
if (!fs.existsSync(GIT_SANDBOX)) fs.mkdirSync(GIT_SANDBOX, { recursive: true });

function _run(args, cwd = GIT_SANDBOX) {
  return new Promise((resolve, reject) => {
    execFile('git', args, { cwd, timeout: 30000, maxBuffer: 2 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(stderr?.trim() || err.message));
      resolve((stdout || '').trim());
    });
  });
}

function _safePath(p) {
  const abs = path.resolve(GIT_SANDBOX, p || '');
  if (!abs.startsWith(GIT_SANDBOX)) throw new Error('路径越权：只能操作 git-repos/ 下的仓库');
  return abs;
}

/* ─── git.init ──────────────────────────────────────────── */
const gitInit = {
  name: 'git.init',
  description: '在沙箱目录下初始化一个新的 Git 仓库',
  category: 'git', icon: '📦', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string', description: '仓库文件夹名' },
      defaultBranch: { type: 'string', default: 'main' }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir = _safePath(input.repoName);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    await _run(['-c', `init.defaultBranch=${input.defaultBranch || 'main'}`, 'init'], dir);
    return { path: dir, message: `仓库 ${input.repoName} 已初始化` };
  }
};

/* ─── git.clone ─────────────────────────────────────────── */
const gitClone = {
  name: 'git.clone',
  description: '克隆远程仓库到沙箱目录',
  category: 'git', icon: '📥', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      url:      { type: 'string', description: 'Git 仓库 URL' },
      dirName:  { type: 'string', description: '目标文件夹名' },
      depth:    { type: 'number', default: 1, description: '浅克隆深度' }
    },
    required: ['url']
  },
  handler: async (input) => {
    const name = input.dirName || input.url.split('/').pop().replace(/\.git$/, '');
    const dir  = _safePath(name);
    const args = ['clone', '--depth', String(input.depth || 1), input.url, dir];
    await _run(args, GIT_SANDBOX);
    return { path: dir, message: `仓库已克隆到 ${name}` };
  }
};

/* ─── git.status ────────────────────────────────────────── */
const gitStatus = {
  name: 'git.status',
  description: '获取仓库当前状态（工作区变更、暂存区状态）',
  category: 'git', icon: '📋', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: { repoName: { type: 'string' } },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir = _safePath(input.repoName);
    const status = await _run(['status', '--porcelain'], dir);
    const branch = await _run(['branch', '--show-current'], dir).catch(() => 'HEAD detached');
    return { branch, status: status || '(clean)', lines: status ? status.split('\n') : [] };
  }
};

/* ─── git.add ───────────────────────────────────────────── */
const gitAdd = {
  name: 'git.add',
  description: '暂存文件到 Git 索引（支持通配符或 "."）',
  category: 'git', icon: '➕', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      files:    { type: 'array', items: { type: 'string' }, description: '文件路径列表，传 ["."] 表示全部' }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir   = _safePath(input.repoName);
    const files = input.files?.length ? input.files : ['.'];
    await _run(['add', ...files], dir);
    return { message: `已暂存: ${files.join(', ')}` };
  }
};

/* ─── git.commit ────────────────────────────────────────── */
const gitCommit = {
  name: 'git.commit',
  description: '提交暂存区到本地仓库',
  category: 'git', icon: '💾', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      message:  { type: 'string', description: '提交信息' },
      author:   { type: 'string', description: '作者（name <email>）' }
    },
    required: ['repoName', 'message']
  },
  handler: async (input) => {
    const dir  = _safePath(input.repoName);
    const args = ['commit', '-m', input.message];
    if (input.author) args.push('--author', input.author);
    const out = await _run(args, dir);
    return { message: out };
  }
};

/* ─── git.push ──────────────────────────────────────────── */
const gitPush = {
  name: 'git.push',
  description: '推送本地提交到远程仓库',
  category: 'git', icon: '🚀', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      remote:   { type: 'string', default: 'origin' },
      branch:   { type: 'string', default: 'main' },
      setUpstream: { type: 'boolean', default: false }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir  = _safePath(input.repoName);
    const args = ['push', input.remote || 'origin', input.branch || 'main'];
    if (input.setUpstream) args.splice(1, 0, '-u');
    const out = await _run(args, dir);
    return { message: out || '推送成功' };
  }
};

/* ─── git.log ───────────────────────────────────────────── */
const gitLog = {
  name: 'git.log',
  description: '获取提交历史',
  category: 'git', icon: '📜', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      maxCount: { type: 'number', default: 20 },
      oneline:  { type: 'boolean', default: true }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir  = _safePath(input.repoName);
    const fmt  = input.oneline !== false ? ['--oneline'] : ['--format=%H|%an|%s|%ci'];
    const out  = await _run(['log', ...fmt, `-${input.maxCount || 20}`], dir);
    return { commits: out ? out.split('\n') : [] };
  }
};

/* ─── git.diff ──────────────────────────────────────────── */
const gitDiff = {
  name: 'git.diff',
  description: '查看工作区或暂存区的文件差异',
  category: 'git', icon: '🔀', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      staged:   { type: 'boolean', default: false },
      file:     { type: 'string', description: '限定某文件' }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir  = _safePath(input.repoName);
    const args = ['diff'];
    if (input.staged) args.push('--cached');
    if (input.file)   args.push('--', input.file);
    const out = await _run(args, dir);
    return { diff: out || '(no diff)' };
  }
};

/* ─── git.branch ────────────────────────────────────────── */
const gitBranch = {
  name: 'git.branch',
  description: '分支管理：列出 / 创建 / 切换 / 删除分支',
  category: 'git', icon: '🌿', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      action:   { type: 'string', enum: ['list', 'create', 'checkout', 'delete'], default: 'list' },
      name:     { type: 'string', description: '分支名（create/checkout/delete 必填）' }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir = _safePath(input.repoName);
    const act = input.action || 'list';
    if (act === 'list') {
      const out = await _run(['branch', '-a'], dir);
      return { branches: out ? out.split('\n').map(b => b.trim()) : [] };
    }
    if (!input.name) throw new Error('分支名不能为空');
    if (act === 'create')   { await _run(['branch', input.name], dir); return { message: `分支 ${input.name} 已创建` }; }
    if (act === 'checkout') { await _run(['checkout', input.name], dir); return { message: `已切换到 ${input.name}` }; }
    if (act === 'delete')   { await _run(['branch', '-d', input.name], dir); return { message: `分支 ${input.name} 已删除` }; }
    throw new Error(`不支持的动作: ${act}`);
  }
};

/* ─── git.remote ────────────────────────────────────────── */
const gitRemote = {
  name: 'git.remote',
  description: '远程仓库管理：列出 / 添加 / 删除远程',
  category: 'git', icon: '🌐', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      action:   { type: 'string', enum: ['list', 'add', 'remove'], default: 'list' },
      name:     { type: 'string', description: '远程名' },
      url:      { type: 'string', description: '远程 URL（add 时）' }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir = _safePath(input.repoName);
    const act = input.action || 'list';
    if (act === 'list') {
      const out = await _run(['remote', '-v'], dir);
      return { remotes: out || '(none)' };
    }
    if (!input.name) throw new Error('远程名不能为空');
    if (act === 'add') {
      if (!input.url) throw new Error('add 需提供 url');
      await _run(['remote', 'add', input.name, input.url], dir);
      return { message: `远程 ${input.name} 已添加` };
    }
    if (act === 'remove') {
      await _run(['remote', 'remove', input.name], dir);
      return { message: `远程 ${input.name} 已移除` };
    }
    throw new Error(`不支持的动作: ${act}`);
  }
};

/* ─── git.tag ───────────────────────────────────────────── */
const gitTag = {
  name: 'git.tag',
  description: '标签管理：列出 / 创建 / 删除标签',
  category: 'git', icon: '🏷️', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      repoName: { type: 'string' },
      action:   { type: 'string', enum: ['list', 'create', 'delete'], default: 'list' },
      name:     { type: 'string' },
      message:  { type: 'string' }
    },
    required: ['repoName']
  },
  handler: async (input) => {
    const dir = _safePath(input.repoName);
    const act = input.action || 'list';
    if (act === 'list') {
      const out = await _run(['tag', '-l'], dir);
      return { tags: out ? out.split('\n') : [] };
    }
    if (!input.name) throw new Error('标签名不能为空');
    if (act === 'create') {
      const args = input.message ? ['tag', '-a', input.name, '-m', input.message] : ['tag', input.name];
      await _run(args, dir);
      return { message: `标签 ${input.name} 已创建` };
    }
    if (act === 'delete') {
      await _run(['tag', '-d', input.name], dir);
      return { message: `标签 ${input.name} 已删除` };
    }
    throw new Error(`不支持的动作: ${act}`);
  }
};

module.exports = {
  ALL_GIT_TOOLS: [
    gitInit, gitClone, gitStatus, gitAdd, gitCommit,
    gitPush, gitLog, gitDiff, gitBranch, gitRemote, gitTag
  ]
};
