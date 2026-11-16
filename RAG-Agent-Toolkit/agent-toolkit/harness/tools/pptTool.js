/**
 * PPT Tools — 封装 PPT 生成流程为 Harness 工具
 */
const BaseTool = require('./baseTool');

/* ── PPT 大纲生成工具 ────────────────────────────────────── */
class PPTOutlineTool extends BaseTool {
  constructor() { super('pptOutline', '根据内容生成 PPT 大纲（JSON）'); }

  async execute(input) {
    const { content, template, userId } = input;
    const { callAI } = require('../../services/aiService');
    const outline = await callAI([
      {
        role: 'system',
        content: '你是 PPT 内容设计专家。根据输入内容生成 PPT 大纲，以 JSON 数组输出，每项含 { title, bullets: string[] }，不加任何 Markdown 代码块。'
      },
      {
        role: 'user',
        content: `模板类型: ${template || '通用'}\n\n内容:\n${content}\n\n请生成 PPT 大纲（6-12 页）。`
      }
    ], { maxTokens: 2000 }, userId);

    try {
      const slides = JSON.parse(outline);
      return { slides };
    } catch {
      // 尝试从文本中提取 JSON 数组
      const match = outline.match(/\[[\s\S]*\]/);
      if (match) {
        try { return { slides: JSON.parse(match[0]) }; } catch {}
      }
      return { slides: [], rawOutline: outline };
    }
  }
}

/* ── PPT 文件生成工具 ────────────────────────────────────── */
class PPTGenerateTool extends BaseTool {
  constructor() { super('pptGenerate', '根据大纲生成 PPTX 文件'); }

  async execute(input) {
    const { slides, title = '演示文稿', outputDir } = input;
    const pptxgen = require('pptxgenjs');
    const path    = require('path');
    const fs      = require('fs');

    const ppt = new pptxgen();
    ppt.layout = 'LAYOUT_WIDE';

    // 封面
    const cover = ppt.addSlide();
    cover.addText(title, {
      x: 1, y: 2, w: '80%', h: 1.5,
      fontSize: 36, bold: true, color: '363636', align: 'center'
    });

    // 内容页
    for (const slide of (slides || [])) {
      const s = ppt.addSlide();
      s.addText(slide.title || '（无标题）', {
        x: 0.5, y: 0.3, w: '90%', h: 0.8,
        fontSize: 24, bold: true, color: '2E4057'
      });

      const bullets = (slide.bullets || []).map(b => ({ text: b, options: { bullet: true } }));
      if (bullets.length) {
        s.addText(bullets, {
          x: 0.5, y: 1.2, w: '90%', h: 4.5,
          fontSize: 16, color: '404040', valign: 'top'
        });
      }
    }

    const dir = outputDir || path.join(__dirname, '../../../backend/exports/ppt');
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

    const fileName = `harness_ppt_${Date.now()}.pptx`;
    const filePath = path.join(dir, fileName);
    await ppt.writeFile({ fileName: filePath });

    return { filePath, fileName };
  }
}

module.exports = { PPTOutlineTool, PPTGenerateTool };
