const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const { cosineSimilarity, readConfig, readCandidates, rankCandidates } = require('./retriever')

const MESSAGES = {
  EVAL_DATASET_INVALID: '固定评测集或源知识版本校验失败，请检查部署资源',
  EVAL_CORPUS_MISMATCH: '云端已审核候选与冻结的 21 条知识不一致，本次不计算指标',
  EVAL_LABELS_INVALID: '评测 relevant 标签为空、重复或格式不正确',
  EVAL_RESULT_INVALID: '评测检索结果存在重复 ID 或格式错误',
  EVAL_EMBEDDING_FAILED: '评测 Query Embedding 请求失败，请检查 rag 环境变量、模型权限和配额',
  EVAL_EMBEDDING_INVALID: '评测 Query Embedding 返回数量、索引或向量无效',
  EVAL_FAILED: '评测未完整完成，不生成部分平均值，请检查固定评测集、云端数据及环境配置'
}
const fail = code => { throw new Error(code) }
const nonempty = value => typeof value === 'string' && value.trim().length > 0

function loadDataset() {
  // 评测集在部署目录中只有这一份，不复制到前端，也不接受请求参数替换标签/query。
  const folder = path.join(__dirname, 'resources')
  const dataset = JSON.parse(fs.readFileSync(path.join(folder, 'retrieval-eval.json'), 'utf8'))
  const raw = fs.readFileSync(path.join(folder, 'knowledge-source.json'))
  if (crypto.createHash('sha256').update(raw).digest('hex') !== dataset.knowledgeSourceSha256) fail('EVAL_DATASET_INVALID')
  const sources = JSON.parse(raw.toString('utf8'))
  validateDataset(dataset, sources)
  return { dataset, sources }
}

function validateDataset(dataset, sources) {
  if (dataset?.evaluationVersion !== 2 || dataset.retrieverBaselineVersion !== 1 || dataset.topK !== 3 || dataset.expectedKnowledgeCount !== 21 ||
      dataset.embeddingDimension !== 512 || dataset.embeddingModel !== 'qwen3.7-text-embedding-flash' ||
      !Array.isArray(dataset.queries) || dataset.queries.length !== 19 ||
      !Array.isArray(sources) || sources.length !== 21) fail('EVAL_DATASET_INVALID')
  const sourceIds = new Set()
  for (const source of sources) {
    if (!nonempty(source.knowledgeId) || sourceIds.has(source.knowledgeId) || source.verified !== true || source.sourceVersion !== 1) fail('EVAL_DATASET_INVALID')
    sourceIds.add(source.knowledgeId)
  }
  const queryIds = new Set()
  const queryTexts = new Set()
  const counts = { labeled: 0, exploratory: 0, 'external-ood': 0, 'unsupported-domain': 0 }
  for (const item of dataset.queries) {
    if (!nonempty(item.id) || queryIds.has(item.id) || !nonempty(item.query) || queryTexts.has(item.query) ||
        !Object.prototype.hasOwnProperty.call(counts, item.kind) || !Array.isArray(item.relevantKnowledgeIds) ||
        !nonempty(item.labelRationale)) fail('EVAL_DATASET_INVALID')
    const ids = item.relevantKnowledgeIds
    if ((item.kind === 'labeled' ? ids.length === 0 : ids.length !== 0) ||
        new Set(ids).size !== ids.length || ids.some(id => !sourceIds.has(id))) fail('EVAL_DATASET_INVALID')
    counts[item.kind]++
    queryIds.add(item.id)
    queryTexts.add(item.query)
  }
  if (counts.labeled !== 7 || counts.exploratory !== 1 || counts['external-ood'] !== 6 || counts['unsupported-domain'] !== 5) fail('EVAL_DATASET_INVALID')
}

function safeTop3(top3) {
  if (!Array.isArray(top3) || top3.length > 3) fail('EVAL_RESULT_INVALID')
  const ids = new Set()
  return top3.map((item, index) => {
    if (!item || !nonempty(item.knowledgeId) || ids.has(item.knowledgeId) ||
        item.rank !== index + 1 || !nonempty(item.title) || !Number.isFinite(item.similarity)) fail('EVAL_RESULT_INVALID')
    ids.add(item.knowledgeId)
    // 不调整 similarity，也不展开数据库记录，避免返回 embedding。
    return { rank: item.rank, knowledgeId: item.knowledgeId, title: item.title, similarity: item.similarity }
  })
}

function calculateMetrics(relevantKnowledgeIds, top3) {
  if (!Array.isArray(relevantKnowledgeIds) || relevantKnowledgeIds.length === 0 ||
      !relevantKnowledgeIds.every(nonempty) || new Set(relevantKnowledgeIds).size !== relevantKnowledgeIds.length) fail('EVAL_LABELS_INVALID')
  const retrieved = safeTop3(top3)
  const relevant = new Set(relevantKnowledgeIds)
  const retrievedRelevantIds = retrieved.filter(item => relevant.has(item.knowledgeId)).map(item => item.knowledgeId)
  const found = new Set(retrievedRelevantIds)
  return {
    hits: found.size,
    expectedRelevantCount: relevant.size,
    retrievedRelevantIds,
    missedRelevantIds: relevantKnowledgeIds.filter(id => !found.has(id)),
    recallAt3: found.size / relevant.size,
    // 辅助指标：Top-3 可容纳的相关结果是否找满，不替代原始 Recall。
    coverageAt3: found.size / Math.min(relevant.size, 3),
    hitAt3: found.size > 0
  }
}

function summarizeTop1(items) {
  // 空结果记 null，不当成分数 0；scoredCount 明确表示参与分数平均的 Query 数。
  const scores = items.map(item => item.top1Similarity).filter(Number.isFinite)
  return {
    count: items.length, scoredCount: scores.length,
    minTop1Similarity: scores.length ? Math.min(...scores) : null,
    maxTop1Similarity: scores.length ? Math.max(...scores) : null,
    averageTop1Similarity: scores.length ? scores.reduce((sum, score) => sum + score, 0) / scores.length : null
  }
}

function summarizeEvaluation(dataset, rankings) {
  if (!Array.isArray(rankings) || rankings.length !== dataset.queries.length) fail('EVAL_RESULT_INVALID')
  const queries = []
  const externalOodQueries = []
  const unsupportedDomainQueries = []
  const labeledQueries = []
  let recallSum = 0
  let coverageSum = 0
  let evaluatedRecallQueries = 0
  let hitAt3Count = 0
  for (let i = 0; i < dataset.queries.length; i++) {
    const item = dataset.queries[i]
    const top3 = safeTop3(rankings[i])
    if (!['labeled', 'exploratory', 'external-ood', 'unsupported-domain'].includes(item.kind) ||
        !Array.isArray(item.relevantKnowledgeIds) || (item.kind !== 'labeled' && item.relevantKnowledgeIds.length !== 0)) fail('EVAL_DATASET_INVALID')
    if (item.kind === 'external-ood' || item.kind === 'unsupported-domain') {
      const group = item.kind === 'external-ood' ? externalOodQueries : unsupportedDomainQueries
      group.push({ id: item.id, query: item.query, kind: item.kind, top1Similarity: top3[0]?.similarity ?? null,
        top3Similarities: top3.map(row => row.similarity), top3KnowledgeIds: top3.map(row => row.knowledgeId),
        top3Titles: top3.map(row => row.title), top3 })
      continue
    }
    const result = { id: item.id, query: item.query, kind: item.kind, relevantKnowledgeIds: item.relevantKnowledgeIds, top3 }
    if (item.kind === 'labeled') {
      const metrics = calculateMetrics(item.relevantKnowledgeIds, top3)
      const relevantIds = new Set(item.relevantKnowledgeIds)
      const relevantScores = top3.filter(row => relevantIds.has(row.knowledgeId)).map(row => row.similarity)
      Object.assign(result, metrics, {
        top1Similarity: top3[0]?.similarity ?? null,
        thirdSimilarity: top3[2]?.similarity ?? null,
        lowestRelevantSimilarityInTop3: relevantScores.length ? Math.min(...relevantScores) : null
      })
      labeledQueries.push(result)
      recallSum += metrics.recallAt3
      coverageSum += metrics.coverageAt3
      evaluatedRecallQueries++
      if (metrics.hitAt3) hitAt3Count++
    } else {
      Object.assign(result, { recallAt3: null, coverageAt3: null, hitAt3: null, note: '探索性 Query，不参与 Recall/Hit/Coverage 统计' })
    }
    queries.push(result)
  }
  return { totalQueries: dataset.queries.length, evaluatedRecallQueries,
    averageRecallAt3: evaluatedRecallQueries ? recallSum / evaluatedRecallQueries : null,
    averageCoverageAt3: evaluatedRecallQueries ? coverageSum / evaluatedRecallQueries : null,
    hitAt3Count, exploratoryQueries: queries.filter(item => item.kind === 'exploratory').length,
    labeled: summarizeTop1(labeledQueries), queries,
    externalOod: { ...summarizeTop1(externalOodQueries), queries: externalOodQueries },
    unsupportedDomain: { ...summarizeTop1(unsupportedDomainQueries), queries: unsupportedDomainQueries } }
}

async function embedEvaluationQueries(httpclient, config, queries) {
  // 同步接口一次包含固定 19 个文本（不超过模型单批 20 条上限），排名逻辑不变。
  let response
  try {
    response = await httpclient.request(config.endpoint, {
      method: 'POST', headers: { Authorization: `Bearer ${config.apiKey}` },
      contentType: 'json', dataType: 'text', timeout: [5000, 30000], followRedirect: false,
      data: { model: config.model, input: queries.map(item => item.query), dimensions: config.dimension, encoding_format: 'float' }
    })
  } catch { fail('EVAL_EMBEDDING_FAILED') }
  if (!Number.isInteger(response?.status) || response.status < 200 || response.status >= 300) fail('EVAL_EMBEDDING_FAILED')
  let body
  try { body = JSON.parse(response.data) } catch { fail('EVAL_EMBEDDING_INVALID') }
  if (body?.error || !Array.isArray(body?.data) || body.data.length !== queries.length) fail('EVAL_EMBEDDING_INVALID')
  const vectors = new Map()
  for (const item of body.data) {
    if (!Number.isInteger(item?.index) || item.index < 0 || item.index >= queries.length || vectors.has(item.index) ||
        !Array.isArray(item.embedding) || item.embedding.length !== config.dimension) fail('EVAL_EMBEDDING_INVALID')
    try { cosineSimilarity(item.embedding, item.embedding) } catch { fail('EVAL_EMBEDDING_INVALID') }
    vectors.set(item.index, item.embedding)
  }
  if (vectors.size !== queries.length) fail('EVAL_EMBEDDING_INVALID')
  return queries.map((_, index) => vectors.get(index))
}

// 仅通过受限管理入口调用；不接收客户端 query、标签或数据库写入参数。
async function evaluateRetrieval({ db, httpclient, env = process.env }) {
  try {
    const { dataset, sources } = loadDataset()
    const config = readConfig(env)
    const records = (await readCandidates(db)).filter(record => record?.verified === true)
    const sourceMap = new Map(sources.map(item => [item.knowledgeId, item]))
    if (records.length !== dataset.expectedKnowledgeCount || new Set(records.map(item => item.knowledgeId)).size !== records.length ||
        records.some(record => {
          const source = sourceMap.get(record.knowledgeId)
          return !source || ['text', 'title', 'type', 'scope', 'dishId'].some(key => record[key] !== source[key])
        })) fail('EVAL_CORPUS_MISMATCH')
    const vectors = await embedEvaluationQueries(httpclient, config, dataset.queries)
    // 所有 query 使用同一份候选快照；不按标签筛候选，不把 relevant 列表传给 Retriever。
    const rankings = vectors.map(vector => rankCandidates(vector, records, config).results)
    return { errCode: 0, evaluationVersion: dataset.evaluationVersion,
      retrieverBaselineVersion: dataset.retrieverBaselineVersion,
      knowledgeSourceSha256: dataset.knowledgeSourceSha256,
      embeddingModel: config.model, embeddingDimension: config.dimension, totalCandidates: records.length, topK: dataset.topK,
      ...summarizeEvaluation(dataset, rankings) }
  } catch (error) {
    const errCode = Object.prototype.hasOwnProperty.call(MESSAGES, error?.message) ? error.message : 'EVAL_FAILED'
    return { errCode, errMsg: MESSAGES[errCode] }
  }
}

module.exports = { evaluateRetrieval, calculateMetrics, summarizeEvaluation, validateDataset, loadDataset }
