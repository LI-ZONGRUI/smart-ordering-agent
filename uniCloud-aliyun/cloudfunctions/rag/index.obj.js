const { URL } = require('url')

module.exports = {
  async evaluateAnswers() {
    // 固定评测集仅供管理运行，不接受客户端 Query、标签或模型覆盖。
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) {
      return { errCode: 'ANSWER_EVAL_FORBIDDEN', errMsg: '请通过管理云函数执行 Answer 评测' }
    }
    const { evaluateAnswers } = require('./answer-evaluator')
    return evaluateAnswers({ db: uniCloud.database(), httpclient: uniCloud.httpclient })
  },

  async answer(query) {
    // 正式单轮接口只接收文本，不转发用户提供的 model、topK 或 Prompt。
    const { answer } = require('./generator')
    return answer(query, { db: uniCloud.database(), httpclient: uniCloud.httpclient })
  },

  async testRagGeneration() {
    // 固定问题的开发/管理诊断，不是微信用户 API，也不接受外部 query。
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) {
      return { errCode: 'RAG_GENERATION_FORBIDDEN', errMsg: '请通过管理云函数执行固定 RAG Generation 测试' }
    }
    const { testRagGeneration } = require('./generator')
    return testRagGeneration({ db: uniCloud.database(), httpclient: uniCloud.httpclient })
  },

  async evaluateRobustness() {
    // 仅供开发/管理评测，不是普通用户 API；不接收外部 Query 或标签。
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) {
      return { errCode: 'ROBUSTNESS_FORBIDDEN', errMsg: '请通过管理云函数执行 Robustness 评测' }
    }
    const { evaluateRobustness } = require('./robustness-evaluator')
    return evaluateRobustness({ db: uniCloud.database(), httpclient: uniCloud.httpclient })
  },

  async evaluateRetrieval() {
    // 开发/管理评测，不是微信用户 API；固定评测集不从客户端接收。
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) {
      return { errCode: 'EVAL_FORBIDDEN', errMsg: '请通过管理云函数执行固定检索评测' }
    }
    const { evaluateRetrieval } = require('./evaluator')
    return evaluateRetrieval({ db: uniCloud.database(), httpclient: uniCloud.httpclient })
  },

  async testRetrieval() {
    // 固定 query 的只读诊断，不接收前端 query，不调用回答模型或索引写入逻辑。
    const { testRetrieval } = require('./retriever')
    return testRetrieval({ db: uniCloud.database(), httpclient: uniCloud.httpclient })
  },

  async buildKnowledgeIndex() {
    // 开发/管理用 indexing 方法，不是普通用户 API。由管理云函数调用。
    // source 由 uniCloud 调用上下文提供，不接受客户端参数指定来源或知识内容。
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) {
      return { errCode: 'INDEX_FORBIDDEN', errMsg: '仅允许通过受信任的管理云函数执行索引' }
    }
    const { buildIndex } = require('./indexer')
    return buildIndex({ db: uniCloud.database(), httpclient: uniCloud.httpclient })
  },

  async testEmbedding() {
    // 本步骤只测试这一条固定文本，不读取知识文件，也不访问数据库。
    const input = '招牌鸡腿饭由鸡腿搭配米饭和时蔬。'
    const apiKey = (process.env.DASHSCOPE_API_KEY || '').trim()
    const baseUrl = (process.env.LLM_BASE_URL || '').trim()
    const model = (process.env.EMBEDDING_MODEL || '').trim()
    const dimensionText = (process.env.EMBEDDING_DIMENSION || '').trim()
    if (!apiKey) return { errCode: 'EMBEDDING_CONFIG_MISSING', errMsg: 'DASHSCOPE_API_KEY 未配置' }
    if (!baseUrl) return { errCode: 'EMBEDDING_CONFIG_MISSING', errMsg: 'LLM_BASE_URL 未配置' }
    if (!model) return { errCode: 'EMBEDDING_CONFIG_MISSING', errMsg: 'EMBEDDING_MODEL 未配置' }
    // 当前验收目标固定为 512 维；不使用静默默认值掩盖配置缺失。
    if (dimensionText !== '512') {
      return { errCode: 'EMBEDDING_DIMENSION_INVALID', errMsg: 'EMBEDDING_DIMENSION 必须配置为 512' }
    }
    const dimension = Number(dimensionText)

    let endpoint
    try {
      endpoint = new URL(baseUrl)
      if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) {
        throw new Error('invalid URL')
      }
      endpoint.pathname = endpoint.pathname.replace(/\/+$/, '') + '/embeddings'
    } catch {
      return { errCode: 'EMBEDDING_CONFIG_INVALID', errMsg: 'LLM_BASE_URL 必须是无账号、查询参数和片段的 HTTPS 基础地址' }
    }

    let response
    try {
      response = await uniCloud.httpclient.request(endpoint.toString(), {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}` },
        contentType: 'json',
        // 独立解析 JSON，以区分 HTTP 失败和响应正文格式异常。
        dataType: 'text',
        timeout: [5000, 15000],
        followRedirect: false,
        data: { model, input, dimensions: dimension, encoding_format: 'float' }
      })
    } catch {
      // 原始异常可能包含密钥和请求头，禁止打印或直接转发。
      return { errCode: 'EMBEDDING_REQUEST_FAILED', errMsg: 'Embedding 请求失败或超时，请检查云端网络后重试' }
    }
    if (!response || !Number.isInteger(response.status)) {
      return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Embedding HTTP 响应格式异常' }
    }
    if (response.status < 200 || response.status >= 300) {
      // 只提供 HTTP 状态码，不返回上游错误正文或请求配置。
      return { errCode: 'EMBEDDING_HTTP_ERROR', errMsg: `Embedding 服务返回非成功状态（HTTP ${response.status}），请检查密钥权限、模型配置和配额` }
    }

    let body
    try {
      body = JSON.parse(response.data)
    } catch {
      return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Embedding 返回体不是有效 JSON' }
    }
    if (body?.error || !Array.isArray(body?.data) || body.data.length !== 1) {
      return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Embedding 返回体应包含一条向量记录' }
    }
    const embedding = body.data[0]?.embedding
    if (!Array.isArray(embedding)) {
      return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Embedding 向量不是数组' }
    }
    if (embedding.length !== dimension) {
      return { errCode: 'EMBEDDING_LENGTH_INVALID', errMsg: 'Embedding 向量长度不是 512，连通测试未通过' }
    }
    if (!embedding.every(value => typeof value === 'number' && Number.isFinite(value))) {
      return { errCode: 'EMBEDDING_NUMBERS_INVALID', errMsg: 'Embedding 向量含非数字或非有限数字，连通测试未通过' }
    }

    // 完整向量仅在本次调用内校验，不写库、不打印，只返回前 5 个数供核验。
    return {
      errCode: 0,
      model,
      dimension: embedding.length,
      vectorPreview: embedding.slice(0, 5),
      hasValidNumbers: true
    }
  },
  async testBatchEmbedding() {
    // TEMP/DIAGNOSTIC batch embedding fixtures
    // 仅固定这 3 条已审核 V1 知识，不读取整份知识源，不访问数据库。
    const fixtures = [
      { knowledgeId: 'dish-1-description', text: '招牌鸡腿饭由鸡腿搭配米饭和时蔬。' },
      { knowledgeId: 'dish-3-taste', text: '鲜蔬沙拉，项目描述为“清爽”。' },
      { knowledgeId: 'dish-8-ingredients', text: '酸梅汤记录的主要配料为：乌梅、山楂、冰糖。' }
    ]
    // 一次数组请求包含全部 3 条文本，不循环请求，也不自动重试。
    const input = fixtures.map(item => item.text)
    const apiKey = (process.env.DASHSCOPE_API_KEY || '').trim()
    const baseUrl = (process.env.LLM_BASE_URL || '').trim()
    const model = (process.env.EMBEDDING_MODEL || '').trim()
    const dimensionText = (process.env.EMBEDDING_DIMENSION || '').trim()
    if (!apiKey) return { errCode: 'EMBEDDING_CONFIG_MISSING', errMsg: 'DASHSCOPE_API_KEY 未配置' }
    if (!baseUrl) return { errCode: 'EMBEDDING_CONFIG_MISSING', errMsg: 'LLM_BASE_URL 未配置' }
    if (!model) return { errCode: 'EMBEDDING_CONFIG_MISSING', errMsg: 'EMBEDDING_MODEL 未配置' }
    // 当前验收目标固定为 512 维；不使用静默默认值掩盖配置缺失。
    if (dimensionText !== '512') {
      return { errCode: 'EMBEDDING_DIMENSION_INVALID', errMsg: 'EMBEDDING_DIMENSION 必须配置为 512' }
    }
    const dimension = Number(dimensionText)

    let endpoint
    try {
      endpoint = new URL(baseUrl)
      if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) {
        throw new Error('invalid URL')
      }
      endpoint.pathname = endpoint.pathname.replace(/\/+$/, '') + '/embeddings'
    } catch {
      return { errCode: 'EMBEDDING_CONFIG_INVALID', errMsg: 'LLM_BASE_URL 必须是无账号、查询参数和片段的 HTTPS 基础地址' }
    }

    let response
    try {
      response = await uniCloud.httpclient.request(endpoint.toString(), {
        method: 'POST',
        headers: { Authorization: `Bearer ${apiKey}` },
        contentType: 'json',
        // 独立解析 JSON，以区分 HTTP 失败和响应正文格式异常。
        dataType: 'text',
        timeout: [5000, 15000],
        followRedirect: false,
        data: { model, input, dimensions: dimension, encoding_format: 'float' }
      })
    } catch {
      // 原始异常可能包含密钥和请求头，禁止打印或直接转发。
      return { errCode: 'EMBEDDING_REQUEST_FAILED', errMsg: 'Embedding 请求失败或超时，请检查云端网络后重试' }
    }
    if (!response || !Number.isInteger(response.status)) {
      return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Embedding HTTP 响应格式异常' }
    }
    if (response.status < 200 || response.status >= 300) {
      // 只提供 HTTP 状态码，不返回上游错误正文或请求配置。
      return { errCode: 'EMBEDDING_HTTP_ERROR', errMsg: `Embedding 服务返回非成功状态（HTTP ${response.status}），请检查密钥权限、模型配置和配额` }
    }

    let body
    try {
      body = JSON.parse(response.data)
    } catch {
      return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Embedding 返回体不是有效 JSON' }
    }
    if (body?.error) {
      return { errCode: 'EMBEDDING_API_ERROR', errMsg: 'Embedding 服务返回错误，请检查云端模型配置和配额' }
    }
    if (!Array.isArray(body?.data)) {
      return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Batch Embedding 返回的 data 不是数组' }
    }
    if (body.data.length !== fixtures.length) {
      return { errCode: 'EMBEDDING_COUNT_INVALID', errMsg: 'Batch Embedding 必须返回 3 条向量记录' }
    }

    const items = []
    for (let index = 0; index < fixtures.length; index++) {
      const item = body.data[index]
      // 严格校验原始响应顺序，不排序、不补 index，避免向量绑定到错误知识。
      if (!Number.isInteger(item?.index) || item.index !== index) {
        return { errCode: 'EMBEDDING_INDEX_INVALID', errMsg: 'Batch Embedding index 缺失或与输入顺序不一致' }
      }
      const embedding = item.embedding
      if (!Array.isArray(embedding)) {
        return { errCode: 'EMBEDDING_RESPONSE_INVALID', errMsg: 'Batch Embedding 向量不是数组' }
      }
      if (embedding.length !== dimension) {
        return { errCode: 'EMBEDDING_LENGTH_INVALID', errMsg: 'Batch Embedding 向量长度必须为 512' }
      }
      if (!embedding.every(value => typeof value === 'number' && Number.isFinite(value))) {
        return { errCode: 'EMBEDDING_NUMBERS_INVALID', errMsg: 'Batch Embedding 向量含非数字或非有限数字' }
      }
      // 只在所有索引与向量校验通过后返回结果；完整向量不出云对象、不打印、不写库。
      items.push({
        knowledgeId: fixtures[item.index].knowledgeId,
        index: item.index,
        dimension: embedding.length,
        vectorPreview: embedding.slice(0, 3)
      })
    }
    return { errCode: 0, model, dimension, count: items.length, items }
  }
}
