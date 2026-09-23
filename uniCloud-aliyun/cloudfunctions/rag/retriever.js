const { URL } = require('url')

const QUERY = '有什么比较清爽的？'
const TOP_K = 3
const DIMENSION = 512
const PAGE_SIZE = 100

const ERROR_MESSAGES = {
  RETRIEVAL_CONFIG_INVALID: '请检查 rag 的 Embedding 环境变量：模型应为 qwen3.7-text-embedding-flash，维度应为 512',
  RETRIEVAL_QUERY_REQUEST_FAILED: 'Query Embedding 请求失败或超时，请稍后重试',
  RETRIEVAL_QUERY_HTTP_ERROR: 'Query Embedding 服务返回非成功状态，请检查模型权限和配额',
  RETRIEVAL_QUERY_RESPONSE_INVALID: 'Query Embedding 返回格式或向量无效',
  RETRIEVAL_DATABASE_FAILED: '知识索引读取失败，请检查 knowledge_chunks 部署状态',
  RETRIEVAL_EMPTY: '没有可检索的已审核知识，请检查 knowledge_chunks',
  RETRIEVAL_DATA_INVALID: '知识索引包含损坏、不兼容或重复记录，请检查模型、维度、向量及知识字段',
  RETRIEVAL_FAILED: '检索诊断失败，请检查云端配置后重试'
}

function fail(code) { throw new Error(code) }

function isFiniteVector(vector) {
  if (!Array.isArray(vector) || vector.length === 0) return false
  // for...of 同时检查稀疏数组中的空位，不能用会跳过空位的 every。
  for (const value of vector) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return false
  }
  return true
}

function cosineSimilarity(a, b) {
  if (!isFiniteVector(a) || !isFiniteVector(b)) fail('COSINE_VECTOR_INVALID')
  if (a.length !== b.length) fail('COSINE_LENGTH_MISMATCH')

  let scaleA = 0
  let scaleB = 0
  for (let i = 0; i < a.length; i++) {
    scaleA = Math.max(scaleA, Math.abs(a[i]))
    scaleB = Math.max(scaleB, Math.abs(b[i]))
  }
  if (scaleA === 0 || scaleB === 0) fail('COSINE_ZERO_NORM')

  // 两个向量分别除以正数不改变夹角；缩放可避免有限大数平方溢出或小数下溢。
  let dot = 0
  let normA = 0
  let normB = 0
  for (let i = 0; i < a.length; i++) {
    const x = a[i] / scaleA
    const y = b[i] / scaleB
    dot += x * y
    normA += x * x
    normB += y * y
  }
  const similarity = dot / (Math.sqrt(normA) * Math.sqrt(normB))
  if (!Number.isFinite(similarity)) fail('COSINE_RESULT_INVALID')
  return similarity
}

function readConfig(env) {
  const apiKey = (env.DASHSCOPE_API_KEY || '').trim()
  const baseUrl = (env.LLM_BASE_URL || '').trim()
  const model = (env.EMBEDDING_MODEL || '').trim()
  if (!apiKey || !baseUrl || model !== 'qwen3.7-text-embedding-flash' ||
      (env.EMBEDDING_DIMENSION || '').trim() !== '512') fail('RETRIEVAL_CONFIG_INVALID')
  let endpoint
  try {
    endpoint = new URL(baseUrl)
    if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) throw new Error()
    endpoint.pathname = endpoint.pathname.replace(/\/+$/, '') + '/embeddings'
  } catch { fail('RETRIEVAL_CONFIG_INVALID') }
  return { apiKey, model, dimension: Number(env.EMBEDDING_DIMENSION), endpoint: endpoint.toString() }
}

async function embedQuery(httpclient, config) {
  let response
  try {
    response = await httpclient.request(config.endpoint, {
      method: 'POST', headers: { Authorization: `Bearer ${config.apiKey}` },
      contentType: 'json', dataType: 'text', timeout: [5000, 15000], followRedirect: false,
      data: { model: config.model, input: QUERY, dimensions: config.dimension, encoding_format: 'float' }
    })
  } catch { fail('RETRIEVAL_QUERY_REQUEST_FAILED') }
  if (!Number.isInteger(response?.status)) fail('RETRIEVAL_QUERY_RESPONSE_INVALID')
  if (response.status < 200 || response.status >= 300) fail('RETRIEVAL_QUERY_HTTP_ERROR')
  let body
  try { body = JSON.parse(response.data) } catch { fail('RETRIEVAL_QUERY_RESPONSE_INVALID') }
  if (body?.error || !Array.isArray(body?.data) || body.data.length !== 1 || body.data[0]?.index !== 0) {
    fail('RETRIEVAL_QUERY_RESPONSE_INVALID')
  }
  const vector = body.data[0].embedding
  if (!isFiniteVector(vector) || vector.length !== DIMENSION) fail('RETRIEVAL_QUERY_RESPONSE_INVALID')
  try { cosineSimilarity(vector, vector) } catch { fail('RETRIEVAL_QUERY_RESPONSE_INVALID') }
  return vector
}

async function readCandidates(db) {
  const records = []
  try {
    for (let offset = 0; ; offset += PAGE_SIZE) {
      // verified 是唯一候选筛选条件。模型/维度不匹配要报错，不能用 where 静默过滤。
      const result = await db.collection('knowledge_chunks').where({ verified: true })
        .orderBy('_id', 'asc').skip(offset).limit(PAGE_SIZE)
        .field({ knowledgeId: true, dishId: true, scope: true, type: true, title: true, text: true,
          verified: true, embedding: true, embeddingModel: true, embeddingDimension: true }).get()
      if (!Array.isArray(result?.data)) fail('RETRIEVAL_DATABASE_FAILED')
      records.push(...result.data)
      if (result.data.length < PAGE_SIZE) break
    }
  } catch { fail('RETRIEVAL_DATABASE_FAILED') }
  return records
}

// 内部共享原始 Exact Search，仅复用计算，不改变过滤、排序或 Top-3 规则。
function rankCandidates(queryVector, records, config) {
  const scored = []
  const knowledgeIds = new Set()
  const nonempty = value => typeof value === 'string' && value.trim().length > 0
  for (const record of records) {
    if (!record || typeof record !== 'object') fail('RETRIEVAL_DATA_INVALID')
    if (record.verified !== true) continue
    if (!nonempty(record.knowledgeId) || knowledgeIds.has(record.knowledgeId) ||
        !nonempty(record.text) || !nonempty(record.title) ||
        !['dish', 'restaurant'].includes(record.scope) ||
        (record.scope === 'dish' ? !nonempty(record.dishId) : record.dishId !== null) ||
        !['description', 'taste', 'ingredients'].includes(record.type) ||
        record.embeddingModel !== config.model || record.embeddingDimension !== config.dimension ||
        !isFiniteVector(record.embedding) || record.embedding.length !== DIMENSION) {
      fail('RETRIEVAL_DATA_INVALID')
    }
    let similarity
    try { similarity = cosineSimilarity(queryVector, record.embedding) } catch { fail('RETRIEVAL_DATA_INVALID') }
    knowledgeIds.add(record.knowledgeId)
    // 只拣选允许返回的知识字段；不展开整条数据库记录，避免把 embedding 带到前端。
    scored.push({ knowledgeId: record.knowledgeId, dishId: record.dishId, scope: record.scope,
      type: record.type, title: record.title, text: record.text, similarity })
  }
  if (scored.length === 0) fail('RETRIEVAL_EMPTY')
  // 先用原始精度排序，完全相同才按 knowledgeId 字符串升序。没有阈值或额外加权。
  scored.sort((a, b) => b.similarity - a.similarity ||
    (a.knowledgeId < b.knowledgeId ? -1 : a.knowledgeId > b.knowledgeId ? 1 : 0))
  return {
    totalCandidates: scored.length, topK: TOP_K,
    results: scored.slice(0, TOP_K).map((record, index) => ({
      rank: index + 1, ...record, similarity: Number(record.similarity.toFixed(6))
    }))
  }
}

// 依赖注入仅用于本地测试；不提供接收任意 query 的 searchKnowledge 接口。
async function testRetrieval({ db, httpclient, env = process.env }) {
  try {
    const config = readConfig(env)
    const queryVector = await embedQuery(httpclient, config)
    const records = await readCandidates(db)
    return {
      errCode: 0, query: QUERY, embeddingModel: config.model, embeddingDimension: config.dimension,
      ...rankCandidates(queryVector, records, config)
    }
  } catch (error) {
    // 原始 HTTP/数据库异常可能含请求头，不打印、不转发；仅返回固定业务错误文案。
    const errCode = Object.prototype.hasOwnProperty.call(ERROR_MESSAGES, error?.message) ? error.message : 'RETRIEVAL_FAILED'
    return { errCode, errMsg: ERROR_MESSAGES[errCode] }
  }
}

module.exports = { cosineSimilarity, testRetrieval, readConfig, readCandidates, rankCandidates }
