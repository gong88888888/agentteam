/**
 * MCP 智能体演示用例（8 个）
 * 前端"一键演示"专区使用
 */
module.exports = [
  {
    id: 'demo-1', icon: '📊',
    title: '销售数据 → 月度报告 PPT',
    prompt: '分析我上传的销售数据 Excel（示例文件 sales.xlsx），生成一份月度销售分析的 PPT 大纲',
    expectedTools: ['excel.formula', 'ppt.outline'],
    category: 'business'
  },
  {
    id: 'demo-2', icon: '📑',
    title: 'PDF 合同 → 摘要',
    prompt: '读取一份合同文档，提取关键条款，生成不超过 300 字的摘要',
    expectedTools: ['rag.context', 'ai.chat'],
    category: 'legal'
  },
  {
    id: 'demo-3', icon: '💰',
    title: '员工信息 → 年终奖 + 工资条',
    prompt: '根据员工信息表，计算每个人的年终奖（基本工资 × 2 + 绩效奖金），并按部门分组',
    expectedTools: ['excel.formula', 'excel.pivot'],
    category: 'hr'
  },
  {
    id: 'demo-4', icon: '🔎',
    title: '行业数据 → 市场分析',
    prompt: '搜索 2026 年中国新能源汽车市场的最新数据，生成市场分析报告',
    expectedTools: ['web.search', 'ai.chat'],
    category: 'research'
  },
  {
    id: 'demo-5', icon: '📄',
    title: 'Word → PPT',
    prompt: '把这份 Word 文档的核心观点转成 8 页 PPT 大纲，每页 3 个要点',
    expectedTools: ['rag.context', 'ppt.outline', 'ppt.generate'],
    category: 'document'
  },
  {
    id: 'demo-6', icon: '🧹',
    title: '脏数据清洗',
    prompt: '清洗这份 Excel：去除空白行、去前后空格、统一大小写',
    expectedTools: ['excel.clean'],
    category: 'data'
  },
  {
    id: 'demo-7', icon: '📈',
    title: '财务报表 → 可视化看板',
    prompt: '根据财务报表生成柱状图配置（按季度展示营收、利润、毛利率）',
    expectedTools: ['excel.chart', 'ai.chat'],
    category: 'finance'
  },
  {
    id: 'demo-8', icon: '🐍',
    title: '批量图片处理脚本',
    prompt: '生成一个 Python 脚本，批量把目录下的 PNG 图片转成 JPEG 并压缩到 80% 质量',
    expectedTools: ['ai.chat', 'code.python'],
    category: 'dev'
  },
  {
    id: 'demo-9', icon: '🔍',
    title: 'GitHub 搜索 Vue3 项目',
    prompt: '搜索 GitHub 上最新的 Vue3 开源项目（按星标排序前 5 名），生成一份分析报告',
    expectedTools: ['github.search_repos', 'ai.chat'],
    category: 'github'
  },
  {
    id: 'demo-10', icon: '🚀',
    title: '一键发布到 GitHub',
    prompt: '将一份销售分析报告的 Markdown 内容发布到我的 GitHub 仓库 docs/ 目录下，提交信息写"add sales report"',
    expectedTools: ['github.create_file'],
    category: 'github'
  },
  {
    id: 'demo-11', icon: '📂',
    title: '分析 GitHub 仓库结构',
    prompt: '分析 vuejs/core 仓库的基本信息（星标、语言、描述），生成技术文档摘要',
    expectedTools: ['github.repo_info', 'ai.chat'],
    category: 'github'
  },
  {
    id: 'demo-12', icon: '🐛',
    title: '总结 GitHub Issue',
    prompt: '获取 facebook/react 仓库的 Issue #1 的讨论内容，生成摘要和解决方案建议',
    expectedTools: ['github.get_issue', 'ai.chat'],
    category: 'github'
  }
];
