/**
 * Harness 入口
 * 挂载路由、承接 MCP 工具、定期清理日志
 */
const harnessLogger    = require('./logger');
const controller       = require('./controller');

function initHarness(app, options = {}) {
  const loadLegacyTools = options.loadLegacyTools
    ?? process.env.ENABLE_LEGACY_HARNESS_TOOLS === '1';

  if (loadLegacyTools) {
    require('./toolLoader').loadAllTools();
  }
  // 旧版 Harness 工具仅在显式兼容模式下加载；当前工具由 MCP bridge 注入。

  // 2. 挂载 Harness REST API（无鉴权，供内部/外部调用）
  const router = require('express').Router();

  // POST /api/harness/submit  — 提交任务
  router.post('/submit', async (req, res) => {
    try {
      const result = await controller.submitTask(req.body);
      res.json({ success: true, ...result });
    } catch (e) {
      res.status(400).json({ success: false, message: e.message });
    }
  });

  // GET  /api/harness/task/:id  — 查询任务状态
  router.get('/task/:id', (req, res) => {
    const task = controller.getTask(req.params.id);
    if (!task) return res.status(404).json({ success: false, message: '任务不存在' });
    res.json({ success: true, task: _safeTask(task) });
  });

  // GET  /api/harness/tasks  — 查询所有任务（含过滤）
  router.get('/tasks', (req, res) => {
    const { status } = req.query;
    let tasks = controller.getAllTasks();
    if (status) tasks = tasks.filter(t => t.status === status);
    res.json({ success: true, tasks: tasks.map(_safeTask) });
  });

  // POST /api/harness/cancel/:id  — 取消任务
  router.post('/cancel/:id', (req, res) => {
    const ok = controller.cancelTask(req.params.id);
    res.json({ success: ok, message: ok ? '已取消' : '任务不存在或已结束' });
  });

  // GET  /api/harness/logs/:id  — 查询任务磁盘日志
  router.get('/logs/:id', (req, res) => {
    const logs = harnessLogger.getTaskLogs(req.params.id);
    res.json({ success: true, logs });
  });

  // GET  /api/harness/tools  — 列出已注册工具
  router.get('/tools', (req, res) => {
    const tools = [...controller.tools.entries()].map(([name, t]) => ({
      name,
      description: t.description || ''
    }));
    res.json({ success: true, tools });
  });

  app.use('/api/harness', router);
  console.log('[Harness] ✅ API 已挂载到 /api/harness');

  // 3. 每天凌晨清理 7 天前的日志
  setInterval(() => harnessLogger.cleanup(7), 24 * 60 * 60 * 1000);

  return controller;
}

/** 去掉内部字段后返回安全的任务对象 */
function _safeTask(task) {
  const { _cancelled, ...safe } = task;
  return safe;
}

module.exports = { initHarness, controller };
