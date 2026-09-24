const { URL } = require('url')

function fail(code) {
  const error = new Error(code)
  error.code = code
  throw error
}

function readAgentConfig(env) {
  const apiKey = (env.DASHSCOPE_API_KEY || '').trim()
  const baseUrl = (env.LLM_BASE_URL || '').trim()
  const model = (env.AGENT_LLM_MODEL || '').trim()
  if (!apiKey || !baseUrl || !model) fail('AGENT_CONFIG_MISSING')

  let endpoint
  try {
    endpoint = new URL(baseUrl)
    if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password ||
        endpoint.search || endpoint.hash) throw new Error('invalid URL')
    endpoint.pathname = endpoint.pathname.replace(/\/+$/, '') + '/chat/completions'
  } catch {
    // 不回传内部URL；配置错误与缺失统一提示云对象环境变量。
    fail('AGENT_CONFIG_MISSING')
  }
  return { apiKey, model, endpoint: endpoint.toString() }
}

function parseModelResponse(response) {
  if (!response || !Number.isInteger(response.status)) fail('AGENT_MODEL_RESPONSE_INVALID')
  if (response.status < 200 || response.status >= 300) fail('AGENT_MODEL_REQUEST_FAILED')

  let body
  try { body = JSON.parse(response.data) }
  catch { fail('AGENT_MODEL_RESPONSE_INVALID') }
  const message = body && !body.error && Array.isArray(body.choices) && body.choices[0]?.message
  if (!message || message.role !== 'assistant') fail('AGENT_MODEL_RESPONSE_INVALID')
  if (message.tool_calls !== undefined && !Array.isArray(message.tool_calls)) fail('AGENT_MODEL_RESPONSE_INVALID')

  if (Array.isArray(message.tool_calls) && message.tool_calls.length > 0) {
    const ids = new Set()
    const toolCalls = message.tool_calls.map(call => {
      if (!call || call.type !== 'function' || typeof call.id !== 'string' || !call.id.trim() ||
          ids.has(call.id) || !call.function || typeof call.function.name !== 'string' ||
          !call.function.name.trim() || typeof call.function.arguments !== 'string') {
        fail('AGENT_MODEL_RESPONSE_INVALID')
      }
      ids.add(call.id)
      return {
        id: call.id,
        type: 'function',
        function: { name: call.function.name, arguments: call.function.arguments }
      }
    })
    // 只保留协议所需字段；不保存 reasoning_content 或完整上游响应。
    return {
      type: 'tool_calls',
      message: {
        role: 'assistant',
        content: typeof message.content === 'string' ? message.content : null,
        tool_calls: toolCalls
      }
    }
  }

  if (typeof message.content !== 'string' || !message.content.trim()) fail('AGENT_MODEL_RESPONSE_INVALID')
  return { type: 'final', content: message.content.trim() }
}

async function callAgentModel({ httpclient, config, messages, tools }) {
  let response
  try {
    response = await httpclient.request(config.endpoint, {
      method: 'POST',
      headers: { Authorization: `Bearer ${config.apiKey}` },
      contentType: 'json',
      dataType: 'text',
      timeout: [5000, 30000],
      followRedirect: false,
      data: {
        model: config.model,
        messages,
        tools,
        tool_choice: 'auto',
        stream: false,
        enable_thinking: false,
        max_tokens: 512
      }
    })
  } catch {
    // 原始网络异常可能包含请求头或内部地址，禁止记录和透传。
    fail('AGENT_MODEL_REQUEST_FAILED')
  }
  return parseModelResponse(response)
}

module.exports = { readAgentConfig, parseModelResponse, callAgentModel }
