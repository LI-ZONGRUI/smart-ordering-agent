// 任意单轮 Query 的传输适配层；候选校验、cosine、排序、Top-3 全部复用冻结 Retriever。
const { readConfig, readCandidates, rankCandidates, cosineSimilarity } = require('./retriever')

const MESSAGES = {
  RETRIEVAL_CONFIG_INVALID: '请检查 rag 的 Embedding 配置，模型和维度必须与知识索引一致',
  RETRIEVAL_QUERY_REQUEST_FAILED: 'Query Embedding 请求失败或超时，请稍后重试',
  RETRIEVAL_QUERY_HTTP_ERROR: 'Query Embedding 服务返回非成功状态，请检查权限和配额',
  RETRIEVAL_QUERY_RESPONSE_INVALID: 'Query Embedding 返回格式或向量无效',
  RETRIEVAL_DATABASE_FAILED: '知识索引读取失败，请检查部署状态',
  RETRIEVAL_EMPTY: '没有可检索的已审核知识',
  RETRIEVAL_DATA_INVALID: '知识索引包含损坏、不兼容或重复记录',
  RETRIEVAL_FAILED: '知识检索未完成，请稍后重试'
}
const fail = code => { throw new Error(code) }

async function retrieveQuery(query, { db, httpclient, env }) {
  try {
    const config = readConfig(env)
    let response
    try {
      response = await httpclient.request(config.endpoint, {
        method: 'POST', headers: { Authorization: `Bearer ${config.apiKey}` },
        contentType: 'json', dataType: 'text', timeout: [5000, 15000], followRedirect: false,
        data: { model: config.model, input: query, dimensions: config.dimension, encoding_format: 'float' }
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
    if (!Array.isArray(vector) || vector.length !== config.dimension) fail('RETRIEVAL_QUERY_RESPONSE_INVALID')
    // 冻结 cosine 自身会检查有限数字、稀疏数组和零范数；不复制计算逻辑。
    try { cosineSimilarity(vector, vector) } catch { fail('RETRIEVAL_QUERY_RESPONSE_INVALID') }
    const records = await readCandidates(db)
    return { errCode: 0, query, ...rankCandidates(vector, records, config) }
  } catch (error) {
    const errCode = Object.hasOwn(MESSAGES, error?.message) ? error.message : 'RETRIEVAL_FAILED'
    return { errCode, errMsg: MESSAGES[errCode] }
  }
}

module.exports = { retrieveQuery }
