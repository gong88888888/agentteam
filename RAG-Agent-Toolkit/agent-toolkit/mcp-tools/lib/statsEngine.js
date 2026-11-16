/**
 * StatsEngine — 纯 JS 统计算法引擎
 * 无外部依赖，实现：
 *   linearRegression   — 简单线性回归 (OLS)
 *   pearsonCorrelation — 皮尔逊相关系数
 *   detectAnomalies    — IQR + Z-score 异常检测
 *   exponentialSmoothing — 指数平滑时间序列
 *   kMeansClustering   — K-Means 聚类
 *   anovaFTest         — 单因素方差分析 F 检验
 *   descriptiveStats   — 描述性统计
 */
class StatsEngine {

  /* ── 线性回归 ─────────────────────────────────────── */
  linearRegression(xArr, yArr) {
    const n = xArr.length;
    if (n < 2 || n !== yArr.length) throw new Error('x 和 y 长度必须相同且 ≥ 2');

    const meanX = this._mean(xArr);
    const meanY = this._mean(yArr);
    let   sxy   = 0, sxx = 0;

    for (let i = 0; i < n; i++) {
      sxy += (xArr[i] - meanX) * (yArr[i] - meanY);
      sxx += (xArr[i] - meanX) ** 2;
    }

    const slope     = sxx === 0 ? 0 : sxy / sxx;
    const intercept = meanY - slope * meanX;

    // R² coefficient of determination
    const ssRes = yArr.reduce((s, y, i) => s + (y - (slope * xArr[i] + intercept)) ** 2, 0);
    const ssTot = yArr.reduce((s, y)    => s + (y - meanY) ** 2, 0);
    const r2    = ssTot === 0 ? 1 : Math.max(0, 1 - ssRes / ssTot);

    return {
      slope:     +slope.toFixed(6),
      intercept: +intercept.toFixed(6),
      r2:        +r2.toFixed(6),
      equation:  `y = ${slope.toFixed(4)}x + ${intercept.toFixed(4)}`,
      predict:   (x) => slope * x + intercept
    };
  }

  /* ── 皮尔逊相关系数 ────────────────────────────────── */
  pearsonCorrelation(xArr, yArr) {
    const n = xArr.length;
    if (n !== yArr.length || n < 2) throw new Error('数组长度必须相同且 ≥ 2');

    const meanX = this._mean(xArr);
    const meanY = this._mean(yArr);
    let   num   = 0, denX = 0, denY = 0;

    for (let i = 0; i < n; i++) {
      const dx = xArr[i] - meanX;
      const dy = yArr[i] - meanY;
      num  += dx * dy;
      denX += dx * dx;
      denY += dy * dy;
    }

    const den = Math.sqrt(denX * denY);
    return den === 0 ? 0 : +(num / den).toFixed(6);
  }

  /* ── 异常检测（IQR 方法 + Z-Score 辅助） ──────────── */
  detectAnomalies(data, { method = 'iqr', zThreshold = 2.5 } = {}) {
    const sorted = [...data].sort((a, b) => a - b);
    const n = sorted.length;
    const q1 = this._percentile(sorted, 25);
    const q3 = this._percentile(sorted, 75);
    const iqr = q3 - q1;
    const lower  = q1 - 1.5 * iqr;
    const upper  = q3 + 1.5 * iqr;

    const mean  = this._mean(data);
    const std   = this._std(data);

    const anomalies = data
      .map((v, i) => {
        const zScore    = std === 0 ? 0 : Math.abs(v - mean) / std;
        const isIqr     = v < lower || v > upper;
        const isZScore  = zScore > zThreshold;
        const isAnomaly = method === 'iqr' ? isIqr : (isIqr || isZScore);
        return isAnomaly ? { index: i, value: v, zScore: +zScore.toFixed(3) } : null;
      })
      .filter(Boolean);

    return { anomalies, lower: +lower.toFixed(4), upper: +upper.toFixed(4),
             q1: +q1.toFixed(4), q3: +q3.toFixed(4) };
  }

  /* ── 指数平滑 ─────────────────────────────────────── */
  exponentialSmoothing(data, alpha = 0.3, forecastSteps = 1) {
    if (!data.length) throw new Error('数据不能为空');
    const smoothed = [data[0]];
    for (let i = 1; i < data.length; i++) {
      smoothed.push(alpha * data[i] + (1 - alpha) * smoothed[i - 1]);
    }
    let last = smoothed[smoothed.length - 1];
    const forecasts = [];
    for (let i = 0; i < forecastSteps; i++) {
      last = alpha * last + (1 - alpha) * last; // level forecast
      forecasts.push(+last.toFixed(4));
    }
    return { smoothed: smoothed.map(v => +v.toFixed(4)), forecast: forecasts[0] ?? null, forecasts };
  }

  /* ── K-Means 聚类 ─────────────────────────────────── */
  kMeansClustering(points, k, maxIter = 100) {
    if (points.length < k) throw new Error(`数据点数量 ${points.length} 少于聚类数 ${k}`);
    const dim = points[0].length;

    // 随机初始化质心（取前 k 个不同点）
    let centroids = points.slice(0, k).map(p => [...p]);
    let assignments = new Array(points.length).fill(0);

    for (let iter = 0; iter < maxIter; iter++) {
      // 分配
      const newAssign = points.map(p =>
        this._argMin(centroids.map(c => this._euclidean(p, c)))
      );

      // 检查收敛
      const changed = newAssign.some((a, i) => a !== assignments[i]);
      assignments = newAssign;
      if (!changed) break;

      // 更新质心
      for (let c = 0; c < k; c++) {
        const members = points.filter((_, i) => assignments[i] === c);
        if (members.length > 0) {
          centroids[c] = Array.from({ length: dim }, (_, d) =>
            members.reduce((s, p) => s + p[d], 0) / members.length
          );
        }
      }
    }

    const clusters = Array.from({ length: k }, (_, c) => ({
      id: c, centroid: centroids[c],
      members: points.filter((_, i) => assignments[i] === c)
    }));

    return { clusters, assignments, k };
  }

  /* ── 单因素 ANOVA F 检验 ───────────────────────────── */
  anovaFTest(groups) {
    const allData  = groups.flat();
    const n        = allData.length;
    const grandMean = this._mean(allData);

    // SS between groups
    const ssBetween = groups.reduce((s, g) => {
      return s + g.length * (this._mean(g) - grandMean) ** 2;
    }, 0);

    // SS within groups
    const ssWithin = groups.reduce((s, g) => {
      const gMean = this._mean(g);
      return s + g.reduce((gs, v) => gs + (v - gMean) ** 2, 0);
    }, 0);

    const dfBetween = groups.length - 1;
    const dfWithin  = n - groups.length;

    if (dfBetween === 0 || dfWithin === 0 || ssWithin === 0) {
      return { fStatistic: 0, pValue: 1, significant: false, dfBetween, dfWithin };
    }

    const msBetween = ssBetween / dfBetween;
    const msWithin  = ssWithin  / dfWithin;
    const fStatistic = msBetween / msWithin;

    // Approximation: significant if F > critical value ~4 for typical df
    const pValue     = this._fPValueApprox(fStatistic, dfBetween, dfWithin);
    const significant = pValue < 0.05;

    return { fStatistic: +fStatistic.toFixed(4), pValue: +pValue.toFixed(4), significant,
             dfBetween, dfWithin, msBetween: +msBetween.toFixed(4), msWithin: +msWithin.toFixed(4) };
  }

  /* ── 描述性统计 ───────────────────────────────────── */
  descriptiveStats(data) {
    if (!data.length) return {};
    const sorted = [...data].sort((a, b) => a - b);
    const n      = sorted.length;
    const mean   = this._mean(data);
    const std    = this._std(data);
    const median = n % 2 === 0
      ? (sorted[n / 2 - 1] + sorted[n / 2]) / 2
      : sorted[Math.floor(n / 2)];

    return {
      n, mean: +mean.toFixed(4), std: +std.toFixed(4), median: +median.toFixed(4),
      min: sorted[0], max: sorted[n - 1],
      q1: +this._percentile(sorted, 25).toFixed(4),
      q3: +this._percentile(sorted, 75).toFixed(4),
      skewness: +this._skewness(data, mean, std).toFixed(4)
    };
  }

  /* ── 私有辅助方法 ─────────────────────────────────── */
  _mean(arr)  { return arr.reduce((s, v) => s + v, 0) / arr.length; }
  _std(arr)   { const m = this._mean(arr); return Math.sqrt(arr.reduce((s,v) => s+(v-m)**2, 0) / arr.length); }
  _argMin(arr){ let mi=0; for(let i=1;i<arr.length;i++) if(arr[i]<arr[mi]) mi=i; return mi; }
  _euclidean(a,b){ return Math.sqrt(a.reduce((s,v,i)=>s+(v-b[i])**2,0)); }

  _percentile(sortedArr, p) {
    const idx = (p / 100) * (sortedArr.length - 1);
    const lo  = Math.floor(idx);
    const hi  = Math.ceil(idx);
    return sortedArr[lo] + (sortedArr[hi] - sortedArr[lo]) * (idx - lo);
  }

  _skewness(arr, mean, std) {
    if (std === 0) return 0;
    return arr.reduce((s, v) => s + ((v - mean) / std) ** 3, 0) / arr.length;
  }

  // Rough F p-value approximation (sufficient for reporting)
  _fPValueApprox(f, df1, df2) {
    if (f <= 0) return 1;
    // Wilson-Hilferty approximation
    const p = 1 - this._fCdf(f, df1, df2);
    return Math.max(0, Math.min(1, p));
  }

  _fCdf(f, d1, d2) {
    const x = d1 * f / (d1 * f + d2);
    return this._incompleteBeta(x, d1 / 2, d2 / 2);
  }

  _incompleteBeta(x, a, b) {
    // Simple series approximation
    if (x < 0 || x > 1) return 0;
    if (x === 0) return 0;
    if (x === 1) return 1;
    let sum = 0, term = 1;
    for (let n = 0; n < 200; n++) {
      if (n > 0) term *= (n - 1 - b) * x / n;
      sum += term / (a + n);
      if (Math.abs(term) < 1e-8) break;
    }
    return Math.min(1, Math.max(0, sum * Math.pow(x, a) * Math.pow(1 - x, b)));
  }
}

module.exports = StatsEngine;
