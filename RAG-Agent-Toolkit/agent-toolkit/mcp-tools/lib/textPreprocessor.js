/**
 * TextPreprocessor — 文本预处理管道
 * 无外部依赖，纯 Node.js 实现
 */
class TextPreprocessor {
  /**
   * 完整预处理管道
   */
  process(text) {
    if (!text) return '';
    return this.clean(this.normalizeWhitespace(text));
  }

  /**
   * 统一换行符为 \n
   */
  normalizeWhitespace(text) {
    if (!text) return '';
    return text
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n');
  }

  /**
   * 深度清洗：
   * - 去除控制字符（保留 \n \t）
   * - 多空格合并为单空格
   * - 超过 2 个连续空行合并为 1 个
   * - 去除行尾空格
   */
  clean(text) {
    if (!text) return '';
    let t = text
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .replace(/[​-‍⁠﻿]/g, '')                     // 零宽字符 / BOM
      .replace(/　/g, ' ')                                    // 全角空格→普通空格
      .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')   // 控制字符（保留 \t \n）
      .replace(/[^\S\n]+/g, ' ');                            // 多空格→单空格（不含换行）
    // 先逐行去首尾空白（空白行→空串），再合并空行——杜绝空格占位的空白行残留
    t = t.split('\n').map(line => line.trim()).join('\n');
    return t.replace(/\n{3,}/g, '\n\n').trim();              // 3+空行→1空行
  }

  /**
   * 去除 PDF 常见页眉页脚/页码模式
   * 识别并删除如：
   *   "第 3 页"  "- 10 -"  "Page 5 of 20"  "第X页/共Y页"
   */
  removePageArtifacts(text) {
    if (!text) return '';
    const patterns = [
      /^第\s*\d+\s*页\s*$/gm,              // 第 3 页
      /^[-—–]\s*\d+\s*[-—–]\s*$/gm,       // - 10 -
      /^Page\s+\d+\s*(of\s+\d+)?\s*$/gmi, // Page 5 of 20
      /^第\s*\d+\s*页\s*\/?\s*共\s*\d+\s*页\s*$/gm,  // 第X页/共Y页
      /^\d+\s*\/\s*\d+\s*$/gm,            // 1/20
      /^www\.[^\s]+\s*$/gm,               // URL 页脚
      /^©.{0,80}$/gm                      // 版权行
    ];
    let result = text;
    for (const p of patterns) {
      result = result.replace(p, '');
    }
    return this.clean(result);
  }

  /**
   * 提取纯文本（去除 Markdown 格式符号用于分析）
   */
  stripMarkdown(text) {
    if (!text) return '';
    return text
      .replace(/^#{1,6}\s+/gm, '')        // 标题符号
      .replace(/\*\*(.+?)\*\*/g, '$1')    // 粗体
      .replace(/\*(.+?)\*/g, '$1')        // 斜体
      .replace(/`{1,3}[^`]*`{1,3}/g, '') // 代码
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // 链接
      .replace(/^[-*+]\s+/gm, '')         // 列表符号
      .replace(/^>\s*/gm, '')             // 引用
      .trim();
  }
}

module.exports = TextPreprocessor;
