/**
 * MCP (Model Context Protocol) 类型常量与协议工具
 * 遵循 MCP 1.0 / JSON-RPC 2.0 规范
 */

const MCP_VERSION   = '2026-01-01';      // 协议时间戳版本
const PROTOCOL_NAME = 'mcp';

// 标准方法
const METHODS = {
  INITIALIZE:  'initialize',
  TOOLS_LIST:  'tools/list',
  TOOLS_CALL:  'tools/call',
  PING:        'ping'
};

// JSON-RPC 错误码（MCP 子集）
const ERROR_CODES = {
  PARSE_ERROR:       -32700,
  INVALID_REQUEST:   -32600,
  METHOD_NOT_FOUND:  -32601,
  INVALID_PARAMS:    -32602,
  INTERNAL_ERROR:    -32603,
  // MCP 扩展错误
  TOOL_NOT_FOUND:    -32001,
  TOOL_DISABLED:     -32002,
  PERMISSION_DENIED: -32003,
  EXECUTION_TIMEOUT: -32004,
  TOOL_ERROR:        -32005
};

/** 构造标准 JSON-RPC 请求 */
function makeRequest(method, params = {}, id = null) {
  return {
    jsonrpc: '2.0',
    id:      id ?? Math.random().toString(36).slice(2, 10),
    method,
    params
  };
}

/** 构造标准 JSON-RPC 成功响应 */
function makeResponse(id, result) {
  return { jsonrpc: '2.0', id, result };
}

/** 构造标准 JSON-RPC 错误响应 */
function makeError(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) error.data = data;
  return { jsonrpc: '2.0', id, error };
}

/** 构造 MCP 内容数组（tools/call 标准返回结构） */
function makeContent(type, data) {
  if (type === 'text')  return [{ type: 'text', text: String(data) }];
  if (type === 'json')  return [{ type: 'text', text: JSON.stringify(data, null, 2) }];
  if (type === 'image') return [{ type: 'image', data: data.base64, mimeType: data.mimeType || 'image/png' }];
  if (type === 'file')  return [{ type: 'resource', resource: { uri: data.uri, mimeType: data.mimeType, text: data.text } }];
  return [{ type: 'text', text: String(data) }];
}

module.exports = {
  MCP_VERSION,
  PROTOCOL_NAME,
  METHODS,
  ERROR_CODES,
  makeRequest,
  makeResponse,
  makeError,
  makeContent
};
