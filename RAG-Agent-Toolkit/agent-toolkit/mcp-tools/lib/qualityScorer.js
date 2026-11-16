/**
 * QualityScorer — 分块质量评分器（0-100）
 *
 * 多维度评估：
 *   length      — 长度适中性（太短或太长扣分）
 *   density     — 信息密度（有效字符比例）
 *   completeness — 语义完整性（句子是否完整）
 *   uniqueness  — 内容多样性（去重词比例）
 */
class QualityScorer {
  /**
   * 返回总分 (0-100 整数)
   */
  score(text) {
    if (!text || typeof text !== 'string' || !text.trim()) return 0;
    const report = this.evaluate(text);
    return report.score;
  }

  /**
   * 返回详细评分报告
   */
  evaluate(text) {
    if (!text || !text.trim()) {
      return { score: 0, dimensions: { length: 0, density: 0, completeness: 0, uniqueness: 0 } };
    }

    const dims = {
      length:       this._scoreLength(text),
      density:      this._scoreDensity(text),
      completeness: this._scoreCompleteness(text),
      uniqueness:   this._scoreUniqueness(text)
    };

    // 加权平均
    const weights = { length: 0.25, density: 0.30, completeness: 0.25, uniqueness: 0.20 };
    let raw = Object.entries(dims).reduce((sum, [k, v]) => sum + v * weights[k], 0);

    // 硬性惩罚规则：任一关键维度严重不足则整体封顶
    if (text.trim().length < 20) raw = Math.min(raw, 45);   // 过短文本最高 45
    if (dims.uniqueness <= 10)   raw = Math.min(raw, 38);   // 极低多样性最高 38

    const score = Math.min(100, Math.max(0, Math.round(raw)));
    return { score, dimensions: dims };
  }

  /* ── 各维度评分 (0-100) ─────────────────────────────── */

  /** 长度适中：最优区间 100-800 字符 */
  _scoreLength(text) {
    const len = text.length;
    if (len === 0)    return 0;
    if (len < 5)      return 0;
    if (len < 20)     return 15;   // ← 明确低分
    if (len < 50)     return 35;
    if (len < 100)    return 60;
    if (len <= 800)   return 100;
    if (len <= 1200)  return 85;
    if (len <= 2000)  return 70;
    return 50;
  }

  /** 信息密度：有效内容字符占比（去除纯空白/标点） */
  _scoreDensity(text) {
    const total   = text.length;
    if (!total) return 0;

    // 有效字符：汉字、字母、数字
    const meaningful = (text.match(/[一-龥a-zA-Z0-9]/g) || []).length;
    const ratio      = meaningful / total;

    if (ratio < 0.2) return 10;
    if (ratio < 0.4) return 40;
    if (ratio < 0.6) return 70;
    return Math.min(100, Math.round(ratio * 110));
  }

  /** 完整性：末尾是否以句末标点结束（语义完整） */
  _scoreCompleteness(text) {
    const trimmed = text.trim();
    // 完整句末标点
    if (/[。！？.!?]$/.test(trimmed)) return 100;
    // 段落结束（换行 or 一般文字结束）
    if (/[一-龥a-zA-Z0-9]$/.test(trimmed)) return 75;
    // 以逗号/分号结束（不完整）
    if (/[，,；;]$/.test(trimmed)) return 40;
    return 60;
  }

  /** 内容多样性：不重复词比例，检测垃圾/重复内容 */
  _scoreUniqueness(text) {
    const words  = text.replace(/\s+/g, ' ').split(' ').filter(Boolean);
    if (!words.length) return 0;

    const unique = new Set(words);
    const ratio  = unique.size / words.length;

    // 极低多样性（大量重复词）→ 强力低分
    if (ratio < 0.20) return 5;    // ← 更严格惩罚
    if (ratio < 0.35) return 25;
    if (ratio < 0.50) return 55;
    return Math.min(100, Math.round(ratio * 105));
  }
}

module.exports = QualityScorer;
