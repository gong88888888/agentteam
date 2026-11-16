/**
 * ChunkingEngine — 语义分块引擎
 * 功能：
 * - chunkText()     — 语义感知分块（保持句子完整 + 重叠）
 * - chunkMarkdown() — 标题层级感知分块
 * - chunkByParagraph() — 段落分块
 * 无外部依赖
 */
const crypto = require('crypto');

const DEFAULT_MAX_SIZE  = 512;  // 字符数（约等于 ~256 CJK token 或 ~128 English token）
const DEFAULT_OVERLAP   = 0.15; // 重叠比例 15%

class ChunkingEngine {
  /**
   * 通用文本语义分块
   * @param {string} text
   * @param {{ maxSize?, overlap?, docType? }} opts
   * @returns {Array<{id,index,start,end,text,charCount}>}
   */
  chunkText(text, opts = {}) {
    if (!text || typeof text !== 'string') return [];

    const maxSize    = opts.maxSize    ?? DEFAULT_MAX_SIZE;
    const overlapPct = opts.overlap    ?? DEFAULT_OVERLAP;
    const overlapLen = Math.floor(maxSize * overlapPct);

    // 1. 分句（保留分隔符）
    const sentences = this._splitSentences(text);
    if (!sentences.length) return [];

    const chunks = [];
    let current  = '';
    let startPos = 0;
    let charPos  = 0;

    for (const sentence of sentences) {
      if (current.length + sentence.length > maxSize && current.trim()) {
        const chunkStart = startPos;
        const chunkEnd   = startPos + current.length;
        chunks.push(this._makeChunk(current.trim(), chunks.length, chunkStart, chunkEnd));

        // 重叠：取末尾 overlapLen 字符重新开始
        const overlapText = overlapLen > 0 ? this._getOverlapText(current, overlapLen) : '';
        startPos = chunkEnd - overlapText.length;
        current  = overlapText + sentence;
      } else {
        current += sentence;
      }
      charPos += sentence.length;
    }

    if (current.trim()) {
      chunks.push(this._makeChunk(current.trim(), chunks.length, startPos, startPos + current.length));
    }

    return chunks;
  }

  /**
   * Markdown 标题感知分块
   * 每个 H1/H2 形成独立块，H3+ 附属到父块
   * @param {string} markdown
   * @returns {Array<{id,index,title,level,text,charCount}>}
   */
  chunkMarkdown(markdown) {
    if (!markdown) return [];

    const lines   = markdown.split('\n');
    const chunks  = [];
    let curTitle  = '';
    let curLevel  = 0;
    let curLines  = [];

    const flush = () => {
      const text = curLines.join('\n').trim();
      if (text) {
        chunks.push({
          ...this._makeChunk(text, chunks.length, 0, text.length),
          title: curTitle,
          level: curLevel
        });
      }
      curLines = [];
    };

    for (const line of lines) {
      const m = line.match(/^(#{1,6})\s+(.+)/);
      if (m) {
        const level = m[1].length;
        const title = m[2];

        // H1 or H2 → flush and start new block
        if (level <= 2) {
          flush();
          curTitle = title;
          curLevel = level;
          curLines = [line];
        } else {
          // H3+ appended to current block
          curLines.push(line);
        }
      } else {
        curLines.push(line);
      }
    }
    flush();

    return chunks;
  }

  /**
   * 段落分块（空行分隔）
   */
  chunkByParagraph(text, opts = {}) {
    if (!text) return [];
    const maxSize = opts.maxSize ?? DEFAULT_MAX_SIZE;
    const paras   = text.split(/\n{2,}/).map(p => p.trim()).filter(Boolean);

    const chunks  = [];
    let buffer    = '';
    let startPos  = 0;

    for (const para of paras) {
      if (buffer.length + para.length + 2 > maxSize && buffer) {
        chunks.push(this._makeChunk(buffer.trim(), chunks.length, startPos, startPos + buffer.length));
        startPos += buffer.length;
        buffer = para + '\n\n';
      } else {
        buffer += (buffer ? '\n\n' : '') + para;
      }
    }
    if (buffer.trim()) {
      chunks.push(this._makeChunk(buffer.trim(), chunks.length, startPos, startPos + buffer.length));
    }
    return chunks;
  }

  /* ── Helpers ─────────────────────────────────────────── */
  _splitSentences(text) {
    // 中英文句末标点 + 换行作为分句点
    const parts = [];
    let last = 0;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if ('。！？.!?\n'.includes(ch)) {
        parts.push(text.slice(last, i + 1));
        last = i + 1;
      }
    }
    if (last < text.length) parts.push(text.slice(last));
    return parts.filter(s => s.trim());
  }

  _getOverlapText(text, overlapLen) {
    if (!text || overlapLen <= 0) return '';
    const slice = text.slice(-overlapLen);
    // 尝试从句子边界开始
    const boundary = slice.search(/[。！？.!?\n]/);
    return boundary >= 0 && boundary < slice.length - 5 ? slice.slice(boundary + 1) : slice;
  }

  _makeChunk(text, index, start, end) {
    return {
      id:        this._chunkId(text, index),
      index,
      start,
      end,
      text,
      charCount: text.length
    };
  }

  _chunkId(text, index) {
    const hash = crypto.createHash('md5').update(text.slice(0, 64) + index).digest('hex').slice(0, 12);
    return `chunk_${index}_${hash}`;
  }
}

module.exports = ChunkingEngine;
