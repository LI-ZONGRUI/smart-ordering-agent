const crypto = require('crypto')
const fs = require('fs')
const path = require('path')
const { URL } = require('url')

// 模型同步接口单批上限为 20；这里保守使用 10，不硬编码知识总数为 21。
const BATCH_SIZE = 10
const DIMENSION = 512
const PAGE_SIZE = 100
const RUN_BUDGET_MS = 85000 // 配合云对象 120 秒超时，预留返回统计的时间。
const sha256 = value => crypto.createHash('sha256').update(value).digest('hex')
const nonempty = value => typeof value === 'string' && value.trim().length > 0
const validId = value => typeof value === 'string' && /^[a-zA-Z0-9_-]+$/.test(value)

function fail(code) { throw new Error(code) }

function validateSources(sources) {
  if (!Array.isArray(sources) || sources.length === 0) fail('INDEX_SOURCE_INVALID')
  const ids = new Set()
  for (const item of sources) {
    if (!item || !validId(item.knowledgeId) || ids.has(item.knowledgeId) ||
        !['dish', 'restaurant'].includes(item.scope) ||
        (item.scope === 'dish' ? !validId(item.dishId) : item.dishId !== null) ||
        !['description', 'taste', 'ingredients'].includes(item.type) ||
        !nonempty(item.title) || !nonempty(item.text) || item.sourceType !== 'project-data' ||
        item.verified !== true || !Number.isSafeInteger(item.sourceVersion) || item.sourceVersion < 1 ||
        !Array.isArray(item.sourceFields) || item.sourceFields.length === 0) fail('INDEX_SOURCE_INVALID')
    for (const field of item.sourceFields) {
      if (!field || !nonempty(field.file) || !Array.isArray(field.fields) || field.fields.length === 0 ||
          !field.fields.every(nonempty) || (field.recordId !== undefined && !nonempty(field.recordId))) {
        fail('INDEX_SOURCE_INVALID')
      }
    }
    ids.add(item.knowledgeId)
  }
}

// 固定字段及顺序组成 canonical JSON；不 trim 正文，标点/空白变化也能被识别。
// 来源元数据纳入 hash，避免只改来源信息时被错误 skip。真正送给模型的仍然只有 text。
function sourceContent(source) {
  return {
    knowledgeId: source.knowledgeId, scope: source.scope, dishId: source.dishId,
    type: source.type, title: source.title, text: source.text, sourceType: source.sourceType,
    sourceFields: source.sourceFields.map(field => ({
      file: field.file, recordId: field.recordId ?? null, fields: field.fields
    }))
  }
}
function contentHash(source) { return sha256(JSON.stringify(sourceContent(source))) }

function loadSources() {
  // 云端只读取部署目录，不尝试访问项目根目录 docs，也不从请求参数接收知识正文。
  const folder = path.join(__dirname, 'resources')
  const raw = fs.readFileSync(path.join(folder, 'knowledge-source.json'))
  const manifest = JSON.parse(fs.readFileSync(path.join(folder, 'knowledge-source.manifest.json'), 'utf8'))
  if (sha256(raw) !== manifest.sha256 || manifest.sourcePath !== 'docs/rag/knowledge-source.json') {
    fail('INDEX_SOURCE_INVALID')
  }
  const sources = JSON.parse(raw.toString('utf8'))
  validateSources(sources)
  if (sources.length !== manifest.count) fail('INDEX_SOURCE_INVALID')
  return sources
}

function readConfig(env) {
  const apiKey = (env.DASHSCOPE_API_KEY || '').trim()
  const baseUrl = (env.LLM_BASE_URL || '').trim()
  const model = (env.EMBEDDING_MODEL || '').trim()
  if (!apiKey || !baseUrl || !model || (env.EMBEDDING_DIMENSION || '').trim() !== '512') {
    fail('INDEX_CONFIG_INVALID')
  }
  let endpoint
  try {
    endpoint = new URL(baseUrl)
    if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password || endpoint.search || endpoint.hash) throw new Error()
    endpoint.pathname = endpoint.pathname.replace(/\/+$/, '') + '/embeddings'
  } catch { fail('INDEX_CONFIG_INVALID') }
  return { apiKey, endpoint: endpoint.toString(), model, dimension: DIMENSION }
}

async function embedBatch(batch, config, httpclient) {
  let response
  try {
    response = await httpclient.request(config.endpoint, {
      method: 'POST', headers: { Authorization: `Bearer ${config.apiKey}` },
      contentType: 'json', dataType: 'text', timeout: [5000, 15000], followRedirect: false,
      data: { model: config.model, input: batch.map(item => item.text), dimensions: DIMENSION, encoding_format: 'float' }
    })
  } catch { fail('INDEX_EMBEDDING_REQUEST_FAILED') }
  if (!Number.isInteger(response?.status) || response.status < 200 || response.status >= 300) {
    fail('INDEX_EMBEDDING_HTTP_ERROR')
  }
  let body
  try { body = JSON.parse(response.data) } catch { fail('INDEX_EMBEDDING_RESPONSE_INVALID') }
  if (body?.error || !Array.isArray(body?.data) || body.data.length !== batch.length) {
    fail('INDEX_EMBEDDING_RESPONSE_INVALID')
  }
  const vectors = new Map()
  for (const item of body.data) {
    const index = item?.index
    if (!Number.isInteger(index) || index < 0 || index >= batch.length || vectors.has(index)) {
      fail('INDEX_EMBEDDING_INDEX_INVALID')
    }
    const vector = item.embedding
    if (!Array.isArray(vector) || vector.length !== DIMENSION ||
        !vector.every(value => typeof value === 'number' && Number.isFinite(value))) {
      fail('INDEX_EMBEDDING_VECTOR_INVALID')
    }
    vectors.set(index, vector)
  }
  if (vectors.size !== batch.length) fail('INDEX_EMBEDDING_INDEX_INVALID')
  // 按 index 还原输入顺序，不依赖响应数组位置。
  return batch.map((_, index) => vectors.get(index))
}

async function readExisting(collection, checkTime) {
  const records = new Map()
  for (let offset = 0; ; offset += PAGE_SIZE) {
    checkTime()
    const result = await collection.orderBy('_id', 'asc').skip(offset).limit(PAGE_SIZE)
      .field({ _id: true, knowledgeId: true, sourceVersion: true, contentHash: true,
        embeddingModel: true, embeddingDimension: true, verified: true, createTime: true, updateTime: true }).get()
    if (!Array.isArray(result?.data)) fail('INDEX_DATABASE_READ_FAILED')
    for (const record of result.data) {
      if (!validId(record.knowledgeId) || records.has(record.knowledgeId)) fail('INDEX_DATABASE_DUPLICATE_OR_INVALID')
      records.set(record.knowledgeId, record)
    }
    if (result.data.length < PAGE_SIZE) return records
  }
}

// 依赖参数仅供本地测试注入；对外云对象方法不接收这些参数。
async function buildIndex({ db, httpclient, env = process.env, sources, now = Date.now }) {
  const stats = { total: 0, inserted: 0, updated: 0, skipped: 0, failed: 0,
    failures: [], orphanCount: 0, orphanKnowledgeIds: [], orphanScanComplete: false }
  let config, records, collection
  const started = now()
  const checkTime = () => { if (now() - started >= RUN_BUDGET_MS) fail('INDEX_TIME_BUDGET') }
  const reportFailure = (items, code) => {
    for (const item of items) stats.failures.push({ knowledgeId: item.knowledgeId, code })
    stats.failed += items.length
  }
  const safeCodes = new Set(['INDEX_CONFIG_INVALID', 'INDEX_SOURCE_INVALID', 'INDEX_TIME_BUDGET',
    'INDEX_DATABASE_DUPLICATE_OR_INVALID', 'INDEX_DISH_MISSING', 'INDEX_DATABASE_READ_FAILED',
    'INDEX_EMBEDDING_REQUEST_FAILED', 'INDEX_EMBEDDING_HTTP_ERROR', 'INDEX_EMBEDDING_RESPONSE_INVALID',
    'INDEX_EMBEDDING_INDEX_INVALID', 'INDEX_EMBEDDING_VECTOR_INVALID'])
  const safeCode = (error, fallback) => safeCodes.has(error?.message) ? error.message : fallback
  try {
    sources = sources || loadSources()
    stats.total = Array.isArray(sources) ? sources.length : 0
    validateSources(sources)
    config = readConfig(env)
    collection = db.collection('knowledge_chunks')
    records = await readExisting(collection, checkTime)
    const sourceIds = new Set(sources.map(item => item.knowledgeId))
    stats.orphanKnowledgeIds = [...records.keys()].filter(id => !sourceIds.has(id)).sort()
    stats.orphanCount = stats.orphanKnowledgeIds.length
    stats.orphanScanComplete = true
    // 不依据售卖状态删除长期知识，但 dishId 必须仍对应真实菜品。
    const dishIds = [...new Set(sources.filter(item => item.scope === 'dish').map(item => item.dishId))]
    for (let offset = 0; offset < dishIds.length; offset += BATCH_SIZE) {
      checkTime()
      const ids = dishIds.slice(offset, offset + BATCH_SIZE)
      const result = await db.collection('dishes').where({ _id: db.command.in(ids) }).field({ _id: true }).limit(BATCH_SIZE).get()
      if (!Array.isArray(result?.data)) fail('INDEX_DATABASE_READ_FAILED')
      const found = new Set(result.data.map(item => item._id))
      if (ids.some(id => !found.has(id))) fail('INDEX_DISH_MISSING')
    }
  } catch (error) {
    stats.failed = stats.total
    return { errCode: safeCode(error, 'INDEX_PREFLIGHT_FAILED'), errMsg: '索引预检失败，请检查部署副本、环境变量、菜品及数据库定义；未发起 Embedding。', ...stats }
  }

  const pending = []
  for (const source of sources) {
    const old = records.get(source.knowledgeId)
    const hash = contentHash(source)
    if (old && old.sourceVersion === source.sourceVersion && old.contentHash === hash &&
        old.embeddingModel === config.model && old.embeddingDimension === config.dimension && old.verified === true) {
      stats.skipped++
    } else pending.push({ source, old, hash })
  }

  for (let offset = 0; offset < pending.length; offset += BATCH_SIZE) {
    const batch = pending.slice(offset, offset + BATCH_SIZE)
    let vectors
    try {
      checkTime()
      vectors = await embedBatch(batch.map(item => item.source), config, httpclient)
    } catch (error) {
      // 停止后续请求；已确认写入的记录保留，下次重跑只补未完成记录。
      reportFailure(pending.slice(offset).map(item => item.source), safeCode(error, 'INDEX_EMBEDDING_FAILED'))
      break
    }
    for (let index = 0; index < batch.length; index++) {
      const { source, old, hash } = batch[index]
      const record = { ...sourceContent(source), sourceFields: source.sourceFields,
        sourceVersion: source.sourceVersion, verified: true, contentHash: hash,
        embedding: vectors[index], embeddingModel: config.model, embeddingDimension: config.dimension,
        // 保证更新时间递增，同一毫秒内的并发更新也能被条件更新识别。
        updateTime: Math.max(now(), Number.isFinite(old?.updateTime) ? old.updateTime + 1 : 0) }
      try {
        checkTime()
        if (old) {
          // 条件更新避免并发运行覆盖刚被其他运行更新的记录；冲突作为失败，交由重跑核对。
          const result = await collection.where({ _id: old._id, knowledgeId: source.knowledgeId,
            updateTime: old.updateTime ?? db.command.exists(false) }).update(record)
          if (result?.updated !== 1) throw new Error('write conflict')
          stats.updated++
        } else {
          // 唯一 knowledgeId 索引是主保障；确定性 _id 也防止两次并发插入同一知识。
          const result = await collection.add({ _id: sha256(source.knowledgeId).slice(0, 32),
            ...record, createTime: record.updateTime })
          if (!result?.id) throw new Error('write not confirmed')
          stats.inserted++
        }
      } catch (error) {
        reportFailure([source], error?.message === 'INDEX_TIME_BUDGET' ? 'INDEX_TIME_BUDGET' : 'INDEX_WRITE_FAILED')
      }
    }
  }
  return { errCode: stats.failed ? 'INDEX_PARTIAL_FAILURE' : 0,
    errMsg: stats.failed ? '部分知识未确认完成，请检查数据库和部署配置后重跑。' : '索引完成', ...stats }
}

module.exports = { buildIndex, validateSources, contentHash, loadSources, BATCH_SIZE }
