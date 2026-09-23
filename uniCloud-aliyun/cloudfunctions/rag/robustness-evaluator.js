const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const { readConfig, readCandidates, rankCandidates, cosineSimilarity } = require('./retriever')
const { calculateMetrics } = require('./evaluator')

// 独立评测工具；不改 Baseline evaluator，不复制 cosine 或排序算法。
const BATCH_SIZE = 12
const MESSAGES = {
  ROBUSTNESS_DATASET_INVALID: 'Robustness 固定评测集或冻结知识资源校验失败',
  ROBUSTNESS_CORPUS_INVALID: '云端候选与冻结知识不一致，或向量损坏，本轮不生成指标',
  ROBUSTNESS_RESULT_INVALID: 'Robustness 排名结果或分组格式无效',
  ROBUSTNESS_EMBEDDING_FAILED: 'Robustness Embedding 请求失败，请检查 rag 配置、模型权限和配额',
  ROBUSTNESS_EMBEDDING_INVALID: 'Robustness Embedding 数量、索引或向量无效',
  ROBUSTNESS_FAILED: 'Robustness 评测未完整完成，请检查部署、知识库与环境变量'
}
const fail = code => { throw new Error(code) }
const nonempty = value => typeof value === 'string' && value.trim().length > 0
const KINDS = ['supported-paraphrase', 'supported-exploratory', 'unsupported-domain-hard']

function validateDataset(dataset, sources) {
  if (dataset?.robustnessVersion !== 1 || dataset.retrieverBaselineVersion !== 1 ||
      dataset.embeddingModel !== 'qwen3.7-text-embedding-flash' || dataset.embeddingDimension !== 512 ||
      dataset.topK !== 3 || dataset.expectedKnowledgeCount !== 21 ||
      !Array.isArray(dataset.queries) || dataset.queries.length !== 24 ||
      !Array.isArray(sources) || sources.length !== 21) fail('ROBUSTNESS_DATASET_INVALID')
  const ids = new Set(sources.map(item => item.knowledgeId))
  if (ids.size !== 21 || sources.some(item => !nonempty(item.knowledgeId) || item.verified !== true || item.sourceVersion !== 1)) fail('ROBUSTNESS_DATASET_INVALID')
  const queryIds = new Set()
  const texts = new Set()
  const counts = Object.fromEntries(KINDS.map(kind => [kind, 0]))
  for (const item of dataset.queries) {
    if (!nonempty(item?.id) || queryIds.has(item.id) || !nonempty(item.query) || texts.has(item.query) ||
        !KINDS.includes(item.kind) || !nonempty(item.labelRationale) || !Array.isArray(item.relevantKnowledgeIds)) fail('ROBUSTNESS_DATASET_INVALID')
    const relevant = item.relevantKnowledgeIds
    if ((item.kind === 'supported-paraphrase' ? relevant.length === 0 : relevant.length !== 0) ||
        new Set(relevant).size !== relevant.length || relevant.some(id => !ids.has(id))) fail('ROBUSTNESS_DATASET_INVALID')
    counts[item.kind]++
    queryIds.add(item.id)
    texts.add(item.query)
  }
  if (counts['supported-paraphrase'] !== 11 || counts['supported-exploratory'] !== 1 || counts['unsupported-domain-hard'] !== 12) fail('ROBUSTNESS_DATASET_INVALID')
}

function loadDataset() {
  const folder = path.join(__dirname, 'resources')
  const dataset = JSON.parse(fs.readFileSync(path.join(folder, 'retrieval-robustness-eval.json'), 'utf8'))
  const raw = fs.readFileSync(path.join(folder, 'knowledge-source.json'))
  if (crypto.createHash('sha256').update(raw).digest('hex') !== dataset.knowledgeSourceSha256) fail('ROBUSTNESS_DATASET_INVALID')
  const sources = JSON.parse(raw.toString('utf8'))
  validateDataset(dataset, sources)
  return { dataset, sources }
}

function safeTop3(rows) {
  if (!Array.isArray(rows) || rows.length > 3) fail('ROBUSTNESS_RESULT_INVALID')
  const seen = new Set()
  return rows.map((row, index) => {
    if (!row || row.rank !== index + 1 || !nonempty(row.knowledgeId) || seen.has(row.knowledgeId) ||
        !nonempty(row.title) || !Number.isFinite(row.similarity)) fail('ROBUSTNESS_RESULT_INVALID')
    seen.add(row.knowledgeId)
    // 只保留评测字段；不返回或打印完整向量，不重新排序或修正分数。
    return { rank: row.rank, knowledgeId: row.knowledgeId, title: row.title, similarity: row.similarity }
  })
}

function scoreSummary(queries) {
  const scores = queries.map(item => item.top1Similarity).filter(Number.isFinite)
  return {
    count: queries.length, scoredCount: scores.length,
    minTop1Similarity: scores.length ? Math.min(...scores) : null,
    maxTop1Similarity: scores.length ? Math.max(...scores) : null,
    averageTop1Similarity: scores.length ? scores.reduce((sum, value) => sum + value, 0) / scores.length : null
  }
}

function summarizeRobustness(dataset, rankings) {
  if (!Array.isArray(dataset?.queries) || !Array.isArray(rankings) || rankings.length !== dataset.queries.length) fail('ROBUSTNESS_RESULT_INVALID')
  const supported = []
  const unsupported = []
  const exploratory = []
  for (let i = 0; i < dataset.queries.length; i++) {
    const item = dataset.queries[i]
    if (!KINDS.includes(item.kind) || !Array.isArray(item.relevantKnowledgeIds) ||
        (item.kind !== 'supported-paraphrase' && item.relevantKnowledgeIds.length)) fail('ROBUSTNESS_DATASET_INVALID')
    const top3 = safeTop3(rankings[i])
    const result = { id: item.id, query: item.query, kind: item.kind,
      top1KnowledgeId: top3[0]?.knowledgeId ?? null, top1Title: top3[0]?.title ?? null,
      top1Similarity: top3[0]?.similarity ?? null, top3 }
    if (item.kind === 'supported-paraphrase') {
      Object.assign(result, { relevantKnowledgeIds: item.relevantKnowledgeIds,
        top1IsRelevant: top3.length > 0 && item.relevantKnowledgeIds.includes(top3[0].knowledgeId) },
      calculateMetrics(item.relevantKnowledgeIds, top3))
      supported.push(result)
    } else if (item.kind === 'unsupported-domain-hard') {
      Object.assign(result, { top3Similarities: top3.map(row => row.similarity), top3KnowledgeIds: top3.map(row => row.knowledgeId) })
      unsupported.push(result)
    } else {
      Object.assign(result, { recallAt3: null, coverageAt3: null, hitAt3: null,
        note: '语义标签不明确，不参与 supported 或 Separation 统计' })
      exploratory.push(result)
    }
  }
  const supportedScores = scoreSummary(supported)
  const unsupportedScores = scoreSummary(unsupported)
  const supportedMinTop1 = supportedScores.minTop1Similarity
  const unsupportedMaxTop1 = unsupportedScores.maxTop1Similarity
  // 缺少任一组完整分数时无法判断间隔，不能把缺失值当 0 或宣称完美分离。
  const comparable = supported.length > 0 && unsupported.length > 0 &&
    supportedScores.scoredCount === supported.length && unsupportedScores.scoredCount === unsupported.length
  const separationGap = comparable ? supportedMinTop1 - unsupportedMaxTop1 : null
  const compact = item => ({ query: item.query, top1KnowledgeId: item.top1KnowledgeId,
    top1Title: item.top1Title, top1Similarity: item.top1Similarity,
    ...(typeof item.top1IsRelevant === 'boolean' ? { top1IsRelevant: item.top1IsRelevant } : {}) })
  return {
    totalQueries: dataset.queries.length,
    supportedParaphrase: { ...supportedScores,
      top1RelevantCount: supported.filter(item => item.top1IsRelevant).length,
      hitAt3Count: supported.filter(item => item.hitAt3).length,
      averageRecallAt3: supported.length ? supported.reduce((sum, item) => sum + item.recallAt3, 0) / supported.length : null,
      averageCoverageAt3: supported.length ? supported.reduce((sum, item) => sum + item.coverageAt3, 0) / supported.length : null,
      queries: supported },
    unsupportedDomainHard: { ...unsupportedScores, queries: unsupported },
    supportedExploratory: { count: exploratory.length, queries: exploratory },
    overlapAnalysis: {
      hasOverlap: comparable ? separationGap <= 0 : null, separationGap, supportedMinTop1, unsupportedMaxTop1,
      // 仅统计分数重叠案例，不过滤检索结果、不生成阈值或拒答决策。
      hardNegativeQueries: comparable ? unsupported.filter(item => item.top1Similarity >= supportedMinTop1).map(compact) : [],
      lowScoreSupportedQueries: comparable ? supported.filter(item => item.top1Similarity <= unsupportedMaxTop1).map(compact) : [],
      observation: !comparable ? '分组为空或分数不完整，无法判断间隔' : separationGap > 0
        ? '当前 Robustness Dataset 上仍存在分数间隔'
        : 'supported 与 unsupported similarity 已发生重叠，简单固定 threshold 无法在本 Dataset 上完美分离'
    }
  }
}

async function embedQueries(httpclient, config, queries) {
  const vectors = []
  // 固定 24 条分成两批，每批 12 条；不把 24 条塞进原先的小批请求。
  // 每批 index 从 0 开始，映射后按 batch 原序拼接；任一批失败都不生成部分报告。
  for (let offset = 0; offset < queries.length; offset += BATCH_SIZE) {
    const batch = queries.slice(offset, offset + BATCH_SIZE)
    let response
    try {
      response = await httpclient.request(config.endpoint, {
        method: 'POST', headers: { Authorization: `Bearer ${config.apiKey}` },
        contentType: 'json', dataType: 'text', timeout: [5000, 30000], followRedirect: false,
        data: { model: config.model, input: batch.map(item => item.query), dimensions: config.dimension, encoding_format: 'float' }
      })
    } catch { fail('ROBUSTNESS_EMBEDDING_FAILED') }
    if (!Number.isInteger(response?.status) || response.status < 200 || response.status >= 300) fail('ROBUSTNESS_EMBEDDING_FAILED')
    let body
    try { body = JSON.parse(response.data) } catch { fail('ROBUSTNESS_EMBEDDING_INVALID') }
    if (body?.error || !Array.isArray(body?.data) || body.data.length !== batch.length) fail('ROBUSTNESS_EMBEDDING_INVALID')
    const mapped = new Map()
    for (const item of body.data) {
      if (!Number.isInteger(item?.index) || item.index < 0 || item.index >= batch.length || mapped.has(item.index) ||
          !Array.isArray(item.embedding) || item.embedding.length !== config.dimension) fail('ROBUSTNESS_EMBEDDING_INVALID')
      try { cosineSimilarity(item.embedding, item.embedding) } catch { fail('ROBUSTNESS_EMBEDDING_INVALID') }
      mapped.set(item.index, item.embedding)
    }
    if (mapped.size !== batch.length) fail('ROBUSTNESS_EMBEDDING_INVALID')
    vectors.push(...batch.map((_, index) => mapped.get(index)))
  }
  return vectors
}

async function evaluateRobustness({ db, httpclient, env = process.env }) {
  try {
    const { dataset, sources } = loadDataset()
    const config = readConfig(env)
    const records = (await readCandidates(db)).filter(record => record?.verified === true)
    const sourceMap = new Map(sources.map(item => [item.knowledgeId, item]))
    if (records.length !== 21 || new Set(records.map(item => item.knowledgeId)).size !== 21 || records.some(record => {
      const source = sourceMap.get(record.knowledgeId)
      return !source || ['text', 'title', 'type', 'scope', 'dishId'].some(key => record[key] !== source[key])
    })) fail('ROBUSTNESS_CORPUS_INVALID')
    // 先复用 Retriever 验证整份候选，损坏索引不消耗 Query Embedding 用量。
    try { rankCandidates(records[0].embedding, records, config) } catch { fail('ROBUSTNESS_CORPUS_INVALID') }
    const vectors = await embedQueries(httpclient, config, dataset.queries)
    const rankings = vectors.map(vector => rankCandidates(vector, records, config).results)
    return { errCode: 0, robustnessVersion: dataset.robustnessVersion, retrieverBaselineVersion: dataset.retrieverBaselineVersion,
      knowledgeSourceSha256: dataset.knowledgeSourceSha256, embeddingModel: config.model,
      embeddingDimension: config.dimension, totalCandidates: records.length, topK: dataset.topK,
      ...summarizeRobustness(dataset, rankings) }
  } catch (error) {
    // 原始 HTTP/数据库异常可能带敏感请求头；仅返回固定错误码和文案。
    const errCode = Object.prototype.hasOwnProperty.call(MESSAGES, error?.message) ? error.message : 'ROBUSTNESS_FAILED'
    return { errCode, errMsg: MESSAGES[errCode] }
  }
}

module.exports = { evaluateRobustness, summarizeRobustness, validateDataset, loadDataset }
