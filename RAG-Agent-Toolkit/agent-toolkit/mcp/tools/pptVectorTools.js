'use strict';

const fs = require('fs');
const path = require('path');

const exportDir = path.join(__dirname, '../../exports/ppt');
function outFile(prefix) {
  fs.mkdirSync(exportDir, { recursive: true });
  return path.join(exportDir, `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.pptx`);
}

const searchVectorGraphics = {
  name: 'ppt.search_vector_graphics',
  description: '按关键词、图形类型和行业分类检索当前用户可见的 PPT 原生矢量图形组件',
  category: 'ppt', icon: '🔎', source: 'builtin',
  config: { timeoutMs: 10000, rateLimit: { limit: 60, windowMs: 60000 } },
  inputSchema: {
    type: 'object',
    properties: {
      keyword: { type: 'string' },
      graphicType: { type: 'string', enum: ['flow', 'architecture', 'organization', 'all'] },
      category: { type: 'string' },
      limit: { type: 'integer', minimum: 1, maximum: 50 },
    },
  },
  handler: async (input = {}) => {
    const store = require('../../services/ppt/materialStore');
    const ctx = { userId: input.userId, isAdmin: input._ctx?.isAdmin === true };
    const words = String(input.keyword || '').toLowerCase().split(/\s+/).filter(Boolean);
    const matches = [];
    for (const mat of store.list({ ...ctx, category: input.category })) {
      const raw = store.getRaw(mat.id, ctx);
      for (const c of raw?.graphics?.components || []) {
        const hay = `${mat.name} ${mat.category} ${c.label || ''} ${(c.textSamples || []).join(' ')}`.toLowerCase();
        const kind = /流程|flow/.test(hay) ? 'flow' : (/组织|org/.test(hay) ? 'organization' : 'architecture');
        if (input.graphicType && input.graphicType !== 'all' && kind !== input.graphicType) continue;
        const score = words.reduce((n, w) => n + (hay.includes(w) ? 2 : 0), 0) + Math.min(3, (c.shapeCount || 0) / 20);
        if (words.length && score <= 0) continue;
        matches.push({
          materialId: mat.id, materialName: mat.name, componentId: c.id,
          label: c.label, graphicType: kind, score,
          thumbnail: raw?.thumbnails?.components?.[c.id] || null,
          colors: c.colors || mat.colors || [],
        });
      }
    }
    return { items: matches.sort((a, b) => b.score - a.score).slice(0, Math.min(50, input.limit || 20)) };
  },
};

const generateVectorDiagram = {
  name: 'ppt.generate_vector_diagram',
  description: '调用原生环形图、流程图或组织架构图渲染器生成全可编辑 PPTX',
  category: 'ppt', icon: '⬡', source: 'builtin',
  config: { timeoutMs: 90000, rateLimit: { limit: 10, windowMs: 60000 } },
  inputSchema: {
    type: 'object',
    properties: {
      diagramType: { type: 'string', enum: ['ring', 'flow', 'org'] },
      title: { type: 'string' },
      data: { type: 'object' },
      colors: { type: 'object' },
    },
    required: ['diagramType', 'data'],
  },
  handler: async (input) => {
    const serviceName = input.diagramType === 'ring' ? 'ringDiagram' : input.diagramType === 'org' ? 'orgDiagram' : 'flowDiagram';
    const service = require(`../../services/ppt/${serviceName}`);
    const fn = input.diagramType === 'ring' ? service.generateRing : input.diagramType === 'org' ? service.generateOrg : service.generateFlow;
    const out = outFile('mcp-vector');
    const result = fn({ out, title: input.title, colors: input.colors || {}, ...(input.data || {}) });
    if (!result.ok) throw new Error(result.error || '矢量图形生成失败');
    return { ...result, filename: path.basename(out), downloadUrl: `/api/ppt/download/${path.basename(out)}` };
  },
};

const cloneVectorGraphic = {
  name: 'ppt.clone_vector_graphic',
  description: '把素材库指定原生矢量组件克隆到新 PPT 或目标 PPT 的指定页面',
  category: 'ppt', icon: '⧉', source: 'builtin',
  config: { timeoutMs: 90000, rateLimit: { limit: 10, windowMs: 60000 } },
  inputSchema: {
    type: 'object',
    properties: {
      materialId: { type: 'string' },
      componentId: { type: 'string' },
      targetPptPath: { type: 'string' },
      slideIndex: { type: 'integer', minimum: 0 },
      textMap: { type: 'object' },
      colorMap: { type: 'object' },
    },
    required: ['materialId', 'componentId'],
  },
  handler: async (input) => {
    const store = require('../../services/ppt/materialStore');
    const ctx = { userId: input.userId, isAdmin: input._ctx?.isAdmin === true };
    const c = store.getComponent(input.materialId, input.componentId, ctx);
    if (!c) throw new Error('图形组件不存在或无权访问');
    const out = outFile('mcp-clone');
    const result = require('../../services/ppt/graphicsCloner').cloneGraphics({
      out, target: input.targetPptPath, slideIndex: input.slideIndex,
      slideSize: c.slideSize, nodes: c.component.nodes,
      textMap: input.textMap, colorMap: input.colorMap,
    });
    if (!result.ok) throw new Error(result.error || '图形克隆失败');
    return { ...result, filename: path.basename(out), downloadUrl: `/api/ppt/download/${path.basename(out)}` };
  },
};

module.exports = { ALL_PPT_VECTOR_TOOLS: [searchVectorGraphics, generateVectorDiagram, cloneVectorGraphic] };
