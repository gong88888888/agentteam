/**
 * Harness 工具加载器
 * 自动实例化并注册 tools/ 目录下的所有工具类
 */
const harness = require('./controller');

const {
  ExcelFormulaTool,
  ExcelDataCleanTool,
  ExcelChartTool,
  ExcelPivotTool,
  ExcelCompareTool
} = require('./tools/excelTool');

const { PPTOutlineTool, PPTGenerateTool } = require('./tools/pptTool');
const AITool  = require('./tools/aiTool');
const RAGTool = require('./tools/ragTool');

function loadAllTools() {
  const tools = [
    new AITool(),
    new RAGTool(),
    new ExcelFormulaTool(),
    new ExcelDataCleanTool(),
    new ExcelChartTool(),
    new ExcelPivotTool(),
    new ExcelCompareTool(),
    new PPTOutlineTool(),
    new PPTGenerateTool()
  ];

  for (const tool of tools) {
    harness.registerTool(tool.name, tool);
  }

  console.log(`[Harness] 共加载 ${tools.length} 个工具`);
}

module.exports = { loadAllTools };
