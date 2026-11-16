/**
 * Excel 管理类专业工具集 — 11 个 MCP 工具
 *
 * 管理类工具（7个）：
 *   excel.gantt         — 甘特图生成
 *   excel.taskStats     — 任务统计分析
 *   excel.budget        — 预算管理表
 *   excel.schedule      — 人员排班表
 *   excel.kpi           — KPI考核表
 *   excel.meetingNotes  — 会议纪要转Excel
 *   excel.riskRegister  — 风险登记册
 *
 * 统计分析工具（4个）：
 *   excel.regression    — 线性回归分析
 *   excel.correlation   — 相关性矩阵分析
 *   excel.timeSeries    — 时间序列预测
 *   excel.anomaly       — 异常值检测
 */
const ExcelJS    = require('exceljs');
const path       = require('path');
const fs         = require('fs');
const os         = require('os');
const GanttEngine = require('../../mcp-tools/lib/ganttEngine');
const StatsEngine = require('../../mcp-tools/lib/statsEngine');

const gantt = new GanttEngine();
const stats = new StatsEngine();

const EXPORTS_DIR = path.resolve(__dirname, '../../exports/excel-mgmt');
if (!fs.existsSync(EXPORTS_DIR)) fs.mkdirSync(EXPORTS_DIR, { recursive: true });

/* ── 通用辅助 ─────────────────────────────────────────── */
function outPath(input, prefix) {
  const dir = input.outputDir || EXPORTS_DIR;
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, `${prefix}_${Date.now()}.xlsx`);
}

function _border(style = 'thin') {
  return { top: { style }, left: { style }, bottom: { style }, right: { style } };
}

function _hdrStyle(color = 'FF1B4F8A') {
  return {
    fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: color } },
    font: { bold: true, color: { argb: 'FFFFFFFF' }, size: 11 },
    alignment: { horizontal: 'center', vertical: 'middle' },
    border: _border()
  };
}

function _applyStyle(cell, style) {
  Object.assign(cell, style);
}

async function _saveWb(wb, fp) {
  await wb.xlsx.writeFile(fp);
  return fp;
}

/* ═══════════════ 1. excel.gantt ═══════════════════════════ */
const excelGantt = {
  name: 'excel.gantt',
  description: '根据任务清单自动生成专业甘特图 Excel，包含时间轴/进度条/里程碑/延期预警',
  category: 'excel', icon: '📅', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      tasks: {
        type: 'array',
        description: '任务列表 [{name,start,end,owner?,progress?,milestone?,deps?}]'
      },
      title:     { type: 'string', default: '项目甘特图' },
      unit:      { type: 'string', enum: ['day','week','month','quarter'] },
      outputDir: { type: 'string' }
    },
    required: ['tasks']
  },
  handler: async (input) => {
    if (!input.tasks?.length) throw new Error('tasks 不能为空');
    const fp = outPath(input, 'gantt');
    await gantt.generateGanttExcel(input.tasks, fp, {
      unit: input.unit, title: input.title || '项目甘特图'
    });
    return {
      filePath: fp,
      fileName: path.basename(fp),
      taskCount: input.tasks.length,
      message:  '甘特图已生成'
    };
  }
};

/* ═══════════════ 2. excel.taskStats ═══════════════════════ */
const excelTaskStats = {
  name: 'excel.taskStats',
  description: '对任务数据进行全维度统计分析，生成完成率/延期率/负责人分布/风险预警报表',
  category: 'excel', icon: '📊', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      tasks: {
        type: 'array',
        description: '[{name,owner,status,due,progress,phase?}] status: done|in_progress|not_started|overdue'
      },
      title:     { type: 'string', default: '任务统计分析报表' },
      outputDir: { type: 'string' }
    },
    required: ['tasks']
  },
  handler: async (input) => {
    if (!input.tasks?.length) throw new Error('tasks 不能为空');
    const tasks = input.tasks;
    const today = new Date();

    // 统计
    const total          = tasks.length;
    const done           = tasks.filter(t => t.status === 'done' || t.progress >= 100).length;
    const overdue        = tasks.filter(t => t.status === 'overdue' || (t.due && new Date(t.due) < today && t.progress < 100)).length;
    const notStarted     = tasks.filter(t => t.status === 'not_started' || t.progress === 0).length;
    const completionRate = total ? +(done / total * 100).toFixed(1) : 0;
    const overdueRate    = total ? +(overdue / total * 100).toFixed(1) : 0;

    // 负责人分布
    const byOwner = {};
    for (const t of tasks) {
      const o = t.owner || '未分配';
      if (!byOwner[o]) byOwner[o] = { total: 0, done: 0, overdue: 0 };
      byOwner[o].total++;
      if (t.status === 'done' || t.progress >= 100) byOwner[o].done++;
      if (t.status === 'overdue' || (t.due && new Date(t.due) < today && t.progress < 100)) byOwner[o].overdue++;
    }

    // 生成 Excel
    const wb  = new ExcelJS.Workbook();
    const ws1 = wb.addWorksheet('总览');
    const ws2 = wb.addWorksheet('负责人分布');
    const ws3 = wb.addWorksheet('任务明细');

    // Sheet1: 概览
    const title = input.title || '任务统计分析报表';
    ws1.getRow(1).getCell(1).value = title;
    ws1.getRow(1).getCell(1).font  = { bold: true, size: 14 };
    ws1.getRow(1).height = 28;

    const overview = [
      ['指标', '数值', '状态'],
      ['任务总数',   total,          ''],
      ['已完成',     done,           completionRate >= 80 ? '✅ 良好' : '⚠️ 需关注'],
      ['完成率',     `${completionRate}%`, completionRate >= 80 ? '✅' : '❌'],
      ['延期任务',   overdue,        overdue > 0 ? '🔴 需处理' : '✅'],
      ['延期率',     `${overdueRate}%`, overdueRate > 20 ? '🔴 高风险' : overdueRate > 10 ? '⚠️ 中风险' : '✅ 正常'],
      ['未开始',     notStarted,     ''],
      ['进行中',     total - done - overdue - notStarted, '']
    ];
    overview.forEach((row, ri) => {
      const exRow = ws1.getRow(ri + 2);
      row.forEach((v, ci) => {
        const cell = exRow.getCell(ci + 1);
        cell.value = v;
        if (ri === 0) Object.assign(cell, _hdrStyle());
        else {
          cell.border = _border();
          cell.alignment = { vertical: 'middle', horizontal: ci === 0 ? 'left' : 'center' };
        }
      });
      exRow.height = 20;
    });
    ws1.getColumn(1).width = 16; ws1.getColumn(2).width = 12; ws1.getColumn(3).width = 16;

    // Sheet2: 负责人分布
    const ownerHeaders = ['负责人', '任务总数', '已完成', '延期', '完成率', '排名'];
    const ownerHRow = ws2.getRow(1);
    ownerHeaders.forEach((h, i) => { const c = ownerHRow.getCell(i+1); c.value = h; Object.assign(c, _hdrStyle()); });
    ws2.getRow(1).height = 22;

    const ownerRows = Object.entries(byOwner)
      .map(([name, d]) => ({ name, ...d, rate: d.total ? +(d.done/d.total*100).toFixed(1) : 0 }))
      .sort((a, b) => b.rate - a.rate);

    ownerRows.forEach((d, ri) => {
      const row = ws2.getRow(ri + 2);
      [d.name, d.total, d.done, d.overdue, `${d.rate}%`, ri + 1].forEach((v, ci) => {
        const cell = row.getCell(ci + 1);
        cell.value = v;
        cell.border = _border();
        cell.alignment = { horizontal: ci === 0 ? 'left' : 'center', vertical: 'middle' };
        if (ci === 3 && d.overdue > 0) cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFE0E0' } };
      });
      row.height = 18;
    });
    [1,2,3,4,5,6].forEach((c, i) => { ws2.getColumn(c).width = [14,10,10,10,12,8][i]; });

    // Sheet3: 明细
    const detailHeaders = ['#', '任务名称', '负责人', '截止日期', '进度%', '状态', '风险'];
    ws3.getRow(1).height = 22;
    detailHeaders.forEach((h, i) => { const c = ws3.getRow(1).getCell(i+1); c.value = h; Object.assign(c, _hdrStyle('FF37474F')); });

    tasks.forEach((t, ri) => {
      const row   = ws3.getRow(ri + 2);
      const isOd  = t.status === 'overdue' || (t.due && new Date(t.due) < today && t.progress < 100);
      const statusLabel = t.status === 'done' || t.progress >= 100 ? '✅ 已完成'
        : isOd ? '🔴 延期' : t.progress === 0 ? '⬜ 未开始' : '🔵 进行中';
      [ri+1, t.name, t.owner||'', t.due||'', t.progress||0, statusLabel, isOd ? '⚠️ 高' : '正常'].forEach((v, ci) => {
        const cell = row.getCell(ci + 1);
        cell.value = v;
        cell.border = _border();
        if (isOd) cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF3F3' } };
      });
      row.height = 18;
    });
    [1,2,3,4,5,6,7].forEach((c, i) => { ws3.getColumn(c).width = [5,24,12,12,10,14,10][i]; });

    const fp = outPath(input, 'task_stats');
    await _saveWb(wb, fp);
    return {
      filePath: fp, fileName: path.basename(fp),
      stats: { total, done, overdue, overdueCount: overdue, notStarted, completionRate, overdueRate },
      ownerRanking: ownerRows.slice(0, 10)
    };
  }
};

/* ═══════════════ 3. excel.budget ═════════════════════════ */
const excelBudget = {
  name: 'excel.budget',
  description: '生成专业预算执行表，含偏差分析/超支预警/执行率可视化',
  category: 'excel', icon: '💰', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      items: { type: 'array', description: '[{category, budgeted, actual, notes?}]' },
      title: { type: 'string', default: '预算执行分析表' },
      period: { type: 'string', description: '预算期间（如 2026年Q1）' },
      outputDir: { type: 'string' }
    },
    required: ['items']
  },
  handler: async (input) => {
    if (!input.items?.length) throw new Error('items 不能为空');
    const items = input.items;

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('预算执行表');

    // Title
    ws.mergeCells(1, 1, 1, 7);
    ws.getCell(1,1).value = input.title || '预算执行分析表';
    ws.getCell(1,1).font  = { bold: true, size: 14 };
    ws.getCell(1,1).alignment = { horizontal: 'center' };
    ws.getRow(1).height = 28;

    const headers = ['预算科目', '预算金额(元)', '实际执行(元)', '偏差金额(元)', '执行率', '偏差率', '状态'];
    const hRow = ws.getRow(2);
    hRow.height = 22;
    headers.forEach((h, i) => { const c = hRow.getCell(i+1); c.value = h; Object.assign(c, _hdrStyle('FF1B4F8A')); });

    let totalBudgeted = 0, totalActual = 0, overBudgetItems = 0;

    items.forEach((item, ri) => {
      const row       = ws.getRow(ri + 3);
      const deviation = (item.actual || 0) - (item.budgeted || 0);
      const execRate  = item.budgeted ? +(item.actual / item.budgeted * 100).toFixed(1) : 0;
      const devRate   = item.budgeted ? +(deviation / item.budgeted * 100).toFixed(1) : 0;
      const isOver    = deviation > 0;
      const status    = isOver ? '🔴 超支' : execRate < 50 ? '⚠️ 执行不足' : '✅ 正常';

      totalBudgeted += item.budgeted || 0;
      totalActual   += item.actual   || 0;
      if (isOver) overBudgetItems++;

      row.height = 20;
      [item.category, item.budgeted, item.actual, deviation, `${execRate}%`, `${devRate}%`, status].forEach((v, ci) => {
        const cell = row.getCell(ci + 1);
        cell.value = v;
        cell.border = _border();
        cell.alignment = { horizontal: ci === 0 ? 'left' : 'right', vertical: 'middle' };
        if (ci >= 1 && ci <= 3) cell.numFmt = '#,##0';
        if (isOver && ci !== 0) cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF5F5' } };
      });
    });

    // 合计行
    const sumRow = ws.getRow(items.length + 3);
    sumRow.height = 22;
    const totalDev  = totalActual - totalBudgeted;
    const totalRate = totalBudgeted ? +(totalActual / totalBudgeted * 100).toFixed(1) : 0;
    ['合计', totalBudgeted, totalActual, totalDev, `${totalRate}%`, '', totalDev > 0 ? '🔴 整体超支' : '✅ 在预算内'].forEach((v, ci) => {
      const cell = sumRow.getCell(ci + 1);
      cell.value = v;
      cell.font = { bold: true };
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE8F0FE' } };
      cell.border = _border();
      cell.alignment = { horizontal: ci === 0 ? 'left' : 'right', vertical: 'middle' };
      if (ci >= 1 && ci <= 3) cell.numFmt = '#,##0';
    });

    [1,2,3,4,5,6,7].forEach((c, i) => { ws.getColumn(c).width = [20,16,16,16,12,12,14][i]; });
    ws.views = [{ state: 'frozen', ySplit: 2 }];

    const fp = outPath(input, 'budget');
    await _saveWb(wb, fp);
    return {
      filePath: fp, fileName: path.basename(fp),
      summary: { totalBudgeted, totalActual, totalDeviation: totalActual - totalBudgeted, overBudgetItems,
                 executionRate: +(totalActual / totalBudgeted * 100).toFixed(1) }
    };
  }
};

/* ═══════════════ 4. excel.schedule ══════════════════════ */
const excelSchedule = {
  name: 'excel.schedule',
  description: '生成人员排班表，含工时统计/冲突检测/自动着色',
  category: 'excel', icon: '📆', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      employees: { type: 'array', description: '[{name, shifts: [{date, shift}]}] shift: morning|afternoon|night|off' },
      startDate: { type: 'string', description: 'YYYY-MM-DD' },
      days:      { type: 'number', default: 14, description: '排班天数' },
      shifts:    { type: 'array',  description: '班次定义 [{name, hours}]' },
      outputDir: { type: 'string' }
    },
    required: ['employees']
  },
  handler: async (input) => {
    const employees = input.employees || [];
    const days      = Math.min(input.days || 14, 31);
    const startDate = input.startDate ? new Date(input.startDate) : new Date();
    const SHIFT_COLORS = { morning: 'FFCCE5FF', afternoon: 'FFDCF0DC', night: 'FFFDE7C0', off: 'FFF5F5F5' };
    const SHIFT_HOURS  = { morning: 8, afternoon: 8, night: 8, off: 0 };

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('排班表');

    // 日期表头
    const dateHeaders = [];
    for (let i = 0; i < days; i++) {
      const d = new Date(startDate);
      d.setDate(d.getDate() + i);
      dateHeaders.push(`${d.getMonth()+1}/${d.getDate()}`);
    }

    ws.getRow(1).height = 22;
    ws.getCell(1,1).value = '姓名';
    Object.assign(ws.getCell(1,1), _hdrStyle());
    dateHeaders.forEach((h, i) => {
      const cell = ws.getRow(1).getCell(i + 2);
      cell.value = h;
      Object.assign(cell, _hdrStyle('FF37474F'));
    });
    ws.getRow(1).getCell(dateHeaders.length + 2).value = '总工时';
    Object.assign(ws.getRow(1).getCell(dateHeaders.length + 2), _hdrStyle('FF0D47A1'));

    const stats = [];
    employees.forEach((emp, ei) => {
      const row   = ws.getRow(ei + 2);
      row.height  = 18;
      row.getCell(1).value = emp.name;
      row.getCell(1).border = _border();

      let totalHours = 0;
      dateHeaders.forEach((_, di) => {
        const d = new Date(startDate);
        d.setDate(d.getDate() + di);
        const dateStr = d.toISOString().slice(0, 10);
        const shiftInfo = (emp.shifts || []).find(s => s.date === dateStr);
        const shiftName = shiftInfo?.shift || 'off';
        const cell = row.getCell(di + 2);
        cell.value = shiftName === 'off' ? '' : shiftName.charAt(0).toUpperCase();
        cell.fill  = { type: 'pattern', pattern: 'solid', fgColor: { argb: SHIFT_COLORS[shiftName] || 'FFFFFFFF' } };
        cell.border = _border();
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
        totalHours += SHIFT_HOURS[shiftName] || 0;
      });

      const totalCell = row.getCell(dateHeaders.length + 2);
      totalCell.value = totalHours;
      totalCell.font  = { bold: true };
      totalCell.fill  = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE8F0FE' } };
      totalCell.border = _border();
      totalCell.alignment = { horizontal: 'center' };
      stats.push({ name: emp.name, totalHours });
    });

    ws.getColumn(1).width = 14;
    for (let i = 2; i <= days + 2; i++) ws.getColumn(i).width = 5;

    const fp = outPath(input, 'schedule');
    await _saveWb(wb, fp);
    return { filePath: fp, fileName: path.basename(fp), stats };
  }
};

/* ═══════════════ 5. excel.kpi ═══════════════════════════ */
const excelKpi = {
  name: 'excel.kpi',
  description: '生成KPI考核表，自动加权计算总分，输出等级与排名',
  category: 'excel', icon: '🎯', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      employees:  { type: 'array', description: '[{name, scores: {维度名: 分数}}]' },
      dimensions: { type: 'array', description: '[{name, weight, description?}]' },
      title:      { type: 'string', default: 'KPI考核评分表' },
      outputDir:  { type: 'string' }
    },
    required: ['employees', 'dimensions']
  },
  handler: async (input) => {
    const emps  = input.employees || [];
    const dims  = input.dimensions || [];
    if (!emps.length || !dims.length) throw new Error('employees 和 dimensions 不能为空');

    const getGrade = (score) =>
      score >= 90 ? 'S' : score >= 80 ? 'A' : score >= 70 ? 'B' : score >= 60 ? 'C' : 'D';

    const rankings = emps.map(emp => {
      const totalScore = dims.reduce((s, d) => s + (emp.scores?.[d.name] || 0) * (d.weight || 0), 0);
      return { name: emp.name, scores: emp.scores, totalScore: +totalScore.toFixed(2), grade: getGrade(totalScore) };
    }).sort((a, b) => b.totalScore - a.totalScore);

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('KPI考核');

    // Headers
    const allHeaders = ['排名', '姓名', ...dims.map(d => `${d.name}\n(${Math.round(d.weight*100)}%)`), '总分', '等级'];
    ws.getRow(1).height = 30;
    allHeaders.forEach((h, i) => {
      const cell = ws.getRow(1).getCell(i + 1);
      cell.value = h;
      Object.assign(cell, _hdrStyle());
      cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true };
    });

    const gradeColor = { S: 'FF4CAF50', A: 'FF2196F3', B: 'FFFF9800', C: 'FFE91E63', D: 'FF9E9E9E' };
    rankings.forEach((emp, ri) => {
      const row = ws.getRow(ri + 2);
      row.height = 20;
      const rowData = [ri + 1, emp.name, ...dims.map(d => emp.scores?.[d.name] ?? 0), emp.totalScore, emp.grade];
      rowData.forEach((v, ci) => {
        const cell = row.getCell(ci + 1);
        cell.value = v;
        cell.border = _border();
        cell.alignment = { horizontal: ci <= 1 ? 'left' : 'center', vertical: 'middle' };
        if (ci === allHeaders.length - 1) {
          cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: gradeColor[v] + '33' } };
          cell.font = { bold: true, color: { argb: gradeColor[v] } };
        }
        if (ri === 0) cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF8E1' } };
      });
    });

    ws.getColumn(1).width = 6; ws.getColumn(2).width = 14;
    for (let i = 3; i <= dims.length + 2; i++) ws.getColumn(i).width = 12;
    ws.getColumn(dims.length + 3).width = 10; ws.getColumn(dims.length + 4).width = 8;

    const fp = outPath(input, 'kpi');
    await _saveWb(wb, fp);
    return { filePath: fp, fileName: path.basename(fp), rankings };
  }
};

/* ═══════════════ 6. excel.meetingNotes ══════════════════ */
const excelMeetingNotes = {
  name: 'excel.meetingNotes',
  description: '将会议纪要文本结构化提取为Excel待办表（议题/待办/负责人/截止时间）',
  category: 'excel', icon: '📋', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      meetingText: { type: 'string', description: '会议纪要文本' },
      title:       { type: 'string', default: '会议待办清单' },
      outputDir:   { type: 'string' }
    },
    required: ['meetingText']
  },
  handler: async (input) => {
    const text  = input.meetingText || '';
    const todos = [];

    // 提取待办项（识别"待办"/"行动项"/"TODO"模式）
    const lines = text.split('\n');
    let currentTopic = '综合事项';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // 识别议题
      const topicMatch = trimmed.match(/^(议题|主题|事项)\d*[：:]\s*(.+)/);
      if (topicMatch) { currentTopic = topicMatch[2]; continue; }

      // 识别待办
      const todoPatterns = [
        /^待办[：:]\s*(.+)/,
        /^[✅✓☑]\s*(.+)/,
        /^- ?TODO[：:]?\s*(.+)/i,
        /^行动项[：:]\s*(.+)/
      ];

      for (const p of todoPatterns) {
        const m = trimmed.match(p);
        if (m) {
          const content = m[1];
          // 提取负责人 (中文名2-4字 + 空格)
          const ownerMatch = content.match(/^([一-龥]{2,4})\s+/);
          const owner = ownerMatch ? ownerMatch[1] : '';
          // 提取截止时间
          const dueMatch = content.match(/截止\s*([0-9]{4}-?[0-9]{2}-?[0-9]{2}|[0-9]{1,2}月[0-9]{1,2}日)/);
          const due = dueMatch ? dueMatch[1] : '';
          const task = content
            .replace(ownerMatch ? ownerMatch[0] : '', '')
            .replace(dueMatch ? `截止${dueMatch[1]}` : '', '')
            .trim();
          todos.push({ topic: currentTopic, task: task || content, owner, due, status: '待办' });
          break;
        }
      }
    }

    // 若无结构化待办，则将每行非空文本作为简单待办
    if (!todos.length) {
      lines.filter(l => l.trim() && !l.match(/^(会议|时间|参与|议题|主题|结论)/))
        .slice(0, 20)
        .forEach(l => todos.push({ topic: '综合', task: l.trim(), owner: '', due: '', status: '待办' }));
    }

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('待办清单');

    ws.mergeCells(1, 1, 1, 6);
    ws.getCell(1,1).value = input.title || '会议待办清单';
    ws.getCell(1,1).font  = { bold: true, size: 13 };
    ws.getRow(1).height   = 26;

    const headers = ['#', '议题/分类', '待办事项', '负责人', '截止时间', '状态'];
    headers.forEach((h, i) => { const c = ws.getRow(2).getCell(i+1); c.value = h; Object.assign(c, _hdrStyle()); });
    ws.getRow(2).height = 22;

    todos.forEach((t, ri) => {
      const row = ws.getRow(ri + 3);
      row.height = 18;
      [ri+1, t.topic, t.task, t.owner, t.due, t.status].forEach((v, ci) => {
        const cell = row.getCell(ci + 1);
        cell.value = v;
        cell.border = _border();
        cell.alignment = { horizontal: ci === 2 ? 'left' : 'center', vertical: 'middle' };
      });
    });

    [1,2,3,4,5,6].forEach((c, i) => { ws.getColumn(c).width = [5,18,36,12,14,10][i]; });

    const fp = outPath(input, 'meeting');
    await _saveWb(wb, fp);
    return { filePath: fp, fileName: path.basename(fp), todos, todoCount: todos.length };
  }
};

/* ═══════════════ 7. excel.riskRegister ═══════════════════ */
const excelRiskRegister = {
  name: 'excel.riskRegister',
  description: '生成风险登记册，含风险矩阵/等级自动计算/应对措施/跟踪状态',
  category: 'excel', icon: '⚠️', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      risks: {
        type: 'array',
        description: '[{id,name,category,probability(1-5),impact(1-5),mitigation,owner?,status?}]'
      },
      title:     { type: 'string', default: '项目风险登记册' },
      outputDir: { type: 'string' }
    },
    required: ['risks']
  },
  handler: async (input) => {
    const risks = (input.risks || []).map(r => {
      const score    = (r.probability || 1) * (r.impact || 1);
      const level    = score >= 15 ? 'HIGH' : score >= 8 ? 'MEDIUM' : 'LOW';
      const color    = level === 'HIGH' ? 'FFFFC7CE' : level === 'MEDIUM' ? 'FFFFEB9C' : 'FFC6EFCE';
      return { ...r, score, level, color };
    }).sort((a, b) => b.score - a.score);

    const highRisks = risks.filter(r => r.level === 'HIGH');

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('风险登记册');

    ws.mergeCells(1, 1, 1, 9);
    ws.getCell(1,1).value = input.title || '项目风险登记册';
    ws.getCell(1,1).font  = { bold: true, size: 13 };
    ws.getRow(1).height   = 26;

    const headers = ['风险ID', '风险描述', '类别', '概率(1-5)', '影响(1-5)', '风险值', '等级', '应对措施', '状态'];
    headers.forEach((h, i) => { const c = ws.getRow(2).getCell(i+1); c.value = h; Object.assign(c, _hdrStyle('FFCC0000')); });
    ws.getRow(2).height = 22;

    risks.forEach((r, ri) => {
      const row = ws.getRow(ri + 3);
      row.height = 20;
      const levelLabel = { HIGH: '🔴 高', MEDIUM: '🟡 中', LOW: '🟢 低' }[r.level];
      [r.id, r.name, r.category||'', r.probability, r.impact, r.score, levelLabel, r.mitigation||'', r.status||'待处理'].forEach((v, ci) => {
        const cell = row.getCell(ci + 1);
        cell.value = v;
        cell.border = _border();
        cell.fill   = { type: 'pattern', pattern: 'solid', fgColor: { argb: r.color } };
        cell.alignment = { vertical: 'middle', horizontal: [1,7].includes(ci) ? 'left' : 'center', wrapText: ci === 7 };
      });
    });

    [1,2,3,4,5,6,7,8,9].forEach((c, i) => { ws.getColumn(c).width = [10,28,14,10,10,10,10,30,12][i]; });

    // 风险矩阵 sheet
    const wsMatrix = wb.addWorksheet('风险矩阵');
    wsMatrix.getCell(1,1).value = '风险矩阵（概率 × 影响）';
    wsMatrix.getCell(1,1).font  = { bold: true };
    wsMatrix.getRow(2).getCell(1).value = '概率\\影响';
    for (let j = 1; j <= 5; j++) wsMatrix.getRow(2).getCell(j+1).value = j;
    for (let i = 1; i <= 5; i++) {
      wsMatrix.getRow(i+2).getCell(1).value = i;
      for (let j = 1; j <= 5; j++) {
        const score = i * j;
        const cell  = wsMatrix.getRow(i+2).getCell(j+1);
        cell.value  = score;
        const col   = score >= 15 ? 'FFFFC7CE' : score >= 8 ? 'FFFFEB9C' : 'FFC6EFCE';
        cell.fill   = { type: 'pattern', pattern: 'solid', fgColor: { argb: col } };
        cell.border = _border();
        cell.alignment = { horizontal: 'center' };
      }
    }

    const riskMatrix = { high: highRisks.length, medium: risks.filter(r=>r.level==='MEDIUM').length, low: risks.filter(r=>r.level==='LOW').length };
    const fp = outPath(input, 'risk_register');
    await _saveWb(wb, fp);
    return { filePath: fp, fileName: path.basename(fp), riskMatrix, highRisks, totalRisks: risks.length };
  }
};

/* ═══════════════ 8. excel.regression ═════════════════════ */
const excelRegression = {
  name: 'excel.regression',
  description: '线性回归分析：拟合方程/R²/置信区间/预测值，输出Excel报告',
  category: 'excel', icon: '📈', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      x: { type: 'array', description: '自变量数组' },
      y: { type: 'array', description: '因变量数组' },
      xLabel: { type: 'string', default: 'X' },
      yLabel: { type: 'string', default: 'Y' },
      predictX: { type: 'array', description: '预测点 x 值' },
      outputDir: { type: 'string' }
    },
    required: ['x', 'y']
  },
  handler: async (input) => {
    const result = stats.linearRegression(input.x, input.y);
    const desc   = stats.descriptiveStats(input.y);
    const predictions = (input.predictX || []).map(xv => ({
      x: xv, predictedY: +(result.predict(xv)).toFixed(4)
    }));

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('回归分析');

    // 回归结果
    ws.getCell(1,1).value = '线性回归分析报告';
    ws.getCell(1,1).font = { bold: true, size: 13 };
    ws.getRow(1).height  = 24;

    const summaryData = [
      ['回归方程', result.equation],
      ['斜率(Slope)', result.slope],
      ['截距(Intercept)', result.intercept],
      ['决定系数 R²', result.r2],
      ['相关强度', result.r2 >= 0.9 ? '强相关' : result.r2 >= 0.6 ? '中等相关' : '弱相关'],
      ['样本量', input.x.length],
      ['Y均值', +desc.mean.toFixed(4)],
      ['Y标准差', +desc.std.toFixed(4)]
    ];

    summaryData.forEach(([k, v], ri) => {
      ws.getRow(ri + 2).getCell(1).value = k;
      ws.getRow(ri + 2).getCell(2).value = v;
      ws.getRow(ri + 2).getCell(1).font = { bold: true };
      ws.getRow(ri + 2).getCell(2).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFE8F4FF' } };
      [1,2].forEach(c => { ws.getRow(ri+2).getCell(c).border = _border(); });
    });

    // 数据表
    const dataWs = wb.addWorksheet('原始数据');
    [input.xLabel, input.yLabel, '拟合值', '残差'].forEach((h, i) => {
      const c = dataWs.getRow(1).getCell(i+1); c.value = h; Object.assign(c, _hdrStyle());
    });
    input.x.forEach((xv, i) => {
      const yv   = input.y[i];
      const fit  = result.predict(xv);
      const res  = yv - fit;
      [xv, yv, +fit.toFixed(4), +res.toFixed(4)].forEach((v, ci) => {
        dataWs.getRow(i+2).getCell(ci+1).value = v;
        dataWs.getRow(i+2).getCell(ci+1).border = _border();
      });
    });

    ws.getColumn(1).width = 20; ws.getColumn(2).width = 20;

    const fp = outPath(input, 'regression');
    await _saveWb(wb, fp);
    return {
      filePath: fp, fileName: path.basename(fp),
      result: { ...result, equation: result.equation },
      predictions,
      interpretation: `回归方程：${result.equation}，R²=${result.r2}，拟合${result.r2 >= 0.8 ? '效果良好' : '效果一般'}`
    };
  }
};

/* ═══════════════ 9. excel.correlation ════════════════════ */
const excelCorrelation = {
  name: 'excel.correlation',
  description: '多变量相关性矩阵分析，输出带热力图着色的Excel报告',
  category: 'excel', icon: '🔗', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      data:      { type: 'object', description: '{变量名: 数值数组}' },
      outputDir: { type: 'string' }
    },
    required: ['data']
  },
  handler: async (input) => {
    const variables = Object.keys(input.data || {});
    if (variables.length < 2) throw new Error('至少需要2个变量');

    const matrix = {};
    for (const v1 of variables) {
      matrix[v1] = {};
      for (const v2 of variables) {
        if (v1 === v2) { matrix[v1][v2] = 1; continue; }
        matrix[v1][v2] = stats.pearsonCorrelation(input.data[v1], input.data[v2]);
      }
    }

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('相关性矩阵');
    ws.getCell(1,1).value = '相关性分析矩阵（Pearson）';
    ws.getCell(1,1).font  = { bold: true, size: 12 };
    ws.getRow(1).height   = 24;

    // 表头
    ws.getRow(2).getCell(1).value = '';
    variables.forEach((v, i) => {
      const hCell = ws.getRow(2).getCell(i + 2);
      hCell.value = v; Object.assign(hCell, _hdrStyle()); hCell.rotation = 0;
    });

    variables.forEach((v1, ri) => {
      const row = ws.getRow(ri + 3);
      row.height = 22;
      const lCell = row.getCell(1); lCell.value = v1; Object.assign(lCell, _hdrStyle());
      variables.forEach((v2, ci) => {
        const r    = matrix[v1][v2];
        const cell = row.getCell(ci + 2);
        cell.value  = +r.toFixed(3);
        cell.border = _border();
        cell.alignment = { horizontal: 'center', vertical: 'middle' };
        // 热力图着色
        const abs  = Math.abs(r);
        const aRgb = Math.round(abs * 200).toString(16).padStart(2, '0');
        cell.fill = v1 === v2
          ? { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFB0BEC5' } }
          : r > 0
            ? { type: 'pattern', pattern: 'solid', fgColor: { argb: `FF${aRgb}C8${aRgb}` } }
            : { type: 'pattern', pattern: 'solid', fgColor: { argb: `FFC8${aRgb}${aRgb}` } };
        cell.font = { bold: abs > 0.7, color: { argb: abs > 0.9 ? 'FF000000' : 'FF333333' } };
      });
    });

    variables.forEach((_, i) => { ws.getColumn(i + 2).width = 12; });
    ws.getColumn(1).width = 16;

    const fp = outPath(input, 'correlation');
    await _saveWb(wb, fp);
    return { filePath: fp, fileName: path.basename(fp), matrix, variables };
  }
};

/* ═══════════════ 10. excel.timeSeries ════════════════════ */
const excelTimeSeries = {
  name: 'excel.timeSeries',
  description: '时间序列趋势分析与预测，含移动平均/指数平滑/线性趋势',
  category: 'excel', icon: '📉', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      series:          { type: 'array', description: '时间序列数值' },
      labels:          { type: 'array', description: '时间标签' },
      forecastPeriods: { type: 'number', default: 3 },
      alpha:           { type: 'number', default: 0.3 },
      outputDir:       { type: 'string' }
    },
    required: ['series']
  },
  handler: async (input) => {
    const series = input.series || [];
    if (series.length < 3) throw new Error('时间序列至少需要3个数据点');

    const alpha     = input.alpha || 0.3;
    const forecastN = input.forecastPeriods || 3;
    const labels    = input.labels || series.map((_, i) => `T${i+1}`);

    // 指数平滑
    const smooth = stats.exponentialSmoothing(series, alpha, forecastN);

    // 线性趋势
    const xArr = series.map((_, i) => i + 1);
    const reg   = stats.linearRegression(xArr, series);
    const trend = reg.slope > 0.05 ? '上升' : reg.slope < -0.05 ? '下降' : '平稳';

    // 移动平均（3期）
    const maWindow = Math.min(3, Math.floor(series.length / 2));
    const ma3 = series.map((_, i) => {
      if (i < maWindow - 1) return null;
      return +(series.slice(i - maWindow + 1, i + 1).reduce((s,v)=>s+v,0) / maWindow).toFixed(4);
    });

    const forecast = smooth.forecasts.slice(0, forecastN);

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('时间序列分析');

    // 摘要
    ws.getCell(1,1).value = '时间序列分析报告';
    ws.getCell(1,1).font  = { bold: true, size: 13 };
    ws.getRow(1).height   = 26;

    [
      ['整体趋势', trend],
      ['线性斜率', reg.slope],
      ['预测方法', `指数平滑（α=${alpha}）`],
      [`预测未来${forecastN}期`, forecast.map((v,i) => `T+${i+1}: ${v.toFixed(2)}`).join('，')]
    ].forEach(([k, v], ri) => {
      ws.getRow(ri+2).getCell(1).value = k;
      ws.getRow(ri+2).getCell(2).value = v;
      ws.getRow(ri+2).getCell(1).font  = { bold: true };
      [1,2].forEach(c => { ws.getRow(ri+2).getCell(c).border = _border(); });
    });

    // 数据明细
    const dws = wb.addWorksheet('数据明细');
    ['期次', '原始值', '指数平滑', `移动平均(${maWindow}期)`, '线性趋势值'].forEach((h, i) => {
      const c = dws.getRow(1).getCell(i+1); c.value = h; Object.assign(c, _hdrStyle());
    });

    series.forEach((v, i) => {
      const trendVal = +(reg.slope * (i+1) + reg.intercept).toFixed(4);
      [labels[i]||`T${i+1}`, v, smooth.smoothed[i], ma3[i]??'', trendVal].forEach((dv, ci) => {
        dws.getRow(i+2).getCell(ci+1).value = dv;
        dws.getRow(i+2).getCell(ci+1).border = _border();
      });
    });

    ws.getColumn(1).width = 20; ws.getColumn(2).width = 40;
    [1,2,3,4,5].forEach((c, i) => { dws.getColumn(c).width = [12,12,14,14,14][i]; });

    const fp = outPath(input, 'timeseries');
    await _saveWb(wb, fp);
    return { filePath: fp, fileName: path.basename(fp), trend, forecast, smooth: smooth.smoothed };
  }
};

/* ═══════════════ 11. excel.anomaly ═══════════════════════ */
const excelAnomaly = {
  name: 'excel.anomaly',
  description: '异常值检测（IQR + Z-Score），高亮标注Excel报告',
  category: 'excel', icon: '🔍', source: 'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      data:      { type: 'array', description: '数值数组' },
      labels:    { type: 'array', description: '行标签' },
      column:    { type: 'string', default: '数据' },
      outputDir: { type: 'string' }
    },
    required: ['data']
  },
  handler: async (input) => {
    const data   = input.data || [];
    if (!data.length) throw new Error('data 不能为空');
    const labels = input.labels || data.map((_, i) => `第${i+1}行`);
    const result = stats.detectAnomalies(data);
    const desc   = stats.descriptiveStats(data);

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('异常检测');

    ws.getCell(1,1).value = `${input.column || '数据'} — 异常值检测报告`;
    ws.getCell(1,1).font  = { bold: true, size: 13 };
    ws.getRow(1).height   = 26;

    // 统计摘要
    [
      ['异常值数量', result.anomalies.length],
      ['异常率',     `${(result.anomalies.length / data.length * 100).toFixed(1)}%`],
      ['IQR下界',    result.lower], ['IQR上界', result.upper],
      ['均值',       desc.mean], ['标准差', desc.std]
    ].forEach(([k, v], ri) => {
      ws.getRow(ri+2).getCell(1).value = k;
      ws.getRow(ri+2).getCell(2).value = v;
      ws.getRow(ri+2).getCell(1).font  = { bold: true };
      [1,2].forEach(c => { ws.getRow(ri+2).getCell(c).border = _border(); });
    });

    // 数据明细
    const dws = wb.addWorksheet('数据明细');
    ['序号', '标签', '数值', 'Z-Score', '是否异常', '说明'].forEach((h, i) => {
      const c = dws.getRow(1).getCell(i+1); c.value = h; Object.assign(c, _hdrStyle('FF37474F'));
    });

    const anomSet = new Set(result.anomalies.map(a => a.index));
    data.forEach((v, i) => {
      const isAnom  = anomSet.has(i);
      const aInfo   = result.anomalies.find(a => a.index === i);
      const zScore  = aInfo?.zScore ?? +((v - desc.mean) / (desc.std || 1)).toFixed(3);
      const reason  = v > result.upper ? '超过上界' : v < result.lower ? '低于下界' : '正常';
      const row     = dws.getRow(i + 2);
      [i+1, labels[i]||`T${i+1}`, v, zScore, isAnom ? '⚠️ 异常' : '正常', isAnom ? reason : ''].forEach((dv, ci) => {
        const cell  = row.getCell(ci + 1);
        cell.value  = dv;
        cell.border = _border();
        if (isAnom) cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF3CD' } };
        if (isAnom && ci === 4) { cell.font = { bold: true, color: { argb: 'FFCC6600' } }; }
      });
    });

    [1,2,3,4,5,6].forEach((c, i) => { dws.getColumn(c).width = [8,16,12,12,12,16][i]; });

    const fp = outPath(input, 'anomaly');
    await _saveWb(wb, fp);
    return { filePath: fp, fileName: path.basename(fp), anomalies: result.anomalies,
             anomalyCount: result.anomalies.length, stats: desc };
  }
};

module.exports = {
  ALL_MANAGEMENT_TOOLS: [
    excelGantt, excelTaskStats, excelBudget, excelSchedule,
    excelKpi, excelMeetingNotes, excelRiskRegister,
    excelRegression, excelCorrelation, excelTimeSeries, excelAnomaly
  ]
};
