/**
 * GitHub MCP 工具集
 * 通过 GitHub REST API v3 实现（axios，无需额外 SDK）
 * Token 从用户配置中读取（加密存储）
 */
const axios = require('axios');
const path  = require('path');
const fs    = require('fs');
const crypto = require('crypto');

const GITHUB_API = 'https://api.github.com';
const CIPHER_SEED = 'rag-dual-ai-github-token-cipher';
const CIPHER_KEY  = crypto.createHash('sha256').update(CIPHER_SEED).digest(); // exactly 32 bytes
const IV_LEN      = 16;
const GITHUB_CFG  = path.resolve(__dirname, '../../data/github-configs.json');

/* ── Token 加解密 ───────────────────────────────────────── */
function encrypt(text) {
  const iv     = crypto.randomBytes(IV_LEN);
  const cipher = crypto.createCipheriv('aes-256-cbc', CIPHER_KEY, iv);
  let enc      = cipher.update(text, 'utf-8', 'hex');
  enc         += cipher.final('hex');
  return iv.toString('hex') + ':' + enc;
}

function decrypt(data) {
  const [ivHex, enc] = data.split(':');
  const decipher     = crypto.createDecipheriv('aes-256-cbc', CIPHER_KEY, Buffer.from(ivHex, 'hex'));
  let dec            = decipher.update(enc, 'hex', 'utf-8');
  dec               += decipher.final('utf-8');
  return dec;
}

/* ── 用户 GitHub 配置读写 ──────────────────────────────── */
function _readCfg() {
  if (!fs.existsSync(GITHUB_CFG)) { fs.writeFileSync(GITHUB_CFG, '{}', 'utf-8'); return {}; }
  try { return JSON.parse(fs.readFileSync(GITHUB_CFG, 'utf-8')); } catch { return {}; }
}

function _writeCfg(data) { fs.writeFileSync(GITHUB_CFG, JSON.stringify(data, null, 2), 'utf-8'); }

function saveGitHubConfig(userId, cfg) {
  const all = _readCfg();
  all[userId] = {
    token:            cfg.token            ? encrypt(cfg.token) : (all[userId]?.token || ''),
    defaultOwner:     cfg.defaultOwner     || all[userId]?.defaultOwner     || '',
    defaultRepo:      cfg.defaultRepo      || all[userId]?.defaultRepo     || '',
    defaultBranch:    cfg.defaultBranch    || all[userId]?.defaultBranch   || 'main',
    defaultUploadDir: cfg.defaultUploadDir ?? all[userId]?.defaultUploadDir ?? '',
    authorName:       cfg.authorName       || all[userId]?.authorName      || '',
    authorEmail:      cfg.authorEmail      || all[userId]?.authorEmail     || '',
    updatedAt:        new Date().toISOString()
  };
  _writeCfg(all);
}

function getGitHubConfig(userId) {
  const all = _readCfg();
  const cfg = all[userId];
  if (!cfg) return null;
  return { ...cfg, hasToken: !!cfg.token, token: undefined };
}

function getDecryptedToken(userId) {
  const all = _readCfg();
  const cfg = all[userId];
  if (!cfg?.token) return null;
  try { return decrypt(cfg.token); } catch { return null; }
}

function clearGitHubConfig(userId) {
  const all = _readCfg();
  delete all[userId];
  _writeCfg(all);
}

/* ── GitHub API 请求辅助 ──────────────────────────────── */
function _gh(method, urlPath, userId, data) {
  const token = getDecryptedToken(userId);
  if (!token) throw new Error('GitHub Token 未配置，请在「GitHub设置」中配置 Personal Access Token');
  return axios({
    method,
    url: `${GITHUB_API}${urlPath}`,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept:        'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28'
    },
    data,
    timeout: 30000
  }).then(r => r.data).catch(e => {
    const msg = e.response?.data?.message || e.message;
    const status = e.response?.status;
    if (status === 401) throw new Error('GitHub Token 无效或已过期');
    if (status === 403) throw new Error(`GitHub 权限不足: ${msg}`);
    if (status === 404) throw new Error('GitHub 资源不存在 (404)');
    throw new Error(`GitHub API 错误: ${msg}`);
  });
}

/* ─── github.search_repos ──────────────────────────────── */
const ghSearchRepos = {
  name: 'github.search_repos',
  description: '搜索 GitHub 仓库（按关键词、语言、星标排序）',
  category: 'github', icon: '🔍', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      query:    { type: 'string', description: '搜索关键词（支持 GitHub 搜索语法）' },
      sort:     { type: 'string', enum: ['stars', 'forks', 'updated'], default: 'stars' },
      order:    { type: 'string', enum: ['desc', 'asc'], default: 'desc' },
      perPage:  { type: 'number', default: 10 },
      userId:   { type: 'string' }
    },
    required: ['query']
  },
  handler: async (input) => {
    const q      = encodeURIComponent(input.query);
    const sort   = input.sort  || 'stars';
    const order  = input.order || 'desc';
    const pp     = Math.min(input.perPage || 10, 30);
    const data   = await _gh('get', `/search/repositories?q=${q}&sort=${sort}&order=${order}&per_page=${pp}`, input.userId);
    return {
      totalCount: data.total_count,
      items: (data.items || []).map(r => ({
        fullName:    r.full_name,
        description: r.description,
        stars:       r.stargazers_count,
        forks:       r.forks_count,
        language:    r.language,
        updatedAt:   r.updated_at,
        url:         r.html_url
      }))
    };
  }
};

/* ─── github.repo_info ─────────────────────────────────── */
const ghRepoInfo = {
  name: 'github.repo_info',
  description: '获取仓库详细信息（星标、语言、描述、贡献者数等）',
  category: 'github', icon: '📊', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      owner:  { type: 'string' },
      repo:   { type: 'string' },
      userId: { type: 'string' }
    },
    required: ['owner', 'repo']
  },
  handler: async (input) => {
    const r = await _gh('get', `/repos/${input.owner}/${input.repo}`, input.userId);
    return {
      fullName:    r.full_name,
      description: r.description,
      stars:       r.stargazers_count,
      forks:       r.forks_count,
      watchers:    r.watchers_count,
      language:    r.language,
      topics:      r.topics,
      license:     r.license?.spdx_id,
      defaultBranch: r.default_branch,
      openIssues:  r.open_issues_count,
      createdAt:   r.created_at,
      updatedAt:   r.updated_at,
      url:         r.html_url
    };
  }
};

/* ─── github.get_file ──────────────────────────────────── */
const ghGetFile = {
  name: 'github.get_file',
  description: '获取仓库中某文件的内容（自动 Base64 解码）',
  category: 'github', icon: '📄', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      owner:  { type: 'string' },
      repo:   { type: 'string' },
      path:   { type: 'string', description: '文件路径（如 src/index.js）' },
      ref:    { type: 'string', description: '分支/tag/SHA', default: 'main' },
      userId: { type: 'string' }
    },
    required: ['owner', 'repo', 'path']
  },
  handler: async (input) => {
    const ref = input.ref ? `?ref=${input.ref}` : '';
    const r   = await _gh('get', `/repos/${input.owner}/${input.repo}/contents/${input.path}${ref}`, input.userId);
    if (r.type !== 'file') throw new Error(`路径 ${input.path} 不是文件（type=${r.type}）`);
    const content = Buffer.from(r.content, 'base64').toString('utf-8');
    return { name: r.name, path: r.path, sha: r.sha, size: r.size, content };
  }
};

/* ─── github.create_file ───────────────────────────────── */
const ghCreateFile = {
  name: 'github.create_file',
  description: '在仓库中创建或更新文件（一键发布内容）',
  category: 'github', icon: '📤', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      owner:   { type: 'string' },
      repo:    { type: 'string' },
      path:    { type: 'string', description: '目标路径' },
      content: { type: 'string', description: '文件内容（自动 Base64 编码）' },
      message: { type: 'string', description: '提交信息' },
      branch:  { type: 'string', default: 'main' },
      sha:     { type: 'string', description: '如果更新已有文件需要传原 SHA' },
      userId:  { type: 'string' }
    },
    required: ['owner', 'repo', 'path', 'content', 'message']
  },
  handler: async (input) => {
    const body = {
      message: input.message,
      content: Buffer.from(input.content, 'utf-8').toString('base64'),
      branch:  input.branch || 'main'
    };
    if (input.sha) body.sha = input.sha;
    const r = await _gh('put', `/repos/${input.owner}/${input.repo}/contents/${input.path}`, input.userId, body);
    return { sha: r.content?.sha, url: r.content?.html_url, message: '文件已发布到 GitHub' };
  }
};

/* ─── github.get_issue ─────────────────────────────────── */
const ghGetIssue = {
  name: 'github.get_issue',
  description: '获取 Issue 详情及评论',
  category: 'github', icon: '🐛', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      owner:  { type: 'string' },
      repo:   { type: 'string' },
      number: { type: 'number' },
      userId: { type: 'string' }
    },
    required: ['owner', 'repo', 'number']
  },
  handler: async (input) => {
    const issue = await _gh('get', `/repos/${input.owner}/${input.repo}/issues/${input.number}`, input.userId);
    let comments = [];
    if (issue.comments > 0) {
      comments = (await _gh('get', `/repos/${input.owner}/${input.repo}/issues/${input.number}/comments?per_page=30`, input.userId))
        .map(c => ({ user: c.user?.login, body: c.body?.slice(0, 500), createdAt: c.created_at }));
    }
    return {
      title:   issue.title,
      state:   issue.state,
      body:    issue.body?.slice(0, 2000),
      author:  issue.user?.login,
      labels:  issue.labels?.map(l => l.name),
      comments,
      url:     issue.html_url
    };
  }
};

/* ─── github.get_pr ────────────────────────────────────── */
const ghGetPR = {
  name: 'github.get_pr',
  description: '获取 Pull Request 详情（含文件变更列表）',
  category: 'github', icon: '🔃', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      owner:  { type: 'string' },
      repo:   { type: 'string' },
      number: { type: 'number' },
      userId: { type: 'string' }
    },
    required: ['owner', 'repo', 'number']
  },
  handler: async (input) => {
    const pr    = await _gh('get', `/repos/${input.owner}/${input.repo}/pulls/${input.number}`, input.userId);
    const files = await _gh('get', `/repos/${input.owner}/${input.repo}/pulls/${input.number}/files?per_page=50`, input.userId);
    return {
      title:       pr.title,
      state:       pr.state,
      body:        pr.body?.slice(0, 2000),
      author:      pr.user?.login,
      base:        pr.base?.ref,
      head:        pr.head?.ref,
      additions:   pr.additions,
      deletions:   pr.deletions,
      changedFiles: pr.changed_files,
      files: files.slice(0, 30).map(f => ({ filename: f.filename, status: f.status, additions: f.additions, deletions: f.deletions })),
      url: pr.html_url
    };
  }
};

/* ─── github.search_code ───────────────────────────────── */
const ghSearchCode = {
  name: 'github.search_code',
  description: '在 GitHub 全站搜索代码片段',
  category: 'github', icon: '💻', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      query:   { type: 'string' },
      perPage: { type: 'number', default: 10 },
      userId:  { type: 'string' }
    },
    required: ['query']
  },
  handler: async (input) => {
    const q    = encodeURIComponent(input.query);
    const pp   = Math.min(input.perPage || 10, 30);
    const data = await _gh('get', `/search/code?q=${q}&per_page=${pp}`, input.userId);
    return {
      totalCount: data.total_count,
      items: (data.items || []).map(i => ({
        name:     i.name,
        path:     i.path,
        repo:     i.repository?.full_name,
        url:      i.html_url,
        score:    i.score
      }))
    };
  }
};

/* ─── github.test_token ────────────────────────────────── */
const ghTestToken = {
  name: 'github.test_token',
  description: '测试 GitHub Token 是否有效（返回用户名和权限范围）',
  category: 'github', icon: '🔑', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: { userId: { type: 'string' } },
    required: ['userId']
  },
  handler: async (input) => {
    const user = await _gh('get', '/user', input.userId);
    return { login: user.login, name: user.name, avatarUrl: user.avatar_url, publicRepos: user.public_repos };
  }
};

/* ─── github.list_repos — 列出当前用户的仓库 ──────────────── */
const ghListRepos = {
  name: 'github.list_repos',
  description: '列出当前 Token 拥有者的仓库（用于选择发布目标）',
  category: 'github', icon: '📁', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      sort:    { type: 'string', enum: ['updated', 'pushed', 'full_name', 'created'], default: 'updated' },
      perPage: { type: 'number', default: 30 },
      userId:  { type: 'string' }
    }
  },
  handler: async (input) => {
    const sort = input.sort || 'updated';
    const pp   = Math.min(input.perPage || 30, 100);
    const data = await _gh('get', `/user/repos?sort=${sort}&per_page=${pp}&affiliation=owner,collaborator`, input.userId);
    return {
      repos: (data || []).map(r => ({
        fullName:      r.full_name,
        name:          r.name,
        owner:         r.owner?.login,
        description:   r.description,
        private:       r.private,
        defaultBranch: r.default_branch,
        language:      r.language,
        updatedAt:     r.updated_at,
        url:           r.html_url
      }))
    };
  }
};

/* ─── github.download_zip — 获取仓库 zip 下载地址 ──────────── */
const ghDownloadZip = {
  name: 'github.download_zip',
  description: '获取仓库的 ZIP 下载链接（可直接下载源码压缩包）',
  category: 'github', icon: '📦', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      owner:  { type: 'string' },
      repo:   { type: 'string' },
      ref:    { type: 'string', default: 'main', description: '分支/tag/SHA' },
      userId: { type: 'string' }
    },
    required: ['owner', 'repo']
  },
  handler: async (input) => {
    const ref = input.ref || 'main';
    // GitHub API 返回 302 到实际的 zip URL
    const zipUrl = `https://github.com/${input.owner}/${input.repo}/archive/refs/heads/${ref}.zip`;
    const apiUrl = `https://api.github.com/repos/${input.owner}/${input.repo}/zipball/${ref}`;
    // 验证仓库存在
    await _gh('get', `/repos/${input.owner}/${input.repo}`, input.userId);
    return {
      zipUrl,
      apiUrl,
      gitCloneUrl: `https://github.com/${input.owner}/${input.repo}.git`,
      message: `ZIP 下载地址已生成。直接打开 zipUrl 即可下载，或使用 git clone ${input.owner}/${input.repo}`
    };
  }
};

/* ─── github.parse_url — 解析 GitHub URL 并预览 ────────────── */
const ghParseUrl = {
  name: 'github.parse_url',
  description: '解析任意 GitHub URL，自动识别类型（仓库/文件/Issue/PR/用户），返回结构化信息',
  category: 'github', icon: '🔗', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      url:    { type: 'string', description: 'GitHub URL（支持仓库、文件、Issue、PR、用户页面）' },
      userId: { type: 'string' }
    },
    required: ['url']
  },
  handler: async (input) => {
    const url = String(input.url || '').trim().replace(/\/$/, '');

    // 解析不同类型的 GitHub URL
    let match;

    // 文件: github.com/owner/repo/blob/branch/path
    match = url.match(/github\.com\/([^/]+)\/([^/]+)\/blob\/([^/]+)\/(.+)/);
    if (match) {
      const [, owner, repo, ref, filePath] = match;
      const fileData = await _gh('get', `/repos/${owner}/${repo}/contents/${filePath}?ref=${ref}`, input.userId);
      const content = fileData.type === 'file' ? Buffer.from(fileData.content, 'base64').toString('utf-8') : null;
      return {
        type: 'file', owner, repo, ref, path: filePath,
        name: fileData.name, size: fileData.size, sha: fileData.sha,
        content: content?.slice(0, 5000),
        contentTruncated: content && content.length > 5000,
        downloadUrl: fileData.download_url,
        url: fileData.html_url
      };
    }

    // Issue: github.com/owner/repo/issues/number
    match = url.match(/github\.com\/([^/]+)\/([^/]+)\/issues\/(\d+)/);
    if (match) {
      const [, owner, repo, num] = match;
      const issue = await _gh('get', `/repos/${owner}/${repo}/issues/${num}`, input.userId);
      return {
        type: 'issue', owner, repo, number: parseInt(num),
        title: issue.title, state: issue.state,
        author: issue.user?.login,
        body: issue.body?.slice(0, 2000),
        labels: issue.labels?.map(l => l.name),
        comments: issue.comments,
        url: issue.html_url
      };
    }

    // PR: github.com/owner/repo/pull/number
    match = url.match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
    if (match) {
      const [, owner, repo, num] = match;
      const pr = await _gh('get', `/repos/${owner}/${repo}/pulls/${num}`, input.userId);
      return {
        type: 'pr', owner, repo, number: parseInt(num),
        title: pr.title, state: pr.state,
        author: pr.user?.login,
        body: pr.body?.slice(0, 2000),
        base: pr.base?.ref, head: pr.head?.ref,
        additions: pr.additions, deletions: pr.deletions,
        changedFiles: pr.changed_files,
        url: pr.html_url
      };
    }

    // 目录: github.com/owner/repo/tree/branch/path
    match = url.match(/github\.com\/([^/]+)\/([^/]+)\/tree\/([^/]+)(?:\/(.+))?/);
    if (match) {
      const [, owner, repo, ref, dirPath] = match;
      const apiPath = dirPath ? `/repos/${owner}/${repo}/contents/${dirPath}?ref=${ref}` : `/repos/${owner}/${repo}/contents?ref=${ref}`;
      const items = await _gh('get', apiPath, input.userId);
      return {
        type: 'directory', owner, repo, ref, path: dirPath || '/',
        items: (Array.isArray(items) ? items : []).map(i => ({
          name: i.name, type: i.type, size: i.size, path: i.path
        })),
        url
      };
    }

    // 仓库: github.com/owner/repo
    match = url.match(/github\.com\/([^/]+)\/([^/]+?)(?:\.git)?$/);
    if (match) {
      const [, owner, repo] = match;
      const r = await _gh('get', `/repos/${owner}/${repo}`, input.userId);
      return {
        type: 'repo', owner, repo,
        fullName: r.full_name, description: r.description,
        stars: r.stargazers_count, forks: r.forks_count,
        language: r.language, topics: r.topics,
        defaultBranch: r.default_branch,
        license: r.license?.spdx_id,
        zipUrl: `https://github.com/${owner}/${repo}/archive/refs/heads/${r.default_branch}.zip`,
        gitCloneUrl: `https://github.com/${owner}/${repo}.git`,
        url: r.html_url
      };
    }

    // 用户: github.com/username
    match = url.match(/github\.com\/([^/]+)$/);
    if (match) {
      const [, username] = match;
      const u = await _gh('get', `/users/${username}`, input.userId);
      return {
        type: 'user', login: u.login, name: u.name,
        bio: u.bio, publicRepos: u.public_repos,
        followers: u.followers, following: u.following,
        avatarUrl: u.avatar_url, url: u.html_url
      };
    }

    throw new Error('无法解析此 URL，请输入有效的 GitHub 链接');
  }
};

/* ─── github.get_config — 获取当前用户的 GitHub 默认配置 ───── */
const ghGetConfig = {
  name: 'github.get_config',
  description: '获取当前用户的 GitHub 默认配置（仓库/分支/上传目录）',
  category: 'github', icon: '⚙️', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: { userId: { type: 'string' } }
  },
  handler: async (input) => {
    const cfg = getGitHubConfig(input.userId);
    if (!cfg) return { configured: false, message: '未配置 GitHub 账号' };
    return {
      configured: true,
      hasToken:       cfg.hasToken,
      defaultOwner:   cfg.defaultOwner,
      defaultRepo:    cfg.defaultRepo,
      defaultBranch:  cfg.defaultBranch,
      defaultUploadDir: cfg.defaultUploadDir || '',
      authorName:     cfg.authorName,
      authorEmail:    cfg.authorEmail
    };
  }
};

module.exports = {
  ALL_GITHUB_TOOLS: [
    ghSearchRepos, ghRepoInfo, ghGetFile, ghCreateFile,
    ghGetIssue, ghGetPR, ghSearchCode, ghTestToken,
    ghListRepos, ghDownloadZip, ghParseUrl, ghGetConfig
  ],
  // 供路由直接调用的辅助函数
  saveGitHubConfig, getGitHubConfig, getDecryptedToken, clearGitHubConfig,
  encrypt, decrypt
};
