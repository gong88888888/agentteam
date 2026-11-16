/**
 * MCP 对话会话管理
 * - 维护多用户的对话上下文
 * - 自然语言 → AI 选择工具 → 调用 → 回答
 * - 支持多轮、手动指定工具、回退到纯 AI 对话
 */
const client   = require('./client');
const registry = require('./registry');
const { callAI } = require('../services/aiService');

const SESSIONS  = new Map();    // sessionId → session
const MAX_SESSIONS = 1000;
const MAX_TURNS   = 50;

function _evict() {
  if (SESSIONS.size < MAX_SESSIONS) return;
  const sorted = [...SESSIONS.entries()].sort(
    ([, a], [, b]) => new Date(a.updatedAt) - new Date(b.updatedAt)
  );
  for (const [id] of sorted.slice(0, 100)) SESSIONS.delete(id);
}

function createSession({ userId, username }) {
  _evict();
  const id = `mcp_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const sess = {
    id,
    userId,
    username,
    turns:     [],                // [{ role, content, toolCall, timestamp }]
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  };
  SESSIONS.set(id, sess);
  return sess;
}

function getSession(id) {
  return SESSIONS.get(id) || null;
}

function listUserSessions(userId, limit = 20) {
  return [...SESSIONS.values()]
    .filter(s => s.userId === userId)
    .sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt))
    .slice(0, limit)
    .map(s => ({
      id:        s.id,
      title:     s.turns[0]?.content?.slice(0, 40) || '新对话',
      turns:     s.turns.length,
      updatedAt: s.updatedAt
    }));
}

/**
 * 让 AI 根据用户消息选择工具
 * @returns {Object|null} { tool, input, reasoning } | null（表示无需调工具）
 */
async function selectToolWithAI({ message, ctx, history }) {
  const tools = await client.listTools(ctx);
  if (!tools.length) return null;

  const catalog = tools.map(t =>
    `- ${t.name}: ${t.description} | 入参: ${JSON.stringify(t.inputSchema?.properties || {})}`
  ).join('\n');

  const sysPrompt = `你是 MCP 工具调度器。根据用户当前消息和对话历史，判断是否需要调用某个工具。
可用工具列表：
${catalog}

输出严格的 JSON（不要 Markdown 代码块）：
- 需要调工具：{"action":"tool","tool":"<name>","input":{...},"reasoning":"<为什么调它>"}
- 不需要调工具（普通闲聊）：{"action":"chat","reasoning":"<原因>"}

规则：
1. 用户消息要求"生成 / 计算 / 读取文件 / 搜索"等，必须选合适的工具。
2. input 字段必须符合工具的 inputSchema。
3. 不确定就用 ai.chat。`;

  const userPrompt = `历史（最近 3 轮）：
${history.slice(-6).map(t => `${t.role}: ${t.content}`).join('\n') || '（无）'}

当前用户消息：${message}

请输出 JSON。`;

  try {
    const raw = await callAI(
      [{ role: 'system', content: sysPrompt }, { role: 'user', content: userPrompt }],
      { temperature: 0.2, maxTokens: 500 },
      ctx.userId
    );
    const m = raw.match(/\{[\s\S]*\}/);
    if (!m) return null;
    const parsed = JSON.parse(m[0]);
    if (parsed.action === 'tool' && parsed.tool) return parsed;
    return null;
  } catch (e) {
    console.warn('[MCP/chat] 工具选择失败:', e.message);
    return null;
  }
}

const fs   = require('fs');
const path = require('path');

/**
 * 读取附件文件内容（文本类型）
 * @param {Array} attachedFiles [{name, path, ext}]
 * @returns {string} 文件内容摘要
 */
function buildAttachedFilesContext(attachedFiles) {
  if (!Array.isArray(attachedFiles) || attachedFiles.length === 0) return '';
  const parts = [];
  for (const f of attachedFiles) {
    if (!f.path) continue;
    try {
      const filePath = resolveAttachedFilePath(f.path);
      if (!filePath || !fs.existsSync(filePath)) {
        parts.push(`[文件 ${f.name}: 文件不存在或已被清理]`);
        continue;
      }
      const stat = fs.statSync(filePath);
      const ext = (path.extname(f.name) || '').toLowerCase();
      if (['.pdf', '.xlsx', '.xls', '.pptx', '.docx'].includes(ext)) {
        // 二进制文件：告知 AI 文件存在，并提供路径（AI 可用工具读取）
        const officePath = f.officePath || f.path;
        parts.push(`[文件 ${f.name}: 已上传（${(stat.size / 1024).toFixed(0)}KB），文件路径: ${officePath}。请使用 office.view 工具读取内容，filename 必须填写 "${officePath}"]`);
      } else if (stat.size > 500 * 1024) {  // 超过 500KB 只给摘要
        parts.push(`[文件 ${f.name}: 文件较大（${(stat.size / 1024).toFixed(0)}KB），仅展示前 500 字符]\n${fs.readFileSync(filePath, 'utf-8').slice(0, 500)}...`);
      } else {
        // 文本文件：直接读取内容
        const content = fs.readFileSync(filePath, 'utf-8').slice(0, 8000);
        parts.push(`--- 文件: ${f.name} ---\n${content}${content.length >= 8000 ? '\n...[内容已截取]' : ''}`);
      }
    } catch (e) {
      parts.push(`[文件 ${f.name}: 读取失败 - ${e.message}]`);
    }
  }
  return parts.length > 0 ? `\n\n## 附件文件内容\n${parts.join('\n\n')}` : '';
}

function resolveAttachedFilePath(filePath) {
  if (!filePath) return null;
  return path.isAbsolute(filePath)
    ? filePath
    : path.resolve(__dirname, '..', filePath);
}

/**
 * 提交一次对话消息
 * @returns {Object} { session, response, toolCalls }
 */
async function sendMessage({ sessionId, message, ctx, manualTool = null, attachedFiles = null }) {
  let session = SESSIONS.get(sessionId);
  if (!session) session = createSession({ userId: ctx.userId, username: ctx.username });

  // 限制对话轮数
  if (session.turns.length >= MAX_TURNS * 2) {
    session.turns.splice(0, 2);
  }

  // 注入附件文件内容到消息上下文
  const fileContext  = buildAttachedFilesContext(attachedFiles);
  const fullMessage  = fileContext ? `${message}${fileContext}` : message;

  // 写入用户回合（展示原始消息，但 AI 收到的包含文件内容）
  const userTurn = { role: 'user', content: message, timestamp: new Date().toISOString() };
  session.turns.push(userTurn);

  const toolCalls = [];          // 本轮的工具调用可视化时间线

  // 1. 决定是否调工具（使用包含文件内容的完整消息）
  let decision;
  if (manualTool) {
    decision = { action: 'tool', tool: manualTool.name, input: manualTool.input || {}, reasoning: '用户手动指定' };
  } else {
    decision = await selectToolWithAI({
      message:  fullMessage,
      ctx,
      history: session.turns.slice(0, -1)
    });
  }

  let toolResultText = '';

  if (decision && decision.action === 'tool') {
    const tcEntry = {
      step:      'tool_call',
      tool:      decision.tool,
      input:     decision.input,
      reasoning: decision.reasoning,
      startedAt: new Date().toISOString(),
      status:    'running'
    };
    toolCalls.push(tcEntry);

    try {
      // 自动注入 userId
      const args = { userId: ctx.userId, ...(decision.input || {}) };
      const result = await client.callTool(decision.tool, args, ctx);
      tcEntry.status     = result.isError ? 'error' : 'success';
      tcEntry.completedAt = new Date().toISOString();
      tcEntry.output     = result;
      tcEntry.outputText = client.extractText(result);
      toolResultText = tcEntry.outputText;
    } catch (e) {
      tcEntry.status     = 'error';
      tcEntry.error      = e.message;
      tcEntry.completedAt = new Date().toISOString();
      toolResultText = `[工具调用失败] ${e.message}`;
    }
  }

  // 2. 让 AI 根据工具结果合成最终回答（如果调了工具）
  let finalAnswer;
  if (toolCalls.length > 0) {
    try {
      const synthMessages = [
        {
          role: 'system',
          content: '你是 MCP 智能体。根据用户问题、工具调用过程和工具返回结果，给出简洁、友好、结构化的中文回答。'
        },
        ...session.turns.slice(-6).map(t => ({ role: t.role === 'assistant' ? 'assistant' : 'user', content: t.content })),
        {
          role: 'user',
          content: `工具 ${toolCalls[0].tool} 调用结果：\n${toolResultText}\n\n请总结回答用户的原始问题。`
        }
      ];
      finalAnswer = await callAI(synthMessages, { temperature: 0.5, maxTokens: 1000 }, ctx.userId);
    } catch (e) {
      finalAnswer = `工具已执行：\n${toolResultText}\n\n（合成回答失败：${e.message}）`;
    }
  } else {
    // 纯 AI 对话（最后一条 user 消息用包含文件内容的完整版本）
    try {
      const historyForAI = session.turns.slice(0, -1).map(t => ({
        role:    t.role === 'assistant' ? 'assistant' : 'user',
        content: t.content
      }));
      finalAnswer = await callAI([
        { role: 'system', content: '你是 MCP 智能体助理，具备文件分析能力。当用户上传了文件时，请仔细阅读文件内容并给出针对性的分析和回答。' },
        ...historyForAI,
        { role: 'user', content: fullMessage }
      ], { temperature: 0.7, maxTokens: 4000 }, ctx.userId);
    } catch (e) {
      finalAnswer = `（AI 服务暂不可用：${e.message}）`;
    }
  }

  const assistantTurn = {
    role:      'assistant',
    content:   finalAnswer || '（无回答）',
    toolCalls,
    timestamp: new Date().toISOString()
  };
  session.turns.push(assistantTurn);
  session.updatedAt = new Date().toISOString();

  return { session, response: assistantTurn, toolCalls };
}

function deleteSession(id, userId) {
  const s = SESSIONS.get(id);
  if (!s || s.userId !== userId) return false;
  return SESSIONS.delete(id);
}

module.exports = {
  createSession, getSession, listUserSessions,
  sendMessage,   deleteSession
};
