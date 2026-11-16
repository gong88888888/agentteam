/**
 * knowledge-graph — 知识图谱占位符工具 (Module 1)
 *
 * 当前实现：骨架 + 简单共现关系提取（无需 graphology）
 * Module 3 将在此基础上添加：实体关系抽取、图存储、推理等
 *
 * 支持的 action：
 *   build      — 从文本构建简单共现图
 *   info       — 工具信息
 *   query      — 查询与实体相关的关系（占位）
 *   stats      — 图统计
 */
const BaseMcpTool = require('./baseMcpTool');

class KnowledgeGraph extends BaseMcpTool {
  constructor() {
    super(
      'knowledge-graph',
      '知识图谱工具：从文本提取实体关系，构建和查询知识图（Module 3 将集成 graphology 实现完整图算法）',
      {
        type: 'object',
        properties: {
          action: {
            type: 'string',
            enum: ['build', 'info', 'query', 'stats'],
            description: '图操作动作'
          },
          text: {
            type: 'string',
            description: '待分析文本（build 时必填）'
          },
          entity: {
            type: 'string',
            description: '查询实体名称（query 时使用）'
          },
          graphId: {
            type: 'string',
            description: '图 ID（用于多图管理）'
          },
          options: {
            type: 'object',
            description: '额外参数（windowSize: 共现窗口大小）'
          }
        },
        required: ['action']
      }
    );

    // 内存中的简单图存储（Module 3 将替换为 graphology）
    this._graphs = new Map();
  }

  async execute(input) {
    const { action, text = '', entity, graphId = 'default', options = {} } = input;

    switch (action) {
      case 'info':
        return {
          name:    this.name,
          version: '1.0.0',
          status:  'placeholder',
          message: '基础占位实现已就绪，Module 3 将添加完整知识图谱能力',
          graphCount: this._graphs.size,
          capabilities: ['build', 'query', 'stats'],
          plannedCapabilities: [
            'entity-relation-extraction', 'graph-algorithms',
            'semantic-reasoning', 'subgraph-search', 'graph-visualization'
          ]
        };

      case 'build':
        return this._buildGraph(graphId, text, options);

      case 'query':
        return this._queryGraph(graphId, entity);

      case 'stats':
        return this._graphStats(graphId);

      default:
        throw new Error(`不支持的 action: ${action}。可用: build, info, query, stats`);
    }
  }

  /* ── 简单共现图构建 ────────────────────────────────────── */
  _buildGraph(graphId, text, options = {}) {
    if (!text) return { nodes: [], edges: [], nodeCount: 0, edgeCount: 0 };

    const windowSize = options.windowSize || 3;

    // 简单分词
    const tokens = text
      .replace(/[^\w一-龥\s]/g, ' ')
      .split(/\s+/)
      .filter(t => t.length > 1)
      .slice(0, 200);  // 占位实现限制 200 词

    // 计算共现关系
    const nodeSet  = new Set(tokens);
    const edgeMap  = new Map(); // "a|b" → weight

    for (let i = 0; i < tokens.length; i++) {
      for (let j = i + 1; j < Math.min(i + windowSize + 1, tokens.length); j++) {
        if (tokens[i] === tokens[j]) continue;
        const key = [tokens[i], tokens[j]].sort().join('|');
        edgeMap.set(key, (edgeMap.get(key) || 0) + 1);
      }
    }

    // 只保留权重 ≥ 2 的边（过滤噪音）
    const edges = [...edgeMap.entries()]
      .filter(([, w]) => w >= 2)
      .map(([key, weight]) => {
        const [source, target] = key.split('|');
        return { source, target, weight };
      })
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 100);  // 占位限制

    const nodes = [...new Set(edges.flatMap(e => [e.source, e.target]))]
      .map(id => ({ id, degree: edges.filter(e => e.source === id || e.target === id).length }))
      .sort((a, b) => b.degree - a.degree);

    const graph = { nodes, edges, built_at: new Date().toISOString(), textLength: text.length };
    this._graphs.set(graphId, graph);

    return {
      graphId,
      nodeCount: nodes.length,
      edgeCount: edges.length,
      topNodes:  nodes.slice(0, 10).map(n => n.id),
      topEdges:  edges.slice(0, 5),
      note:      'Module 3 将使用 graphology 实现完整图算法和语义推理'
    };
  }

  /* ── 简单图查询 ────────────────────────────────────────── */
  _queryGraph(graphId, entity) {
    const graph = this._graphs.get(graphId);
    if (!graph) return { found: false, message: `图 "${graphId}" 不存在，请先执行 build` };
    if (!entity) return { found: false, message: '请提供 entity 参数' };

    const related = graph.edges
      .filter(e => e.source === entity || e.target === entity)
      .map(e => ({ entity: e.source === entity ? e.target : e.source, weight: e.weight }))
      .sort((a, b) => b.weight - a.weight);

    return {
      entity,
      found:   related.length > 0,
      related,
      degree:  related.length
    };
  }

  /* ── 图统计 ────────────────────────────────────────────── */
  _graphStats(graphId) {
    const graph = this._graphs.get(graphId);
    if (!graph) return { exists: false, graphId };
    return {
      graphId,
      exists:    true,
      nodeCount: graph.nodes.length,
      edgeCount: graph.edges.length,
      builtAt:   graph.built_at,
      avgDegree: graph.nodes.length
        ? +(graph.edges.length * 2 / graph.nodes.length).toFixed(2)
        : 0
    };
  }
}

module.exports = KnowledgeGraph;
