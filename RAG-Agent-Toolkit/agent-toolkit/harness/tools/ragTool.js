/**
 * RAG Tool — 从知识库文件构建上下文
 * input: { fileIds, userId?, maxLength? }
 * output: { context, files }
 */
const BaseTool = require('./baseTool');
const fs   = require('fs');
const path = require('path');
const { buildRagContext } = require('../../services/ragService');

const RAG_FILES_PATH = path.join(__dirname, '../../data/rag-files.json');

class RAGTool extends BaseTool {
  constructor() {
    super('ragTool', '从知识库文件构建 RAG 上下文');
  }

  async execute(input) {
    const { fileIds = [], userId = null, maxLength = 12000 } = input;

    let allFiles = [];
    try {
      allFiles = JSON.parse(fs.readFileSync(RAG_FILES_PATH, 'utf-8'));
    } catch { allFiles = []; }

    const accessible = allFiles.filter(f =>
      f.isPublic === true || !f.userId || f.userId === userId
    );
    const selected = accessible.filter(f => fileIds.includes(f.id));
    const context  = buildRagContext(selected, maxLength);

    return { context, files: selected };
  }
}

module.exports = RAGTool;
