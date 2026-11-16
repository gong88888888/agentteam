/**
 * Harness 核心控制器
 * - 工具注册 / 验证器注册
 * - 任务提交 / 异步执行
 * - 自动重试（每步最多 3 次）
 * - 完整执行日志（内存 + 磁盘）
 */
const harnessLogger = require('./logger');
const validator     = require('./validator');

class HarnessController {
  constructor() {
    this.tasks      = new Map();
    this.tools      = new Map();
    this.MAX_TASKS  = 500;
  }

  /* ── 工具 / 验证器注册 ─────────────────────────────────── */
  registerTool(name, tool) {
    this.tools.set(name, tool);
    console.log(`[Harness] ✅ 注册工具: ${name}`);
  }

  hasTool(name) { return this.tools.has(name); }

  /* ── 提交任务 ───────────────────────────────────────────── */
  async submitTask(task) {
    if (this.tasks.size >= this.MAX_TASKS) this._evictOldTasks();

    const taskId = `h_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
    const record = {
      id:          taskId,
      status:      'pending',
      progress:    0,
      steps:       (task.steps || []).map(s => ({ ...s, output: null })),
      currentStep: 0,
      result:      null,
      error:       null,
      logs:        [],         // 内存日志（快速读取）
      meta:        task.meta || {},
      createdAt:   new Date()
    };

    this.tasks.set(taskId, record);
    this._log(taskId, 'info', `任务已提交，共 ${record.steps.length} 步`);

    // 异步执行，不阻塞当前调用
    setImmediate(() => this._executeTask(taskId));

    return { taskId };
  }

  /* ── 查询 ───────────────────────────────────────────────── */
  getTask(taskId) {
    return this.tasks.get(taskId) || null;
  }

  getAllTasks() {
    return [...this.tasks.values()];
  }

  /* ── 取消任务 ───────────────────────────────────────────── */
  cancelTask(taskId) {
    const task = this.tasks.get(taskId);
    if (!task) return false;
    if (['pending', 'running'].includes(task.status)) {
      task._cancelled = true;
      task.status     = 'cancelled';
      this._log(taskId, 'warn', '任务已取消');
    }
    return true;
  }

  /* ── 内部：执行任务 ─────────────────────────────────────── */
  async _executeTask(taskId) {
    const task = this.tasks.get(taskId);
    if (!task || task.status === 'cancelled') return;

    task.status    = 'running';
    task.startedAt = new Date();
    this._log(taskId, 'info', '任务开始执行');

    try {
      for (let i = 0; i < task.steps.length; i++) {
        if (task._cancelled) return;

        task.currentStep = i;
        const step       = task.steps[i];
        const maxRetries = step.maxRetries ?? 3;

        this._log(taskId, 'info', `▶ 步骤 ${i + 1}/${task.steps.length}: ${step.name}`);

        let lastErr;
        for (let attempt = 1; attempt <= maxRetries; attempt++) {
          if (task._cancelled) return;

          try {
            const tool = this.tools.get(step.tool);
            if (!tool) throw new Error(`工具 "${step.tool}" 未注册`);

            // 将上一步输出注入当前步骤 input（支持 $prev 引用）
            const input = this._resolveInput(step.input, task.steps, i);

            const result = await tool.execute(input);

            // 输出验证
            if (step.validator) {
              const v = validator.validate(step.validator, result);
              if (!v.valid) throw new Error(`验证失败: ${v.message}`);
            }

            step.output = result;
            this._log(taskId, 'success', `✓ 步骤 ${i + 1} 完成（第 ${attempt} 次）`);
            lastErr = null;
            break;

          } catch (err) {
            lastErr = err;
            if (attempt < maxRetries) {
              this._log(taskId, 'warn', `步骤 ${i + 1} 第 ${attempt} 次失败，${attempt}s 后重试: ${err.message}`);
              await this._sleep(attempt * 1000);
            }
          }
        }

        if (lastErr) throw lastErr;

        task.progress = Math.round(((i + 1) / task.steps.length) * 100);
      }

      task.status      = 'completed';
      task.progress    = 100;
      task.completedAt = new Date();
      task.result      = task.steps[task.steps.length - 1]?.output ?? null;
      this._log(taskId, 'success', '🎉 任务全部步骤执行完成');

    } catch (err) {
      task.status      = 'failed';
      task.error       = err.message;
      task.completedAt = new Date();
      this._log(taskId, 'error', `❌ 任务失败: ${err.message}`);
    }
  }

  /* ── 辅助：解析步骤输入中的 $prev 引用 ──────────────────── */
  _resolveInput(rawInput, steps, currentIdx) {
    if (!rawInput || typeof rawInput !== 'object') return rawInput;

    const resolved = { ...rawInput };
    for (const [key, val] of Object.entries(resolved)) {
      if (val === '$prev' && currentIdx > 0) {
        resolved[key] = steps[currentIdx - 1]?.output ?? null;
      } else if (typeof val === 'string' && val.startsWith('$step.')) {
        // $step.0.output 格式
        const parts = val.split('.');
        const idx   = parseInt(parts[1]);
        const field = parts[2] || 'output';
        if (!isNaN(idx) && steps[idx]) {
          resolved[key] = steps[idx][field] ?? null;
        }
      }
    }
    return resolved;
  }

  /* ── 辅助：写日志 ───────────────────────────────────────── */
  _log(taskId, level, message) {
    const task = this.tasks.get(taskId);
    const entry = { level, message, timestamp: new Date() };
    if (task) task.logs.push(entry);
    harnessLogger.write(taskId, level, message);
  }

  /* ── 辅助：淘汰旧任务（保留最近 400 条） ──────────────────── */
  _evictOldTasks() {
    const finished = [...this.tasks.entries()]
      .filter(([, t]) => ['completed', 'failed', 'cancelled'].includes(t.status))
      .sort(([, a], [, b]) => a.createdAt - b.createdAt);
    for (const [id] of finished.slice(0, 100)) this.tasks.delete(id);
  }

  _sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
}

module.exports = new HarnessController();
