const { URL } = require('url')

module.exports = {
  recommend: require('./recommend'),
  async testConnection() {
    // 配置只从云对象运行环境读取，不接收前端传入的密钥、地址或 Prompt。
    const apiKey = (process.env.DASHSCOPE_API_KEY || '').trim()
    const baseUrl = (process.env.LLM_BASE_URL || '').trim()
    const model = (process.env.LLM_MODEL || '').trim()
    if (!apiKey) return { errCode: 'AI_CONFIG_MISSING', errMsg: 'DASHSCOPE_API_KEY 未配置' }
    if (!baseUrl) return { errCode: 'AI_CONFIG_MISSING', errMsg: 'LLM_BASE_URL 未配置' }
    if (!model) return { errCode: 'AI_CONFIG_MISSING', errMsg: 'LLM_MODEL 未配置' }

    let endpoint
    try {
      endpoint = new URL(baseUrl)
      if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password ||
          endpoint.search || endpoint.hash) {
        throw new Error('invalid URL')
      }
      endpoint.pathname = endpoint.pathname.replace(/\/+$/, '') + '/chat/completions'
    } catch {
      return { errCode: 'AI_CONFIG_INVALID', errMsg: 'LLM_BASE_URL 必须是无账号、查询参数和片段的 HTTPS 基础地址' }
    }

    let response
    try {
      response = await uniCloud.httpclient.request(endpoint.toString(), {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}` },
        contentType: 'json',
        // 先读文本，再独立解析，便于区分 HTTP 错误与 JSON 格式错误。
        dataType: 'text',
        timeout: [5000, 15000],
        followRedirect: false,
        data: {
          model,
          messages: [{ role: 'user', content: '只回复：连接成功' }],
          stream: false,
          enable_thinking: false,
          max_tokens: 32
        }
      })
    } catch {
      // 原始异常可能携带 Authorization 或请求配置，禁止打印或直接返回。
      return { errCode: 'AI_REQUEST_FAILED', errMsg: 'Model Studio HTTP 请求失败或超时，请检查云端网络和服务可用性' }
    }

    if (!response || !Number.isInteger(response.status)) {
      return { errCode: 'AI_RESPONSE_INVALID', errMsg: 'Model Studio HTTP 响应格式异常' }
    }
    if (response.status < 200 || response.status >= 300) {
      // 只返回状态码，不转发上游错误正文或任何请求头。
      return { errCode: 'AI_HTTP_ERROR', errMsg: `Model Studio 返回非成功状态（HTTP ${response.status}），请检查密钥权限、模型名称和配额` }
    }

    let body
    try {
      body = JSON.parse(response.data)
    } catch {
      return { errCode: 'AI_RESPONSE_INVALID', errMsg: 'Model Studio 返回体不是有效 JSON' }
    }
    const content = body && Array.isArray(body.choices) && body.choices[0]?.message?.content
    if (body?.error || typeof content !== 'string' || !content.trim()) {
      return { errCode: 'AI_RESPONSE_INVALID', errMsg: 'Model Studio 返回体缺少有效的 choices[0].message.content' }
    }

    // 仅返回测试文本，不返回完整响应、请求头或模型的思考内容。
    return { errCode: 0, content: content.trim() }
  }
}
