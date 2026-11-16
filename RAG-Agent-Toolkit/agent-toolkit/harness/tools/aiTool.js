/**
 * AI Tool — 封装 callAI / callAIStream，供 Harness 步骤调用
 * input: { messages, overrideConfig?, userId?, stream?, onChunk? }
 * output: { content }
 */
const BaseTool = require('./baseTool');
const { callAI, callAIStream } = require('../../services/aiService');

class AITool extends BaseTool {
  constructor() {
    super('aiTool', '调用 AI 大模型（支持流式和非流式）');
  }

  async execute(input) {
    const {
      messages,
      overrideConfig = {},
      userId         = null,
      stream         = false,
      onChunk        = null
    } = input;

    if (!messages || !Array.isArray(messages)) {
      throw new Error('aiTool: messages 必须是数组');
    }

    if (stream && typeof onChunk === 'function') {
      return new Promise((resolve, reject) => {
        callAIStream(
          messages,
          overrideConfig,
          onChunk,
          (full) => resolve({ content: full }),
          (err)  => reject(err),
          userId
        );
      });
    }

    const content = await callAI(messages, overrideConfig, userId);
    return { content };
  }
}

module.exports = AITool;
