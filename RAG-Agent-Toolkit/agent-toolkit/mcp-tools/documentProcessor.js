/**
 * document-processor — 文档处理 MCP 工具 (Module 2 升级版)
 *
 * Module 1 Action（保持完全兼容）：
 *   tokenize   — 分词
 *   stats      — 文本统计
 *   info       — 工具信息
 *   extract    — 关键词提取
 *
 * Module 2 新增 Action：
 *   split_document         — 分词切分单个文档 (TXT/MD/PDF/DOCX/XLSX)
 *   get_chunk_info         — 获取缓存分块详情
 *   evaluate_chunk_quality — 评估分块质量 (0-100)
 *   batch_process          — 批量处理多个文档
 */
const BaseMcpTool      = require('./baseMcpTool');
const ChunkingEngine   = require('./lib/chunkingEngine');
const QualityScorer    = require('./lib/qualityScorer');
const DocumentParser   = require('./lib/documentParser');
const TextPreprocessor = require('./lib/textPreprocessor');

const engine   = new ChunkingEngine();
const scorer   = new QualityScorer();
const parser   = new DocumentParser();
const preproc  = new TextPreprocessor();

/** 内存分块缓存 chunkId → chunk 对象（重启清空，Module 3 可持久化到 SQLite） */
const _chunkCache = new Map();
const CACHE_MAX   = 5000; // 防止内存泄漏

class DocumentProcessor extends BaseMcpTool {
  constructor() {
    super(
      'document-processor',
      '文档智能处理工具：多格式解析/语义分块/质量评分/批量处理（支持 TXT/MD/PDF/DOCX/XLSX）',
      {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['tokenize','stats','info','extract',
                   'split_document','get_chunk_info','evaluate_chunk_quality','batch_process'],
            description: '处理动作'
          },
          text:      { type: 'string',  description: '待处理文本' },
          filePath:  { type: 'string',  description: '文件路径（split_document）' },
          filePaths: { type: 'array',   items: { type: 'string' }, description: '文件路径数组（batch_process）' },
          chunkId:   { type: 'string',  description: '分块 ID（get_chunk_info）' },
          options: {
            type: 'object',
            description: '分块参数 { maxSize:512, overlap:0.15 }'
          }
        },
        required: ['action']
      }
    );
  }

  async execute(input) {
    const { action, text = '', filePath, filePaths, chunkId, options = {} } = input;

    switch (action) {
      /* ── Module 1 兼容动作 ───────────────────────────── */
      case 'info':
        return {
          name:    this.name,
          version: '2.0.0',
          status:  'active',
          message: 'Module 2 已就绪：完整分词切分引擎',
          capabilities: ['tokenize','stats','extract',
                         'split_document','get_chunk_info','evaluate_chunk_quality','batch_process'],
          supportedFormats: ['txt','md','pdf','docx','xlsx','csv'],
          cacheSize: _chunkCache.size
        };

      case 'tokenize':         return this._tokenize(text, options);
      case 'stats':            return this._stats(text);
      case 'extract':          return this._extractKeywords(text, options.maxKeywords || 10);

      /* ── Module 2 新增动作 ───────────────────────────── */
      case 'split_document':
        return this._splitDocument(filePath, options);

      case 'get_chunk_info':
        return this._getChunkInfo(chunkId);

      case 'evaluate_chunk_quality':
        return this._evaluateQuality(text);

      case 'batch_process':
        return this._batchProcess(filePaths || [], options);

      default:
        throw new Error(`不支持的 action: ${action}`);
    }
  }

  /* ══════════════ Module 2 核心实现 ══════════════════════ */

  /** 切分单个文档 */
  async _splitDocument(filePath, options = {}) {
    if (!filePath) throw new Error('split_document 需要 filePath');

    const parsed = await parser.parse(filePath);

    // 按格式选择最优分块策略
    let chunks;
    if (parsed.format === 'md') {
      // 用原始 MD 文本（含 # 标记）驱动标题感知分块
      const mdSource = parsed.rawText || parsed.text;
      chunks = engine.chunkMarkdown(mdSource);
      // 若 MD 分块过少（无标题结构）则回退语义分块
      if (chunks.length <= 1 && parsed.text.length > (options.maxSize || 512)) {
        chunks = engine.chunkText(parsed.text, options);
      }
    } else if (parsed.format === 'xlsx' || parsed.format === 'csv') {
      // 表格类：段落分块更合适
      chunks = engine.chunkByParagraph(parsed.text, options);
    } else {
      chunks = engine.chunkText(parsed.text, options);
    }

    // 质量评分 + 写入缓存
    const scored = chunks.map(c => {
      const q       = scorer.evaluate(c.text);
      const enriched = { ...c, quality: q.score, qualityDims: q.dimensions, format: parsed.format };
      this._cacheChunk(c.id, enriched);
      return enriched;
    });

    return {
      filePath,
      format:      parsed.format,
      totalChunks: scored.length,
      charCount:   parsed.charCount,
      wordCount:   parsed.wordCount,
      avgQuality:  scored.length
        ? Math.round(scored.reduce((s, c) => s + c.quality, 0) / scored.length)
        : 0,
      chunks: scored,
      meta: parsed.meta
    };
  }

  /** 获取缓存分块 */
  _getChunkInfo(chunkId) {
    if (!chunkId) throw new Error('get_chunk_info 需要 chunkId');
    const chunk = _chunkCache.get(chunkId);
    if (!chunk) throw new Error(`分块 "${chunkId}" 不存在（缓存已过期或 chunkId 有误）`);
    return chunk;
  }

  /** 质量评估 */
  _evaluateQuality(text) {
    if (!text) throw new Error('evaluate_chunk_quality 需要 text');
    return scorer.evaluate(text);
  }

  /** 批量处理 */
  async _batchProcess(filePaths, options = {}) {
    if (!Array.isArray(filePaths) || !filePaths.length) {
      throw new Error('batch_process 需要非空的 filePaths 数组');
    }
    const results      = [];
    let totalChunks    = 0;
    let processedFiles = 0;
    let failedFiles    = 0;

    for (const fp of filePaths) {
      try {
        const r = await this._splitDocument(fp, options);
        results.push({ filePath: fp, success: true, ...r });
        totalChunks    += r.totalChunks;
        processedFiles++;
      } catch (e) {
        results.push({ filePath: fp, success: false, error: e.message });
        failedFiles++;
      }
    }
    return { results, totalChunks, processedFiles, failedFiles };
  }

  /** 缓存分块（超限时淘汰最旧的） */
  _cacheChunk(id, data) {
    if (_chunkCache.size >= CACHE_MAX) {
      const firstKey = _chunkCache.keys().next().value;
      _chunkCache.delete(firstKey);
    }
    _chunkCache.set(id, data);
  }

  /* ══════════════ Module 1 兼容实现 ══════════════════════ */

  _tokenize(text, options = {}) {
    if (!text) return { tokens: [], count: 0 };
    const cleaned = preproc.process(text);
    const tokens  = cleaned
      .replace(/[，。！？；：""''《》【】、]/g, ' ')
      .replace(/[,.!?;:'"<>[\]]/g, ' ')
      .split(/\s+/)
      .filter(t => t.trim().length > 0);
    return {
      tokens,
      count:       tokens.length,
      uniqueCount: new Set(tokens).size,
      language:    options.language || this._detectLanguage(text)
    };
  }

  _stats(text) {
    if (!text) return { chars: 0, words: 0, sentences: 0, paragraphs: 0 };
    const chars      = text.length;
    const words      = text.split(/\s+/).filter(Boolean).length;
    const sentences  = (text.match(/[。！？.!?]/g) || []).length || 1;
    const paragraphs = text.split(/\n{2,}/).filter(p => p.trim()).length || 1;
    return {
      chars, words, sentences, paragraphs,
      avgWordPerSentence:    +(words / sentences).toFixed(1),
      estimatedReadMinutes:  +(words / 250).toFixed(1),
      language: this._detectLanguage(text)
    };
  }

  _extractKeywords(text, maxKeywords = 10) {
    if (!text) return { keywords: [] };
    const STOPWORDS = new Set([
      '的','了','是','在','我','有','和','就','不','人','都','一','一个','上','也','很','到','说','要','去',
      'the','a','an','is','are','was','were','in','on','at','to','for','of','and','or','it','this','that'
    ]);
    const tokens = text.toLowerCase()
      .replace(/[^\w一-龥\s]/g, ' ').split(/\s+/)
      .filter(t => t.length > 1 && !STOPWORDS.has(t));
    const freq = {};
    for (const t of tokens) freq[t] = (freq[t] || 0) + 1;
    const keywords = Object.entries(freq)
      .sort(([, a], [, b]) => b - a).slice(0, maxKeywords)
      .map(([word, count]) => ({ word, count, score: +(count / tokens.length).toFixed(4) }));
    return { keywords, totalTokens: tokens.length };
  }

  _detectLanguage(text) {
    const cn = (text.match(/[一-龥]/g) || []).length;
    return cn / Math.max(text.length, 1) > 0.1 ? 'zh' : 'en';
  }
}

module.exports = DocumentProcessor;
