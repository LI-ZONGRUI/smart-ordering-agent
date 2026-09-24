const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const { answerQuery } = require('./generator')
const CONCURRENCY = 3
const NO_ANSWER = '当前提供的知识不足以回答这个问题。'
const nonempty = value => typeof value === 'string' && value.trim().length > 0
const idsValid = value => Array.isArray(value) && value.every(nonempty)
const unique = values => [...new Set(values)]
const ratio = (n, d) => d ? n / d : null
const mean = values => values.length ? values.reduce((sum, n) => sum + n, 0) / values.length : null

function validateDataset(dataset, sources) {
  if (dataset?.evaluationVersion !== 1 || !Array.isArray(dataset.queries) || dataset.queries.length !== 12) throw new Error('DATASET_INVALID')
  const known = new Set(sources.filter(s => s.verified === true).map(s => s.knowledgeId))
  const seen = new Set()
  const seenQuery = new Set()
  const counts = { supported: 0, 'unsupported-domain': 0, 'external-ood': 0 }
  for (const row of dataset.queries) {
    if (!nonempty(row.id) || seen.has(row.id) || !nonempty(row.query) || row.query !== row.query.trim() ||
        Array.from(row.query).length > 200 || seenQuery.has(row.query) || !Object.hasOwn(counts, row.kind) ||
        row.expectedAnswerable !== (row.kind === 'supported')) throw new Error('DATASET_INVALID')
    seen.add(row.id); seenQuery.add(row.query); counts[row.kind]++
    if (row.kind === 'supported') {
      const ids = row.relevantKnowledgeIds
      if (!idsValid(ids) || !ids.length || unique(ids).length !== ids.length || ids.some(id => !known.has(id))) throw new Error('DATASET_INVALID')
    } else if (Object.hasOwn(row, 'relevantKnowledgeIds')) throw new Error('DATASET_INVALID')
  }
  if (counts.supported !== 6 || counts['unsupported-domain'] !== 3 || counts['external-ood'] !== 3) throw new Error('DATASET_INVALID')
  return dataset
}

function loadDataset() {
  const sourceBytes = fs.readFileSync(path.join(__dirname, 'resources/knowledge-source.json'))
  const dataset = JSON.parse(fs.readFileSync(path.join(__dirname, 'resources/answer-eval.json'), 'utf8'))
  if (crypto.createHash('sha256').update(sourceBytes).digest('hex') !== dataset.knowledgeSourceSha256) throw new Error('DATASET_INVALID')
  return validateDataset(dataset, JSON.parse(sourceBytes))
}

function failure(row) {
  // 不把原始异常、上游响应或任意错误字符串带入报告；失败也不伪装成拒答。
  return { id: row.id, query: row.query, kind: row.kind, expectedAnswerable: row.expectedAnswerable,
    status: 'failed', errCode: 'ANSWER_EVAL_QUERY_FAILED', errMsg: '本条调用失败或诊断格式异常，请单独通过管理入口排查',
    actualAnswerable: null, answerabilityCorrect: null, answer: null,
    selectedKnowledgeIds: [], selectedDishIds: [], evidence: [], serverGroundingPass: null }
}

function scoreQuery(row, result) {
  const g = result?.generation
  const r = result?.retrieval
  if (result?.errCode !== 0 || result.query !== row.query || typeof g?.answerable !== 'boolean' ||
      typeof g.answer !== 'string' || !idsValid(g.usedKnowledgeIds) || !idsValid(g.dishIds) ||
      !Array.isArray(g.evidence) || !Array.isArray(r?.results) || r.topK !== 3 || r.results.length > 3) return failure(row)
  const evidenceFields = ['knowledgeId', 'dishId', 'scope', 'type', 'title', 'text']
  const validEvidence = e => e && nonempty(e.knowledgeId) && nonempty(e.title) && nonempty(e.text) &&
    ['dish', 'restaurant'].includes(e.scope) && ['description','taste','ingredients'].includes(e.type) &&
    (e.scope === 'dish' ? nonempty(e.dishId) : e.dishId === null)
  if (!g.evidence.every(validEvidence) || !r.results.every(validEvidence)) return failure(row)
  // 显式挑选字段，不展开诊断对象，完整向量、Prompt、HTTP 响应不会进入报告。
  const evidence = g.evidence.map(e => Object.fromEntries(evidenceFields.map(key => [key, e[key]])))
  const selected = unique(g.usedKnowledgeIds)
  const retrieved = unique(r.results.map(e => e.knowledgeId))
  const selectedDishes = unique(g.dishIds)
  const sameIds = (a, b) => JSON.stringify(a) === JSON.stringify(b)
  const evidenceMatchesRetrieval = evidence.every(e => {
    const original = r.results.find(k => k.knowledgeId === e.knowledgeId)
    return original && evidenceFields.every(key => original[key] === e[key])
  })
  // 仅工程结构检查：原文来源、ID一致性和渲染相等，不判断证据与Query的语义相关性。
  const serverGroundingPass = g.answerable
    ? selected.length > 0 && sameIds(selected, g.usedKnowledgeIds) && sameIds(selectedDishes, g.dishIds) &&
      sameIds(evidence.map(e => e.knowledgeId), selected) && evidenceMatchesRetrieval &&
      evidence.every(e => e.scope !== 'dish' || selectedDishes.includes(e.dishId)) &&
      selectedDishes.every(id => evidence.some(e => e.scope === 'dish' && e.dishId === id)) &&
      g.answer === evidence.map(e => e.text).join('\n')
    : g.answer === NO_ANSWER && selected.length === 0 && selectedDishes.length === 0 && evidence.length === 0
  const output = { id: row.id, query: row.query, kind: row.kind, expectedAnswerable: row.expectedAnswerable,
    status: 'completed', actualAnswerable: g.answerable, answerabilityCorrect: g.answerable === row.expectedAnswerable,
    answer: g.answer, selectedKnowledgeIds: selected, selectedDishIds: selectedDishes, evidence,
    retrievedKnowledgeIds: retrieved, serverGroundingPass }
  if (row.kind === 'supported') {
    const relevant = row.relevantKnowledgeIds
    const selectedRelevant = selected.filter(id => relevant.includes(id))
    const retrievedRelevant = retrieved.filter(id => relevant.includes(id))
    Object.assign(output, {
      relevantKnowledgeIds: [...relevant], selectedRelevantKnowledgeIds: selectedRelevant,
      selectedIrrelevantKnowledgeIds: selected.filter(id => !relevant.includes(id)),
      missedRelevantKnowledgeIds: relevant.filter(id => !selected.includes(id)),
      evidenceHit: selectedRelevant.length > 0,
      evidencePrecision: selected.length ? selectedRelevant.length / selected.length : 0,
      evidenceRecall: selectedRelevant.length / relevant.length,
      retrievedRelevantKnowledgeIds: retrievedRelevant, retrievalHit: retrievedRelevant.length > 0,
      retrievalRecallAt3: retrievedRelevant.length / relevant.length,
      retrievalMissKnowledgeIds: relevant.filter(id => !retrieved.includes(id)),
      evidenceSelectionMissKnowledgeIds: retrievedRelevant.filter(id => !selected.includes(id))
    })
  }
  return output
}

function summarize(queries) {
  const completed = queries.filter(q => q.status === 'completed')
  const supported = completed.filter(q => q.kind === 'supported')
  const unsupported = completed.filter(q => q.kind === 'unsupported-domain')
  const external = completed.filter(q => q.kind === 'external-ood')
  const negatives = [...unsupported, ...external]
  const count = (rows, predicate) => rows.filter(predicate).length
  const correct = count(completed, q => q.answerabilityCorrect)
  const tp = count(supported, q => q.actualAnswerable)
  const tn = count(negatives, q => !q.actualAnswerable)
  const evidenceHits = count(supported, q => q.evidenceHit)
  const retrievalHits = count(supported, q => q.retrievalHit)
  const grounding = count(completed, q => q.serverGroundingPass)
  // 失败不当作FP/FN或TN，所有分母明确报告；整轮存在失败则返回非零errCode。
  return { totalQueries: queries.length,
    supportedCount: count(queries, q => q.kind === 'supported'),
    unsupportedDomainCount: count(queries, q => q.kind === 'unsupported-domain'),
    externalOodCount: count(queries, q => q.kind === 'external-ood'),
    completedCount: completed.length, failedCount: queries.length - completed.length,
    evaluatedSupportedCount: supported.length, evaluatedUnsupportedDomainCount: unsupported.length,
    evaluatedExternalOodCount: external.length,
    answerabilityCorrectCount: correct, answerabilityAccuracy: ratio(correct, completed.length),
    truePositiveCount: tp, supportedAnswerRate: ratio(tp, supported.length),
    trueNegativeCount: tn, rejectionRate: ratio(tn, negatives.length),
    unsupportedDomainRejectionRate: ratio(count(unsupported, q => !q.actualAnswerable), unsupported.length),
    externalOodRejectionRate: ratio(count(external, q => !q.actualAnswerable), external.length),
    falsePositiveQueries: completed.filter(q => !q.expectedAnswerable && q.actualAnswerable).map(q => ({ id: q.id, query: q.query })),
    falseNegativeQueries: supported.filter(q => !q.actualAnswerable).map(q => ({ id: q.id, query: q.query })),
    evidenceHitCount: evidenceHits, evidenceHitRate: ratio(evidenceHits, supported.length),
    averageEvidencePrecision: mean(supported.map(q => q.evidencePrecision)),
    averageEvidenceRecall: mean(supported.map(q => q.evidenceRecall)),
    retrievalHitCount: retrievalHits, retrievalHitRate: ratio(retrievalHits, supported.length),
    averageRetrievalRecallAt3: mean(supported.map(q => q.retrievalRecallAt3)),
    serverGroundingPassCount: grounding, serverGroundingPassRate: ratio(grounding, completed.length) }
}

// 依赖注入只供本地测试；云对象入口不接受或转发测试依赖和标签。
async function evaluateAnswers(options, runAnswer = answerQuery) {
  let dataset
  try { dataset = loadDataset() } catch {
    return { errCode: 'ANSWER_EVAL_DATASET_INVALID', errMsg: '请检查固定评测集与知识源部署副本' }
  }
  const queries = new Array(dataset.queries.length)
  let nextIndex = 0
  async function worker() {
    while (nextIndex < dataset.queries.length) {
      const index = nextIndex++
      const row = dataset.queries[index]
      try { queries[index] = scoreQuery(row, await runAnswer(row.query, options)) }
      catch { queries[index] = failure(row) }
    }
  }
  // 最多3个完整单轮调用并发；写入原下标，即使完成乱序也不会串Query。
  await Promise.all(Array.from({ length: CONCURRENCY }, () => worker()))
  const summary = summarize(queries)
  const structuralFailure = queries.some(q => q.serverGroundingPass === false)
  return { errCode: summary.failedCount ? 'ANSWER_EVAL_PARTIAL_FAILED' : structuralFailure ? 'ANSWER_EVAL_STRUCTURE_FAILED' : 0,
    evaluationVersion: dataset.evaluationVersion, knowledgeSourceSha256: dataset.knowledgeSourceSha256,
    concurrency: CONCURRENCY, ...summary, queries }
}

module.exports = { evaluateAnswers, loadDataset, validateDataset, scoreQuery, summarize }
