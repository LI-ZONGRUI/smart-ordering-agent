const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const crypto = require('node:crypto')
const { calculateMetrics, summarizeEvaluation, evaluateRetrieval, validateDataset, loadDataset } = require('../uniCloud-aliyun/cloudfunctions/rag/evaluator')
const dataset = require('../uniCloud-aliyun/cloudfunctions/rag/resources/retrieval-eval.json')
const sources = require('../docs/rag/knowledge-source.json')
const baseline = require('./fixtures/rag-retrieval-baseline-v1.json')
const top = (...ids) => ids.map((knowledgeId, i) => ({ rank: i + 1, knowledgeId, title: '测试标题', similarity: 0.6 - i * 0.1 }))
const vector = (x, y = 0) => [x, y, ...Array(510).fill(0)]

test('Baseline V1 冻结：Retriever 字节、原7条标签与1条 exploratory 完全不变', () => {
  const raw = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag/retriever.js'))
  assert.equal(crypto.createHash('sha256').update(raw).digest('hex'), baseline.retrieverSha256)
  assert.deepEqual(dataset.queries.slice(0, 8), baseline.dataset.queries.slice(0, 8))
  for (const field of ['embeddingModel', 'embeddingDimension', 'topK', 'expectedKnowledgeCount', 'knowledgeSourceSha256']) {
    assert.equal(dataset[field], baseline.dataset[field])
  }
})

for (const [relevant, retrieved, expected] of [
  [['a'], ['a', 'x', 'y'], 1],
  [['a', 'b'], ['a', 'x', 'y'], 0.5],
  [['a', 'b'], ['a', 'b', 'x'], 1],
  [['a', 'b', 'c', 'd'], ['a', 'b', 'c'], 1],
  [['a', 'b', 'c', 'd', 'e'], ['a', 'b', 'c'], 1],
  [['a', 'b', 'c', 'd'], ['a'], 1 / 3],
  [['a', 'b'], ['x'], 0],
  [['a'], [], 0]
]) {
  test(`Coverage 分母 min(relevant,3)：${relevant.length} 标签 / ${retrieved.join(',')} → ${expected}`, () => {
    assert.equal(calculateMetrics(relevant, top(...retrieved)).coverageAt3, expected)
  })
}

test('Baseline 已报告命中数量复算：Recall 0.80，Coverage 20/21；不冒充真实排名', () => {
  const labeled = baseline.dataset.queries.filter(item => item.kind === 'labeled')
  const hits = [3, 3, 2, 3, 2, 3, 1]
  // 这里只验证已报告命中数量对应的公式，ID 选择不是历史云端排名记录。
  const results = labeled.map((item, i) => top(...item.relevantKnowledgeIds.slice(0, hits[i])))
  const summary = summarizeEvaluation({ queries: labeled }, results)
  assert.ok(Math.abs(summary.averageRecallAt3 - baseline.reportedResults.averageRecallAt3) < 1e-12)
  assert.ok(Math.abs(summary.averageCoverageAt3 - 20 / 21) < 1e-12)
  assert.equal(summary.queries.filter(item => item.coverageAt3 === 1).length, 6)
})

test('三组 top1 分布分别统计，保留负分，labeled 第三名与最低命中分数正确', () => {
  const kinds = ['labeled', 'labeled', 'external-ood', 'external-ood', 'unsupported-domain', 'unsupported-domain']
  const queries = kinds.map((kind, i) => ({ id: String(i), query: String(i), kind,
    relevantKnowledgeIds: kind === 'labeled' ? ['a', 'b'] : [] }))
  const scores = [[0.9, 0.6, 0.2], [0.5, 0.4], [-0.1, -0.2, -0.3], [0.3], [0.7], [0.8]]
  const rankings = scores.map(values => top(...['a', 'b', 'x'].slice(0, values.length))
    .map((row, i) => ({ ...row, similarity: values[i], embedding: vector(1) })))
  const result = summarizeEvaluation({ queries }, rankings)
  for (const [key, min, max, average] of [['labeled', 0.5, 0.9, 0.7], ['externalOod', -0.1, 0.3, 0.1], ['unsupportedDomain', 0.7, 0.8, 0.75]]) {
    assert.equal(result[key].count, 2)
    assert.equal(result[key].scoredCount, 2)
    assert.equal(result[key].minTop1Similarity, min)
    assert.equal(result[key].maxTop1Similarity, max)
    assert.ok(Math.abs(result[key].averageTop1Similarity - average) < 1e-12)
  }
  assert.equal(result.queries[0].thirdSimilarity, 0.2)
  assert.equal(result.queries[0].lowestRelevantSimilarityInTop3, 0.6)
  assert.equal(result.queries[1].thirdSimilarity, null)
  assert.deepEqual(result.unsupportedDomain.queries[0].top3Titles, ['测试标题'])
  assert.ok(!JSON.stringify(result).includes('embedding'))
})

test('无命中时最低相关分数为null；无结果的分布不伪造0分', () => {
  const result = summarizeEvaluation({ queries: [
    { id: 'l', query: 'l', kind: 'labeled', relevantKnowledgeIds: ['a'] },
    { id: 'u', query: 'u', kind: 'unsupported-domain', relevantKnowledgeIds: [] }
  ] }, [top('x'), []])
  assert.equal(result.queries[0].lowestRelevantSimilarityInTop3, null)
  assert.equal(result.unsupportedDomain.count, 1)
  assert.equal(result.unsupportedDomain.scoredCount, 0)
  for (const group of [result.unsupportedDomain, result.externalOod]) {
    assert.equal(group.minTop1Similarity, null)
    assert.equal(group.maxTop1Similarity, null)
    assert.equal(group.averageTop1Similarity, null)
  }
})

test('只有两类无答案时不生成 Recall/Coverage 平均，也不能给无答案添加标签', () => {
  const queries = ['external-ood', 'unsupported-domain'].map(kind => ({ id: kind, query: kind, kind, relevantKnowledgeIds: [] }))
  const result = summarizeEvaluation({ queries }, [top('a'), top('a')])
  assert.equal(result.evaluatedRecallQueries, 0)
  assert.equal(result.averageRecallAt3, null)
  assert.equal(result.averageCoverageAt3, null)
  assert.equal(result.hitAt3Count, 0)
  queries[1].relevantKnowledgeIds = ['a']
  assert.throws(() => summarizeEvaluation({ queries }, [top('a'), top('a')]), /EVAL_DATASET_INVALID/)
})

test('固定19条 Query：全部标签真实存在，7 labeled / 1 exploratory / 6 external / 5 unsupported', () => {
  assert.doesNotThrow(() => validateDataset(dataset, sources))
  assert.deepEqual(loadDataset().sources, sources)
  const raw = fs.readFileSync(path.join(__dirname, '../docs/rag/knowledge-source.json'))
  assert.equal(crypto.createHash('sha256').update(raw).digest('hex'), dataset.knowledgeSourceSha256)
  assert.deepEqual(dataset.queries.map(x => x.query), ['我想吃牛肉', '有什么鸡肉？', '想吃酸甜的', '哪些菜有辣椒？',
    '有什么饮料？', '有什么比较清爽的？', '我想吃点爽脆的', '想看看主要配料是什么', '今天香港天气怎么样？', 'Python 怎么安装？',
    '2 加 2 等于多少？', '什么是光合作用？', 'iPhone 怎么截屏？', '给我写一首短诗。',
    '你们几点营业？', '可以开发票吗？', '餐厅有停车位吗？', '可以外送吗？', '支持什么付款方式？'])
  assert.equal(dataset.queries.filter(x => x.kind === 'labeled').length, 7)
})

test('Recall@3 部分命中：两次命中 / 四个相关标签 = 0.5，Hit 为 true', () => {
  assert.deepEqual(calculateMetrics(['a', 'b', 'c', 'd'], top('b', 'x', 'd')), {
    hits: 2, expectedRelevantCount: 4, retrievedRelevantIds: ['b', 'd'], missedRelevantIds: ['a', 'c'],
    recallAt3: 0.5, coverageAt3: 2 / 3, hitAt3: true
  })
})
test('Recall 全部命中为1', () => assert.equal(calculateMetrics(['a', 'b'], top('a', 'b', 'x')).recallAt3, 1))
test('完全未命中：Recall 0，Hit false，保留全部 missed IDs', () => {
  const result = calculateMetrics(['a', 'b'], top('x', 'y', 'z'))
  assert.equal(result.recallAt3, 0)
  assert.equal(result.hitAt3, false)
  assert.equal(result.hits, 0)
  assert.deepEqual(result.missedRelevantIds, ['a', 'b'])
})
test('Top-3不足三条按实际命中计算，分母仍为相关标签总数', () => {
  assert.equal(calculateMetrics(['a', 'b', 'c', 'd'], top('a')).recallAt3, 0.25)
  assert.equal(calculateMetrics(['a'], []).recallAt3, 0)
  assert.equal(calculateMetrics(['a'], []).hitAt3, false)
})
test('重复检索 ID 拒绝，不重复计 hits', () => assert.throws(() => calculateMetrics(['a'], top('a', 'a')), /EVAL_RESULT_INVALID/))
test('重复/空 relevant 拒绝，不歪曲分母', () => {
  assert.throws(() => calculateMetrics(['a', 'a'], top('a')), /EVAL_LABELS_INVALID/)
  assert.throws(() => calculateMetrics([], top('a')), /EVAL_LABELS_INVALID/)
})
test('超过3条、无效 rank 或 similarity 拒绝', () => {
  assert.throws(() => calculateMetrics(['a'], top('a', 'b', 'c', 'd')), /EVAL_RESULT_INVALID/)
  for (const patch of [{ rank: 0 }, { similarity: Infinity }, { similarity: '0.9' }]) {
    assert.throws(() => calculateMetrics(['a'], [{ ...top('a')[0], ...patch }]), /EVAL_RESULT_INVALID/)
  }
})

test('按 Query 宏平均，OOD/exploratory 不参与 Recall 或 Hit 分母', () => {
  const data = { queries: [
    { id: 'q1', query: 'q1', kind: 'labeled', relevantKnowledgeIds: ['a', 'b'] },
    { id: 'q2', query: 'q2', kind: 'labeled', relevantKnowledgeIds: ['c'] },
    { id: 'q3', query: 'q3', kind: 'exploratory', relevantKnowledgeIds: [] },
    { id: 'q4', query: 'q4', kind: 'external-ood', relevantKnowledgeIds: [] },
    { id: 'q5', query: 'q5', kind: 'unsupported-domain', relevantKnowledgeIds: [] }
  ] }
  const result = summarizeEvaluation(data, [top('a', 'x'), top('c'), top('z'), top('a', 'b', 'c'), top('a')])
  assert.equal(result.totalQueries, 5)
  assert.equal(result.evaluatedRecallQueries, 2)
  assert.equal(result.averageRecallAt3, 0.75)
  assert.equal(result.averageCoverageAt3, 0.75)
  assert.equal(result.unsupportedDomain.count, 1)
  assert.equal(result.unsupportedDomain.queries[0].coverageAt3, undefined)
  assert.equal(result.hitAt3Count, 2)
  assert.equal(result.exploratoryQueries, 1)
  assert.equal(result.queries[2].recallAt3, null)
  assert.equal(result.queries[2].hitAt3, null)
  assert.equal(result.externalOod.queries[0].recallAt3, undefined)
})
test('OOD保存原相似度，不当成概率，不过滤负分、不返回 embedding', () => {
  const data = { queries: [{ id: 'ood', query: 'ood', kind: 'external-ood', relevantKnowledgeIds: [] }] }
  const ranking = top('a', 'b', 'c')
  ranking[0].similarity = 0.576992
  ranking[1].similarity = 0
  ranking[2].similarity = -0.123456
  ranking[0].embedding = Array(512).fill(1)
  const result = summarizeEvaluation(data, [ranking])
  assert.equal(result.averageRecallAt3, null)
  assert.equal(result.evaluatedRecallQueries, 0)
  assert.equal(result.externalOod.queries[0].top1Similarity, 0.576992)
  assert.deepEqual(result.externalOod.queries[0].top3Similarities, [0.576992, 0, -0.123456])
  assert.deepEqual(result.externalOod.queries[0].top3KnowledgeIds, ['a', 'b', 'c'])
  assert.ok(!JSON.stringify(result).includes('"embedding":'))
})
test('OOD没有结果时最高相似度为null，而不是误写0', () => {
  const result = summarizeEvaluation({ queries: [{ id: 'ood', query: 'ood', kind: 'external-ood', relevantKnowledgeIds: [] }] }, [[]])
  assert.equal(result.externalOod.queries[0].top1Similarity, null)
  assert.deepEqual(result.externalOod.queries[0].top3Similarities, [])
})
test('评测未完整返回19个结果时拒绝汇总', () => assert.throws(() => summarizeEvaluation(dataset, [top('a')]), /EVAL_RESULT_INVALID/))

for (const kind of ['unknown-id', 'duplicate-label', 'duplicate-query', 'ood-label', 'unsupported-label', 'invalid-kind', 'wrong-counts', 'empty-labeled']) {
  test(`数据集拒绝 ${kind}`, () => {
    const copy = structuredClone(dataset)
    if (kind === 'unknown-id') copy.queries[0].relevantKnowledgeIds.push('not-in-source')
    if (kind === 'duplicate-label') copy.queries[0].relevantKnowledgeIds.push(copy.queries[0].relevantKnowledgeIds[0])
    if (kind === 'duplicate-query') copy.queries[1].query = copy.queries[0].query
    if (kind === 'ood-label') copy.queries[9].relevantKnowledgeIds = ['dish-1-description']
    if (kind === 'unsupported-label') copy.queries[14].relevantKnowledgeIds = ['dish-1-description']
    if (kind === 'invalid-kind') copy.queries[14].kind = 'out-of-domain'
    if (kind === 'wrong-counts') copy.queries[14].kind = 'external-ood'
    if (kind === 'empty-labeled') copy.queries[0].relevantKnowledgeIds = []
    assert.throws(() => validateDataset(copy, sources), /EVAL_DATASET_INVALID/)
  })
}

function setup(options = {}) {
  const requests = []
  let reads = 0
  const records = structuredClone(sources).map(item => ({ ...item, embedding: vector(1),
    embeddingModel: dataset.embeddingModel, embeddingDimension: 512 }))
  if (options.records) options.records(records)
  const db = { collection(name) {
    assert.equal(name, 'knowledge_chunks')
    return {
      where(value) { assert.deepEqual(value, { verified: true }); return this },
      orderBy() { return this }, skip() { return this }, limit() { return this }, field() { return this },
      async get() { reads++; if (options.dbFails) throw new Error('Authorization test-only-secret'); return { data: records } },
      add() { assert.fail('评测不得写库') }, update() { assert.fail('评测不得更新') }, remove() { assert.fail('评测不得删除') }
    }
  } }
  const vectors = Array.from({ length: dataset.queries.length }, (_, i) => i % 3 === 0 ? vector(1) : i % 3 === 1 ? vector(0, 1) : vector(-1))
  const httpclient = { async request(url, config) {
    requests.push({ url, config })
    if (options.networkFails) throw new Error('Authorization test-only-secret')
    if (options.response) return options.response
    const data = vectors.map((embedding, index) => ({ index, embedding }))
    if (options.mutate) options.mutate(data)
    return { status: 200, data: JSON.stringify({ data }) }
  } }
  return { requests, reads: () => reads, async run() {
    const result = await evaluateRetrieval({ db, httpclient, env: {
      DASHSCOPE_API_KEY: 'test-only-secret', LLM_BASE_URL: 'https://example.invalid/v1',
      EMBEDDING_MODEL: dataset.embeddingModel, EMBEDDING_DIMENSION: '512'
    } })
    assert.ok(!JSON.stringify(result).includes('test-only-secret'))
    assert.ok(!JSON.stringify(result).includes('Authorization'))
    assert.ok(!JSON.stringify(result).includes('"embedding":'))
    return result
  } }
}

test('整套固定19条只读评测，一次批量请求；乱序index仍映射正确', async () => {
  const app = setup({ mutate: data => data.reverse() })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.totalCandidates, 21)
  assert.equal(result.totalQueries, 19)
  assert.equal(result.evaluatedRecallQueries, 7)
  assert.equal(result.queries.length, 8)
  assert.equal(result.externalOod.queries.length, 6)
  assert.equal(result.unsupportedDomain.queries.length, 5)
  assert.equal(result.evaluationVersion, 2)
  assert.equal(result.retrieverBaselineVersion, 1)
  assert.equal(result.exploratoryQueries, 1)
  assert.equal(app.reads(), 1)
  assert.equal(app.requests.length, 1)
  assert.deepEqual(app.requests[0].config.data, { model: dataset.embeddingModel,
    input: dataset.queries.map(item => item.query), dimensions: 512, encoding_format: 'float' })
  assert.equal(app.requests[0].url, 'https://example.invalid/v1/embeddings')
  assert.equal(app.requests[0].config.method, 'POST')
  assert.ok(result.queries[0].top3.every(item => item.similarity === 1))
  assert.ok(result.queries[1].top3.every(item => item.similarity === 0))
  assert.ok(result.queries[2].top3.every(item => item.similarity === -1))
  assert.deepEqual(result.externalOod.queries[0].top3Similarities, [-1, -1, -1])
  assert.deepEqual(result.externalOod.queries[1].top3Similarities, [1, 1, 1])
})

for (const [name, change] of [
  ['数量变化', records => records.pop()],
  ['text变化', records => { records[0].text += '改动' }],
  ['ID重复', records => { records[1] = { ...records[0] } }],
  ['未审核', records => { records[0].verified = false }]
]) {
  test(`云端候选 ${name}：拒绝不可比的评测，不消耗模型`, async () => {
    const app = setup({ records: change })
    assert.equal((await app.run()).errCode, 'EVAL_CORPUS_MISMATCH')
    assert.equal(app.requests.length, 0)
  })
}
test('损坏或不兼容向量导致整套评测失败，不输出部分平均值', async () => {
  for (const patch of [{ embeddingModel: 'wrong' }, { embeddingDimension: 256 }, { embedding: vector(0) }]) {
    const result = await setup({ records: data => Object.assign(data[0], patch) }).run()
    assert.notEqual(result.errCode, 0)
    assert.equal(result.averageRecallAt3, undefined)
  }
})
for (const [name, mutate] of [
  ['重复 index', data => { data[1].index = 0 }],
  ['缺失 index', data => { delete data[1].index }],
  ['数量少', data => data.pop()],
  ['维度错', data => data[1].embedding.pop()],
  ['零向量', data => { data[1].embedding = vector(0) }],
  ['非数字', data => { data[1].embedding[0] = '1' }]
]) {
  test(`Embedding ${name} 拒绝，不输出部分结果`, async () => {
    const result = await setup({ mutate }).run()
    assert.equal(result.errCode, 'EVAL_EMBEDDING_INVALID')
    assert.equal(result.queries, undefined)
  })
}
test('数据库、网络和API错误安全返回', async () => {
  for (const options of [{ dbFails: true }, { networkFails: true },
    { response: { status: 401, data: 'Authorization test-only-secret' } },
    { response: { status: 200, data: '{"error":"test-only-secret"}' } }]) {
    assert.notEqual((await setup(options).run()).errCode, 0)
  }
})
test('管理云函数拒绝客户端伪造来源；server执行不转发参数', async () => {
  const code = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag-eval-admin/index.js'), 'utf8')
  let calls = 0
  const sandbox = { exports: {}, uniCloud: { importObject: name => {
    assert.equal(name, 'rag')
    return { evaluateRetrieval: async (...args) => { assert.equal(args.length, 0); calls++; return { errCode: 0 } } }
  } } }
  vm.runInNewContext(code, sandbox)
  assert.equal((await sandbox.exports.main({ clientInfo: { source: 'server' } }, { SOURCE: 'client' })).errCode, 'EVAL_FORBIDDEN')
  assert.equal(calls, 0)
  assert.equal((await sandbox.exports.main({ query: 'ignored' }, { SOURCE: 'server' })).errCode, 0)
  assert.equal(calls, 1)
})
test('rag评测方法拒绝客户端/HTTP/无来源，云函数入口使用固定集', async () => {
  const code = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag/index.obj.js'), 'utf8')
  let calls = 0
  const sandbox = { module: { exports: {} }, uniCloud: { database: () => ({}), httpclient: {} },
    require: name => name === './evaluator' ? { evaluateRetrieval: async args => {
      assert.deepEqual(Object.keys(args).sort(), ['db', 'httpclient']); calls++; return { errCode: 0 }
    } } : require(name) }
  vm.runInNewContext(code, sandbox)
  const method = sandbox.module.exports.evaluateRetrieval
  for (const source of ['client', 'http', undefined]) assert.equal((await method.call({ getClientInfo: () => ({ source }) })).errCode, 'EVAL_FORBIDDEN')
  assert.equal(calls, 0)
  await method.call({ getClientInfo: () => ({ source: 'function' }) }, { query: 'ignored' })
  assert.equal(calls, 1)
})
