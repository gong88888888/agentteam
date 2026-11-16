/**
 * 内置 MCP 工具集
 * - 把现有 Harness 工具包装为标准 MCP 工具（保留原实现，不删除）
 * - 新增若干通用工具（文档生成、搜索占位、文件读取等）
 */
const AITool          = require('../../harness/tools/aiTool');
const RAGTool         = require('../../harness/tools/ragTool');
const {
  ExcelFormulaTool, ExcelDataCleanTool, ExcelChartTool,
  ExcelPivotTool,   ExcelCompareTool
}                     = require('../../harness/tools/excelTool');
const { PPTOutlineTool, PPTGenerateTool } = require('../../harness/tools/pptTool');

const fs   = require('fs');
const path = require('path');

/** 把一个 Harness BaseTool 实例转换为 MCP 工具描述 */
function wrap(toolInstance, meta) {
  return {
    name:        meta.name,
    description: meta.description || toolInstance.description,
    inputSchema: meta.inputSchema || { type: 'object', properties: {} },
    category:    meta.category    || 'general',
    icon:        meta.icon        || '🛠️',
    source:      'builtin',
    handler:     async (input) => {
      const result = await toolInstance.execute(input || {});
      return result;
    }
  };
}

/* ─── AI 工具 ─────────────────────────────────────────────── */
const aiTool = new AITool();

const mcpAITool = {
  name:        'ai.chat',
  description: '调用 AI 大模型完成对话/生成任务（OpenAI 兼容）',
  category:    'ai',
  icon:        '🧠',
  source:      'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      messages: { type: 'array', description: 'OpenAI 消息数组 [{role, content}]' },
      userId:   { type: 'string', description: '用户 ID，用于读取该用户的 API 配置' },
      overrideConfig: { type: 'object', description: '覆盖采样参数：temperature/maxTokens 等' }
    },
    required: ['messages']
  },
  handler: async (input) => aiTool.execute(input)
};

/* ─── RAG 工具 ────────────────────────────────────────────── */
const ragTool = new RAGTool();
const mcpRAGTool = {
  name:        'rag.context',
  description: '从知识库构建 RAG 上下文，自动合并多文件',
  category:    'rag',
  icon:        '📚',
  source:      'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      fileIds:   { type: 'array', items: { type: 'string' } },
      userId:    { type: 'string' },
      maxLength: { type: 'number', default: 12000 }
    },
    required: ['fileIds']
  },
  handler: async (input) => ragTool.execute(input)
};

/* ─── Excel 工具集 ────────────────────────────────────────── */
const mcpExcelFormula = wrap(new ExcelFormulaTool(), {
  name: 'excel.formula',
  description: '把自然语言需求翻译为 Excel 公式',
  category: 'excel', icon: '🔢',
  inputSchema: {
    type: 'object',
    properties: {
      naturalLanguage: { type: 'string' },
      dataRange:       { type: 'string', default: 'A1:Z100' },
      userId:          { type: 'string' }
    },
    required: ['naturalLanguage']
  }
});

const mcpExcelClean = wrap(new ExcelDataCleanTool(), {
  name: 'excel.clean',
  description: 'Excel 文件数据清洗（trim/upper/removeEmpty）',
  category: 'excel', icon: '🧹',
  inputSchema: {
    type: 'object',
    properties: {
      filePath:   { type: 'string' },
      operations: { type: 'array', items: { type: 'string' } }
    },
    required: ['filePath']
  }
});

const mcpExcelChart = wrap(new ExcelChartTool(), {
  name: 'excel.chart',
  description: '根据自然语言描述生成 Excel 图表配置',
  category: 'excel', icon: '📊',
  inputSchema: {
    type: 'object',
    properties: {
      description: { type: 'string' },
      dataRange:   { type: 'string' },
      userId:      { type: 'string' }
    },
    required: ['description']
  }
});

const mcpExcelPivot = wrap(new ExcelPivotTool(), {
  name: 'excel.pivot',
  description: '生成数据透视表配置',
  category: 'excel', icon: '🔀',
  inputSchema: {
    type: 'object',
    properties: {
      description: { type: 'string' },
      sheetName:   { type: 'string', default: 'Sheet1' },
      userId:      { type: 'string' }
    },
    required: ['description']
  }
});

const mcpExcelCompare = wrap(new ExcelCompareTool(), {
  name: 'excel.compare',
  description: '对比两个 Excel 文件的差异',
  category: 'excel', icon: '🔍',
  inputSchema: {
    type: 'object',
    properties: {
      filePathA: { type: 'string' },
      filePathB: { type: 'string' },
      sheetName: { type: 'string', default: 'Sheet1' },
      keyColumn: { type: 'string', default: 'A' }
    },
    required: ['filePathA', 'filePathB']
  }
});

/* ─── PPT 工具集 ──────────────────────────────────────────── */
const mcpPptOutline = wrap(new PPTOutlineTool(), {
  name: 'ppt.outline',
  description: '根据正文内容生成 PPT 大纲（JSON 数组）',
  category: 'ppt', icon: '📝',
  inputSchema: {
    type: 'object',
    properties: {
      content:  { type: 'string' },
      template: { type: 'string', default: '通用' },
      userId:   { type: 'string' }
    },
    required: ['content']
  }
});

const mcpPptGenerate = wrap(new PPTGenerateTool(), {
  name: 'ppt.generate',
  description: '根据大纲生成 PPTX 文件，返回文件路径',
  category: 'ppt', icon: '🎯',
  inputSchema: {
    type: 'object',
    properties: {
      slides:    { type: 'array' },
      title:     { type: 'string' },
      outputDir: { type: 'string' }
    },
    required: ['slides']
  }
});

/* ─── 新增：文档读取工具 ──────────────────────────────────── */
const mcpFileRead = {
  name:        'fs.readText',
  description: '读取本地文本文件内容（限制在 backend/exports 与 backend/uploads 目录下）',
  category:    'fs',
  icon:        '📄',
  source:      'builtin',
  inputSchema: {
    type: 'object',
    properties: { filePath: { type: 'string' } },
    required: ['filePath']
  },
  handler: async (input) => {
    const abs = path.resolve(input.filePath);
    const allowedDirs = [
      path.resolve(__dirname, '../../uploads'),
      path.resolve(__dirname, '../../exports'),
      path.resolve(__dirname, '../../data')
    ];
    const allowed = allowedDirs.some(d => abs.startsWith(d));
    if (!allowed) throw new Error('沙箱拒绝：仅允许访问 uploads / exports / data 目录');
    if (!fs.existsSync(abs)) throw new Error('文件不存在');
    const stat = fs.statSync(abs);
    if (stat.size > 2 * 1024 * 1024) throw new Error('文件超过 2MB');
    const content = fs.readFileSync(abs, 'utf-8');
    return { content, size: stat.size, path: abs };
  }
};

/* ─── 新增：搜索占位工具（实际由 AI 模拟回答） ─────────────── */
const mcpSearch = {
  name:        'web.search',
  description: '联网搜索（演示版：通过 AI 总结公开知识，不实际抓取）',
  category:    'web',
  icon:        '🔎',
  source:      'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      query:  { type: 'string' },
      userId: { type: 'string' }
    },
    required: ['query']
  },
  handler: async (input) => {
    return {
      query:   input.query,
      results: [
        { title: '说明', snippet: `演示模式：未联网，请在 AI 对话中通过 ai.chat 让模型回答 "${input.query}"。` }
      ],
      note: 'web.search 为占位工具。生产环境请接入 brave-search/serper 等 MCP server。'
    };
  }
};

/* ─── 新增：基础数学工具（演示沙箱） ──────────────────────── */
const mcpMath = {
  name:        'math.eval',
  description: '安全求值简单数学表达式（仅支持数字、+-*/()和小数）',
  category:    'utility',
  icon:        '➗',
  source:      'builtin',
  inputSchema: {
    type: 'object',
    properties: { expression: { type: 'string' } },
    required: ['expression']
  },
  handler: async (input) => {
    const expr = String(input.expression || '');
    if (!/^[\d\s+\-*/().]+$/.test(expr)) throw new Error('表达式含非法字符');
    // eslint-disable-next-line no-new-func
    const value = Function(`"use strict"; return (${expr});`)();
    if (typeof value !== 'number' || !isFinite(value)) throw new Error('计算结果非有限数');
    return { expression: expr, result: value };
  }
};

/* ─── 新增：素材矢量图形编排（打通生成时复用素材图形） ─────── */
const mcpPptComposeGraphics = {
  name:        'ppt.compose_graphics',
  description: '按每页语义从全部可见素材库自主选择矢量图形，完成图文组合编排；materialId 可选，素材无匹配时使用系统内置可编辑矢量组件兜底',
  category:    'ppt',
  icon:        '🧩',
  source:      'builtin',
  inputSchema: {
    type: 'object',
    properties: {
      pptJson:    { type: 'object', description: 'PPT 结构（含 slides）' },
      materialId: { type: 'string', description: '可选：限定使用某个素材库条目；留空则从全部可见素材自主选择' },
      maxSlides:  { type: 'number', default: 3 },
      allowBuiltin: { type: 'boolean', default: true, description: '素材无匹配时是否允许使用系统内置可编辑矢量组件' },
      colors: { type: 'object', description: '内置矢量组件的配色覆盖（primary/secondary/accent）' },
      userId:     { type: 'string' },
      isAdmin:    { type: 'boolean' }
    },
    required: ['pptJson']
  },
  handler: async (input) => {
    const composer = require('../../services/ppt/graphicComposer');
    const pptJson = input.pptJson || {};
    const res = composer.composeAutonomously(pptJson,
      { userId: input.userId, isAdmin: input.isAdmin === true },
      {
        materialId: input.materialId || undefined,
        maxSlides: input.maxSlides || 3,
        allowLibrary: true,
        allowBuiltin: input.allowBuiltin !== false,
        colors: input.colors || {},
      });
    return {
      applied: res.applied || [],
      skipped: res.skipped || null,
      libraryComponentCount: res.libraryComponentCount || 0,
      builtinComponentCount: res.builtinComponentCount || 0,
      pptJson,
    };
  }
};

const { ALL_GIT_TOOLS }          = require('./gitTool');
const { ALL_GITHUB_TOOLS }       = require('./githubTool');
const { ALL_OFFICE_TOOLS }       = require('./officeTool');
const { ALL_HTML_PPT_TOOLS }     = require('./htmlPptTool');
const { ALL_MANAGEMENT_TOOLS }   = require('./excelManagement');
const { ALL_PPT_VECTOR_TOOLS }   = require('./pptVectorTools');

module.exports = {
  ALL_BUILTIN_TOOLS: [
    mcpAITool,
    mcpRAGTool,
    mcpExcelFormula, mcpExcelClean, mcpExcelChart, mcpExcelPivot, mcpExcelCompare,
    mcpPptOutline,   mcpPptGenerate, mcpPptComposeGraphics,
    mcpFileRead,     mcpSearch, mcpMath,
    ...ALL_GIT_TOOLS,
    ...ALL_GITHUB_TOOLS,
    ...ALL_OFFICE_TOOLS,
    ...ALL_HTML_PPT_TOOLS,
    ...ALL_MANAGEMENT_TOOLS
    , ...ALL_PPT_VECTOR_TOOLS
  ]
};
