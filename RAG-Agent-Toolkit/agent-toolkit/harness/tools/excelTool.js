/**
 * Excel Tools — 封装 Excel 智能体各功能为 Harness 工具
 * 每个工具是独立类，最终统一导出供 toolLoader 注册
 */
const BaseTool = require('./baseTool');

/* ── 公式生成工具 ─────────────────────────────────────────── */
class ExcelFormulaTool extends BaseTool {
  constructor() { super('excelFormula', '自然语言 → Excel 公式'); }

  async execute(input) {
    const { naturalLanguage, dataRange, userId } = input;
    const { callAI } = require('../../services/aiService');
    const formula = await callAI([
      { role: 'system', content: '你是 Excel 公式专家，只输出公式本身，不加任何解释。' },
      { role: 'user',   content: `将以下需求转为 Excel 公式。数据范围: ${dataRange || 'A1:Z100'}\n需求: ${naturalLanguage}` }
    ], {}, userId);
    return { formula: formula.trim() };
  }
}

/* ── 数据清洗工具 ─────────────────────────────────────────── */
class ExcelDataCleanTool extends BaseTool {
  constructor() { super('excelDataClean', 'Excel 数据清洗'); }

  async execute(input) {
    const { filePath, operations = [] } = input;
    const ExcelJS = require('exceljs');
    const path    = require('path');
    const wb      = new ExcelJS.Workbook();
    await wb.xlsx.readFile(filePath);

    wb.eachSheet(sheet => {
      sheet.eachRow(row => {
        row.eachCell(cell => {
          if (operations.includes('trim') && typeof cell.value === 'string') {
            cell.value = cell.value.trim();
          }
          if (operations.includes('upper') && typeof cell.value === 'string') {
            cell.value = cell.value.toUpperCase();
          }
          if (operations.includes('removeEmpty') && cell.value === '') {
            cell.value = null;
          }
        });
      });
    });

    const outPath = path.join(path.dirname(filePath), `cleaned_${Date.now()}.xlsx`);
    await wb.xlsx.writeFile(outPath);
    return { filePath: outPath };
  }
}

/* ── 图表生成工具 ─────────────────────────────────────────── */
class ExcelChartTool extends BaseTool {
  constructor() { super('excelChart', 'Excel 图表生成（描述 → 配置）'); }

  async execute(input) {
    const { description, dataRange, userId } = input;
    const { callAI } = require('../../services/aiService');
    const config = await callAI([
      { role: 'system', content: '你是 Excel 图表配置专家，以 JSON 格式输出图表配置，不加任何 Markdown 代码块。' },
      { role: 'user',   content: `为以下需求生成 ExcelJS 图表配置对象（包含 type、series、categories 等）:\n数据范围: ${dataRange}\n需求: ${description}` }
    ], {}, userId);
    try {
      return { chartConfig: JSON.parse(config) };
    } catch {
      return { chartConfig: null, rawConfig: config };
    }
  }
}

/* ── 数据透视表工具 ───────────────────────────────────────── */
class ExcelPivotTool extends BaseTool {
  constructor() { super('excelPivot', 'Excel 数据透视表生成'); }

  async execute(input) {
    const { description, sheetName, userId } = input;
    const { callAI } = require('../../services/aiService');
    const config = await callAI([
      { role: 'system', content: '你是数据透视表专家，以 JSON 格式描述透视表结构（rows, columns, values, filters），不加 Markdown。' },
      { role: 'user',   content: `为工作表 "${sheetName}" 生成透视表配置:\n需求: ${description}` }
    ], {}, userId);
    try {
      return { pivotConfig: JSON.parse(config) };
    } catch {
      return { pivotConfig: null, rawConfig: config };
    }
  }
}

/* ── 数据对比工具 ─────────────────────────────────────────── */
class ExcelCompareTool extends BaseTool {
  constructor() { super('excelCompare', 'Excel 多表数据对比'); }

  async execute(input) {
    const { filePathA, filePathB, sheetName = 'Sheet1', keyColumn = 'A' } = input;
    const ExcelJS = require('exceljs');

    const readSheet = async (fp) => {
      const wb = new ExcelJS.Workbook();
      await wb.xlsx.readFile(fp);
      const ws = wb.getWorksheet(sheetName) || wb.worksheets[0];
      const rows = [];
      ws.eachRow(r => rows.push(r.values.slice(1)));
      return rows;
    };

    const [rowsA, rowsB] = await Promise.all([readSheet(filePathA), readSheet(filePathB)]);
    const diff = [];
    const maxLen = Math.max(rowsA.length, rowsB.length);

    for (let i = 0; i < maxLen; i++) {
      const a = JSON.stringify(rowsA[i] || []);
      const b = JSON.stringify(rowsB[i] || []);
      if (a !== b) diff.push({ row: i + 1, fileA: rowsA[i], fileB: rowsB[i] });
    }

    return { totalRows: maxLen, diffCount: diff.length, differences: diff.slice(0, 100) };
  }
}

module.exports = {
  ExcelFormulaTool,
  ExcelDataCleanTool,
  ExcelChartTool,
  ExcelPivotTool,
  ExcelCompareTool
};
