/**
 * DocumentParser — 多格式文档解析器
 * 支持：TXT / MD / PDF / DOCX / XLSX
 * 复用已有依赖：pdf-parse / mammoth / exceljs
 */
const fs   = require('fs');
const path = require('path');
const TextPreprocessor = require('./textPreprocessor');

const tp = new TextPreprocessor();

class DocumentParser {
  /**
   * 自动检测格式并解析
   * @returns {Promise<{text, format, charCount, wordCount, meta}>}
   */
  async parse(filePath) {
    if (!filePath) throw new Error('filePath 不能为空');

    const ext = path.extname(filePath).toLowerCase().slice(1);
    switch (ext) {
      case 'txt':              return this.parseTxt(filePath);
      case 'md': case 'mdx':  return this.parseMarkdown(filePath);
      case 'pdf':              return this.parsePdf(filePath);
      case 'docx': case 'doc':return this.parseDocx(filePath);
      case 'xlsx': case 'xls':return this.parseXlsx(filePath);
      case 'csv':              return this.parseCsv(filePath);
      default:
        throw new Error(`不支持的文件格式: .${ext}。支持: txt/md/pdf/docx/xlsx/csv`);
    }
  }

  /** TXT 解析 */
  async parseTxt(filePath) {
    if (!fs.existsSync(filePath)) throw new Error(`文件不存在: ${filePath}`);
    const raw  = fs.readFileSync(filePath, 'utf-8');
    const text = tp.process(raw);
    return this._result('txt', text, { rawLength: raw.length });
  }

  /** Markdown 解析（保留结构信息）
   *  rawText = 原始 MD（含 # 标记，供 chunkMarkdown 使用）
   *  text    = 纯文本版本（用于全文检索/统计）
   */
  async parseMarkdown(filePath) {
    if (!fs.existsSync(filePath)) throw new Error(`文件不存在: ${filePath}`);
    const raw = fs.readFileSync(filePath, 'utf-8');

    // 提取标题列表
    const headings = [];
    for (const line of raw.split('\n')) {
      const m = line.match(/^(#{1,6})\s+(.+)/);
      if (m) headings.push({ level: m[1].length, title: m[2].trim() });
    }

    // 纯文本版（去除 Markdown 格式符）用于统计和全文检索
    const cleaned = tp.stripMarkdown(raw);
    const text    = tp.clean(cleaned);

    const result = this._result('md', text, { headings, headingCount: headings.length, rawLength: raw.length });
    result.headings = headings;   // top-level shortcut
    result.rawText  = tp.normalizeWhitespace(raw); // 保留原始 MD 供分块使用
    return result;
  }

  /** PDF 解析（使用已安装的 pdf-parse） */
  async parsePdf(filePath) {
    if (!fs.existsSync(filePath)) throw new Error(`文件不存在: ${filePath}`);
    try {
      const pdfParse = require('pdf-parse');
      const buffer   = fs.readFileSync(filePath);
      const data     = await pdfParse(buffer);
      const text     = tp.removePageArtifacts(tp.process(data.text));
      return this._result('pdf', text, {
        pages: data.numpages,
        info:  data.info,
        rawLength: data.text.length
      });
    } catch (e) {
      throw new Error(`PDF 解析失败: ${e.message}`);
    }
  }

  /** DOCX 解析（使用 mammoth） */
  async parseDocx(filePath) {
    if (!fs.existsSync(filePath)) throw new Error(`文件不存在: ${filePath}`);
    try {
      const mammoth = require('mammoth');
      const result  = await mammoth.extractRawText({ path: filePath });
      const text    = tp.process(result.value);
      return this._result('docx', text, {
        warnings: result.messages.length,
        rawLength: result.value.length
      });
    } catch (e) {
      throw new Error(`DOCX 解析失败: ${e.message}`);
    }
  }

  /** XLSX 解析（使用 exceljs） */
  async parseXlsx(filePath) {
    if (!fs.existsSync(filePath)) throw new Error(`文件不存在: ${filePath}`);
    try {
      const ExcelJS = require('exceljs');
      const wb      = new ExcelJS.Workbook();
      await wb.xlsx.readFile(filePath);

      const sheets     = [];
      const textParts  = [];

      wb.eachSheet(ws => {
        const rows = [];
        ws.eachRow(row => {
          const vals = [];
          row.eachCell({ includeEmpty: false }, cell => {
            const v = cell.value;
            if (v !== null && v !== undefined) {
              vals.push(String(v?.result ?? v).trim());
            }
          });
          if (vals.length) rows.push(vals);
        });

        const sheetText = rows.map(r => r.join('\t')).join('\n');
        sheets.push({ name: ws.name, rowCount: rows.length, text: sheetText });
        textParts.push(`=== ${ws.name} ===\n${sheetText}`);
      });

      const text   = tp.process(textParts.join('\n\n'));
      const result = this._result('xlsx', text, { sheets, sheetCount: sheets.length });
      result.sheets = sheets;  // top-level shortcut
      return result;
    } catch (e) {
      throw new Error(`XLSX 解析失败: ${e.message}`);
    }
  }

  /** CSV 解析（内置） */
  async parseCsv(filePath) {
    if (!fs.existsSync(filePath)) throw new Error(`文件不存在: ${filePath}`);
    const raw  = fs.readFileSync(filePath, 'utf-8');
    const rows = raw.split('\n').filter(r => r.trim());
    const text = tp.process(rows.join('\n'));
    return this._result('csv', text, { rowCount: rows.length });
  }

  /* ── Helpers ─────────────────────────────────────────── */
  _result(format, text, meta = {}) {
    const words = text.split(/\s+/).filter(Boolean).length;
    return { text, format, charCount: text.length, wordCount: words, meta };
  }
}

module.exports = DocumentParser;
