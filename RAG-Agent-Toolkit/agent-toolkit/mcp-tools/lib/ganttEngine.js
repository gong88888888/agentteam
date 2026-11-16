/**
 * GanttEngine — 专业甘特图 Excel 生成器
 * 使用 ExcelJS 构建可编辑的甘特图，包含：
 *   - 时间轴（日/周/月/季度自适应）
 *   - 任务进度条（彩色单元格填充）
 *   - 里程碑标记（菱形符号）
 *   - 延期风险高亮（红色）
 *   - 依赖关系标注（备注）
 */
const ExcelJS = require('exceljs');
const path    = require('path');
const fs      = require('fs');

const COLORS = {
  header:      'FF1B4F8A',
  headerFg:    'FFFFFFFF',
  task:        'FF409EFF',
  taskDone:    'FF67C23A',
  taskOverdue: 'FFF56C6C',
  milestone:   'FFFF9900',
  rowOdd:      'FFF5F7FA',
  rowEven:     'FFFFFFFF',
  progressBg:  'FFE8F4FF',
  weekend:     'FFFAFAFA',
  gridLine:    'FFD9D9D9'
};

class GanttEngine {
  /**
   * 从任务数组构建甘特图数据结构
   */
  buildGanttData(tasks, opts = {}) {
    if (!tasks?.length) return { headers: [], rows: [], totalDays: 0 };

    // 时间范围
    const allDates = tasks.flatMap(t => [new Date(t.start), new Date(t.end)]);
    const minDate  = new Date(Math.min(...allDates));
    const maxDate  = new Date(Math.max(...allDates));
    minDate.setDate(minDate.getDate() - 2);  // 左边留白
    maxDate.setDate(maxDate.getDate() + 5);  // 右边留白

    const totalDays = Math.ceil((maxDate - minDate) / 86400000);
    const unit      = opts.unit || this._autoUnit(totalDays);
    const headers   = this._buildHeaders(minDate, maxDate, unit);
    const today     = new Date();

    const rows = tasks.map((t, idx) => {
      const start    = new Date(t.start);
      const end      = new Date(t.end);
      const duration = Math.ceil((end - start) / 86400000) + 1;
      const offset   = Math.ceil((start - minDate) / 86400000);
      const progress = Math.min(100, Math.max(0, t.progress || 0));
      const isOverdue = end < today && progress < 100;

      return {
        id:        t.id || idx + 1,
        name:      t.name || '',
        owner:     t.owner || '',
        start:     t.start,
        end:       t.end,
        duration,
        offset,
        progress,
        milestone:  !!t.milestone,
        deps:       t.deps || [],
        isOverdue,
        riskLevel:  isOverdue ? 'high' : (progress < 30 && duration > 14 ? 'medium' : 'low')
      };
    });

    return { headers, rows, totalDays, unit, startDate: minDate, endDate: maxDate };
  }

  /**
   * 生成甘特图 Excel 文件
   */
  async generateGanttExcel(tasks, outputPath, opts = {}) {
    const data = this.buildGanttData(tasks, opts);
    const wb   = new ExcelJS.Workbook();
    const ws   = wb.addWorksheet('甘特图', { properties: { tabColor: { argb: 'FF409EFF' } } });

    const FIXED_COLS  = 5; // 序号/任务名/负责人/开始/结束
    const totalCols   = FIXED_COLS + data.headers.length;

    // ── 列宽设置 ────────────────────────────────────
    ws.getColumn(1).width = 6;   // 序号
    ws.getColumn(2).width = 24;  // 任务名
    ws.getColumn(3).width = 10;  // 负责人
    ws.getColumn(4).width = 12;  // 开始日期
    ws.getColumn(5).width = 12;  // 结束日期
    for (let c = FIXED_COLS + 1; c <= totalCols; c++) {
      ws.getColumn(c).width = 3.5;
    }

    // ── 标题行 ──────────────────────────────────────
    const title = opts.title || '项目甘特图';
    ws.mergeCells(1, 1, 1, totalCols);
    const titleCell = ws.getCell(1, 1);
    titleCell.value = title;
    titleCell.font  = { bold: true, size: 14, color: { argb: 'FF1B4F8A' } };
    titleCell.alignment = { horizontal: 'center', vertical: 'middle' };
    ws.getRow(1).height = 30;

    // ── 表头行 ──────────────────────────────────────
    const headers = ['#', '任务名称', '负责人', '开始日期', '结束日期', ...data.headers];
    const hRow = ws.getRow(2);
    hRow.height = 24;
    headers.forEach((h, i) => {
      const cell = hRow.getCell(i + 1);
      cell.value = h;
      cell.fill  = { type: 'pattern', pattern: 'solid', fgColor: { argb: COLORS.header } };
      cell.font  = { bold: true, size: 10, color: { argb: COLORS.headerFg } };
      cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: false };
      cell.border = { right: { style: 'thin', color: { argb: 'FF2E6DA4' } } };
    });

    // ── 任务行 ──────────────────────────────────────
    data.rows.forEach((row, ri) => {
      const excelRow = ws.getRow(ri + 3);
      excelRow.height = 18;
      const bg = ri % 2 === 0 ? COLORS.rowOdd : COLORS.rowEven;

      // 固定列数据
      const fixedData = [
        row.id, row.name, row.owner,
        { value: new Date(row.start), numFmt: 'yyyy-mm-dd' },
        { value: new Date(row.end),   numFmt: 'yyyy-mm-dd' }
      ];
      fixedData.forEach((d, ci) => {
        const cell = excelRow.getCell(ci + 1);
        if (typeof d === 'object' && d.value instanceof Date) {
          cell.value  = d.value;
          cell.numFmt = d.numFmt;
        } else {
          cell.value = d;
        }
        cell.fill      = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
        cell.alignment = { vertical: 'middle', horizontal: ci === 1 ? 'left' : 'center' };
        cell.font      = { size: 10, color: { argb: row.isOverdue && ci === 1 ? 'FFCC0000' : 'FF333333' } };
        cell.border    = { bottom: { style: 'thin', color: { argb: COLORS.gridLine } } };
      });

      // 甘特图进度条（彩色单元格）
      for (let ci = 0; ci < data.headers.length; ci++) {
        const col    = excelRow.getCell(FIXED_COLS + ci + 1);
        const dayIdx = ci;
        const inTask = dayIdx >= row.offset && dayIdx < row.offset + row.duration;
        const donePct = row.progress / 100;
        const progressEnd = row.offset + Math.floor(row.duration * donePct);

        if (row.milestone && dayIdx === row.offset) {
          col.value = '◆';
          col.font  = { bold: true, size: 11, color: { argb: COLORS.milestone } };
          col.alignment = { horizontal: 'center', vertical: 'middle' };
          col.fill  = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFF3CD' } };
        } else if (inTask) {
          const isProgress = dayIdx < progressEnd;
          const barColor   = row.isOverdue ? COLORS.taskOverdue : (isProgress ? COLORS.taskDone : COLORS.task);
          col.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: isProgress ? barColor : COLORS.progressBg } };
          col.value = '';
        } else {
          col.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
        }
        col.border = { right: { style: 'hair', color: { argb: COLORS.gridLine } },
                       bottom: { style: 'thin', color: { argb: COLORS.gridLine } } };
      }
    });

    // ── 图例 ────────────────────────────────────────
    const legendRow = data.rows.length + 4;
    [
      ['■ 已完成', COLORS.taskDone],
      ['■ 进行中', COLORS.task],
      ['■ 延期',   COLORS.taskOverdue],
      ['◆ 里程碑', COLORS.milestone]
    ].forEach(([text, color], i) => {
      const cell = ws.getCell(legendRow, i * 2 + 1);
      cell.value = text;
      cell.font  = { size: 9, color: { argb: color }, bold: true };
    });

    // 写文件
    const dir = path.dirname(outputPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    await wb.xlsx.writeFile(outputPath);
    return { filePath: outputPath, ...data };
  }

  /* ── 辅助 ────────────────────────────────────────── */
  _autoUnit(totalDays) {
    if (totalDays <= 60)  return 'day';
    if (totalDays <= 180) return 'week';
    if (totalDays <= 730) return 'month';
    return 'quarter';
  }

  _buildHeaders(start, end, unit) {
    const headers = [];
    const cur = new Date(start);
    while (cur <= end) {
      if (unit === 'day') {
        headers.push(`${cur.getMonth()+1}/${cur.getDate()}`);
        cur.setDate(cur.getDate() + 1);
      } else if (unit === 'week') {
        headers.push(`W${this._isoWeek(cur)}`);
        cur.setDate(cur.getDate() + 1);
      } else if (unit === 'month') {
        headers.push(`${cur.getFullYear()}/${cur.getMonth()+1}`);
        cur.setDate(cur.getDate() + 1);
      } else {
        headers.push(`Q${Math.ceil((cur.getMonth()+1)/3)}`);
        cur.setDate(cur.getDate() + 1);
      }
    }
    return headers;
  }

  _isoWeek(d) {
    const jan1 = new Date(d.getFullYear(), 0, 1);
    return Math.ceil(((d - jan1) / 86400000 + jan1.getDay() + 1) / 7);
  }
}

module.exports = GanttEngine;
