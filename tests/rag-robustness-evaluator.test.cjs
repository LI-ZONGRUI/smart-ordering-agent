const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const vm = require('node:vm')
const { summarizeRobustness, evaluateRobustness, validateDataset, loadDataset } = require('../uniCloud-aliyun/cloudfunctions/rag/robustness-evaluator')
const dataset = require('../uniCloud-aliyun/cloudfunctions/rag/resources/retrieval-robustness-eval.json')
const sources = require('../docs/rag/knowledge-source.json')
const frozen = require('./fixtures/rag-robustness-frozen-files.json')
const root = path.join(__dirname, '..')
const vector = (x, y = 0) => [x, y, ...Array(510).fill(0)]
const query = (id, kind, relevant = []) => ({ id, query: id, kind, relevantKnowledgeIds: relevant })
const top = (scores, ids = ['a', 'b', 'c']) => scores.map((similarity, i) => ({
  rank: i + 1, knowledgeId: ids[i], title: `标题${ids[i]}`, similarity, embedding: vector(1)
}))

test('9 个冻结文件逐字节未变：历史数据、Evaluator、Retriever、Indexer、知识源和 schema/index', () => {
  for (const [file, hash] of Object.entries(frozen)) {
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex'), hash, file)
  }
})
test('24 条固定集：11 supported、1 exploratory、12 hard；标签基于真实知识', () => {
  assert.doesNotThrow(() => validateDataset(dataset, sources))
  assert.deepEqual(loadDataset().dataset, dataset)
  assert.deepEqual(loadDataset().sources, sources)
  assert.equal(dataset.queries.filter(item => item.kind === 'supported-paraphrase').length, 11)
  assert.equal(dataset.queries.filter(item => item.kind === 'unsupported-domain-hard').length, 12)
  assert.equal(dataset.queries.find(item => item.kind === 'supported-exploratory').query, '想吃点爽口的')
  assert.deepEqual(dataset.queries.find(item => item.query === '什么里面有番茄？').relevantKnowledgeIds,
    ['dish-2-description', 'dish-2-ingredients', 'dish-3-ingredients'])
})
for (const [name, change] of [
  ['未知kind', d => { d.queries[0].kind = 'labeled' }],
  ['hard标签', d => { d.queries[12].relevantKnowledgeIds = ['dish-1-description'] }],
  ['exploratory标签', d => { d.queries[11].relevantKnowledgeIds = ['dish-3-taste'] }],
  ['空supported标签', d => { d.queries[0].relevantKnowledgeIds = [] }],
  ['不存在ID', d => { d.queries[0].relevantKnowledgeIds = ['nonexistent'] }],
  ['重复标签', d => { d.queries[0].relevantKnowledgeIds.push(d.queries[0].relevantKnowledgeIds[0]) }],
  ['重复query', d => { d.queries[1].query = d.queries[0].query }],
  ['错误dimension', d => { d.embeddingDimension = 256 }],
  ['数量错误', d => { d.queries.pop() }]
]) test(`Dataset 拒绝 ${name}`, () => {
  const copy = structuredClone(dataset)
  change(copy)
  assert.throws(() => validateDataset(copy, sources), /ROBUSTNESS_DATASET_INVALID/)
})

for (const [supportedScore, unsupportedScore, overlap] of [[0.5, 0.4, false], [0.4, 0.4, true], [0.3, 0.4, true]]) {
  test(`Separation ${supportedScore} - ${unsupportedScore}：hasOverlap=${overlap}`, () => {
    const data = { queries: [query('s', 'supported-paraphrase', ['a']), query('u', 'unsupported-domain-hard')] }
    const result = summarizeRobustness(data, [top([supportedScore]), top([unsupportedScore])])
    const analysis = result.overlapAnalysis
    assert.equal(analysis.supportedMinTop1, supportedScore)
    assert.equal(analysis.unsupportedMaxTop1, unsupportedScore)
    assert.equal(analysis.separationGap, supportedScore - unsupportedScore)
    assert.equal(analysis.hasOverlap, overlap)
    assert.deepEqual(analysis.hardNegativeQueries.map(item => item.query), overlap ? ['u'] : [])
    assert.deepEqual(analysis.lowScoreSupportedQueries.map(item => item.query), overlap ? ['s'] : [])
  })
}
test('多个样本的极值、平均和 overlap 两侧案例准确；不隐藏高分错误 Top1', () => {
  const data = { queries: [query('s1', 'supported-paraphrase', ['a']), query('s2', 'supported-paraphrase', ['a']),
    query('u1', 'unsupported-domain-hard'), query('u2', 'unsupported-domain-hard'), query('u3', 'unsupported-domain-hard')] }
  const result = summarizeRobustness(data, [top([0.4, 0.2]), top([0.9, 0.8], ['x', 'a']), top([0.3]), top([0.4]), top([0.5])])
  const supported = result.supportedParaphrase
  assert.equal(supported.minTop1Similarity, 0.4)
  assert.equal(supported.maxTop1Similarity, 0.9)
  assert.equal(supported.averageTop1Similarity, 0.65)
  assert.equal(supported.queries[1].top1IsRelevant, false)
  assert.equal(supported.top1RelevantCount, 1)
  assert.equal(supported.hitAt3Count, 2)
  assert.equal(result.unsupportedDomainHard.maxTop1Similarity, 0.5)
  assert.ok(Math.abs(result.unsupportedDomainHard.averageTop1Similarity - 0.4) < 1e-12)
  assert.deepEqual(result.overlapAnalysis.hardNegativeQueries.map(x => x.query), ['u2', 'u3'])
  assert.deepEqual(result.overlapAnalysis.lowScoreSupportedQueries.map(x => x.query), ['s1'])
})
test('unsupported 与 exploratory 不污染 Recall/Coverage 或 supported 极值', () => {
  const data = { queries: [query('s1', 'supported-paraphrase', ['a', 'b', 'c', 'd']),
    query('s2', 'supported-paraphrase', ['a']), query('u', 'unsupported-domain-hard'),
    query('e', 'supported-exploratory')] }
  const result = summarizeRobustness(data, [top([0.6, 0.5, 0.4]), top([0.5], ['x']), top([0.7]), top([-1])])
  assert.equal(result.supportedParaphrase.averageRecallAt3, 0.375)
  assert.equal(result.supportedParaphrase.averageCoverageAt3, 0.5)
  assert.equal(result.supportedParaphrase.count, 2)
  assert.equal(result.overlapAnalysis.supportedMinTop1, 0.5)
  assert.equal(result.supportedExploratory.queries[0].recallAt3, null)
  assert.equal(result.unsupportedDomainHard.queries[0].recallAt3, undefined)
})
test('负相似度保留为 number，不返回完整向量或私有字段', () => {
  const result = summarizeRobustness({ queries: [query('u', 'unsupported-domain-hard')] }, [top([-0.123456, -0.3])])
  const row = result.unsupportedDomainHard.queries[0]
  assert.equal(row.top1Similarity, -0.123456)
  assert.equal(typeof row.top1Similarity, 'number')
  assert.deepEqual(row.top3Similarities, [-0.123456, -0.3])
  assert.deepEqual(row.top3KnowledgeIds, ['a', 'b'])
  assert.equal(row.top1Title, '标题a')
  assert.ok(!JSON.stringify(result).includes('embedding'))
})
for (const queries of [[], [query('s', 'supported-paraphrase', ['a'])], [query('u', 'unsupported-domain-hard')]]) {
  test(`空分组安全处理（${queries.map(x => x.kind)}）`, () => {
    const result = summarizeRobustness({ queries }, queries.map(() => top([0.4])))
    assert.equal(result.overlapAnalysis.hasOverlap, null)
    assert.equal(result.overlapAnalysis.separationGap, null)
    if (!result.supportedParaphrase.count) assert.equal(result.supportedParaphrase.averageRecallAt3, null)
  })
}
test('缺失 Top1 不伪造分离成功；Top3 少于3条可计分', () => {
  const data = { queries: [query('s', 'supported-paraphrase', ['a', 'b']), query('u', 'unsupported-domain-hard')] }
  const result = summarizeRobustness(data, [top([0.4]), []])
  assert.equal(result.supportedParaphrase.averageRecallAt3, 0.5)
  assert.equal(result.overlapAnalysis.hasOverlap, null)
  assert.equal(result.unsupportedDomainHard.maxTop1Similarity, null)
})
test('非法/重复排名、非数字分数和未完整报告被拒绝', () => {
  const data = { queries: [query('s', 'supported-paraphrase', ['a'])] }
  for (const ranking of [top([0.8, 0.7], ['a', 'a']), top(['0.7']), top([Infinity]), top([NaN])]) {
    assert.throws(() => summarizeRobustness(data, [ranking]), /ROBUSTNESS_RESULT_INVALID/)
  }
  assert.throws(() => summarizeRobustness(data, []), /ROBUSTNESS_RESULT_INVALID/)
})

function setup(options = {}) {
  const requests = []
  let reads = 0
  const records = sources.map(item => ({ ...item, embedding: vector(1), embeddingModel: dataset.embeddingModel, embeddingDimension: 512 }))
  if (options.records) options.records(records)
  const db = { collection(name) {
    assert.equal(name, 'knowledge_chunks')
    return { where(value) { assert.deepEqual(value, { verified: true }); return this },
      orderBy() { return this }, skip() { return this }, limit() { return this }, field() { return this },
      async get() { reads++; if (options.dbFail) throw new Error('secret-test Authorization'); return { data: records } },
      add() { assert.fail('禁止写库') }, update() { assert.fail('禁止更新') }, remove() { assert.fail('禁止删除') } }
  } }
  const httpclient = { async request(url, config) {
    const batchIndex = requests.length
    requests.push({ url, config })
    if (options.networkFail || (options.secondFail && batchIndex === 1)) throw new Error('secret-test Authorization')
    if (options.response) return options.response
    const data = config.data.input.map((_, index) => ({ index, embedding: batchIndex ? vector(-1) : index % 2 ? vector(0, 1) : vector(1) }))
    if (options.mutate) options.mutate(data)
    return { status: 200, data: JSON.stringify({ data }) }
  } }
  return { requests, reads: () => reads, async run() {
    const result = await evaluateRobustness({ db, httpclient, env: {
      DASHSCOPE_API_KEY: 'secret-test', LLM_BASE_URL: 'https://example.invalid/v1',
      EMBEDDING_MODEL: dataset.embeddingModel, EMBEDDING_DIMENSION: '512'
    } })
    const serialized = JSON.stringify(result)
    assert.ok(!serialized.includes('secret-test') && !serialized.includes('Authorization') && !serialized.includes('"embedding":'))
    return result
  } }
}
test('24 Query 两批12条、只读同份21候选、乱序index正确对齐，不改排名', async () => {
  const app = setup({ mutate: rows => rows.reverse() })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.totalQueries, 24)
  assert.equal(result.totalCandidates, 21)
  assert.equal(result.topK, 3)
  assert.equal(result.supportedParaphrase.count, 11)
  assert.equal(result.supportedExploratory.count, 1)
  assert.equal(result.unsupportedDomainHard.count, 12)
  assert.equal(app.reads(), 1)
  assert.equal(app.requests.length, 2)
  app.requests.forEach(({ url, config }, i) => {
    assert.equal(url, 'https://example.invalid/v1/embeddings')
    assert.equal(config.method, 'POST')
    assert.deepEqual(config.data, { model: dataset.embeddingModel,
      input: dataset.queries.slice(i * 12, (i + 1) * 12).map(item => item.query), dimensions: 512, encoding_format: 'float' })
  })
  assert.equal(result.supportedParaphrase.queries[0].top1Similarity, 1)
  assert.equal(result.supportedParaphrase.queries[1].top1Similarity, 0)
  assert.ok(result.unsupportedDomainHard.queries.every(item => item.top3.every(row => row.similarity === -1)))
})
for (const [name, mutate] of [
  ['重复index', rows => { rows[1].index = 0 }], ['缺失index', rows => { delete rows[1].index }],
  ['越界index', rows => { rows[1].index = 12 }], ['数量错', rows => rows.pop()],
  ['维度错', rows => rows[0].embedding.pop()], ['非数字', rows => { rows[0].embedding[0] = '1' }],
  ['零向量', rows => { rows[0].embedding = vector(0) }]
]) test(`Embedding ${name} 安全失败`, async () => {
  const result = await setup({ mutate }).run()
  assert.equal(result.errCode, 'ROBUSTNESS_EMBEDDING_INVALID')
  assert.equal(result.overlapAnalysis, undefined)
})
for (const options of [{ networkFail: true }, { secondFail: true }, { dbFail: true },
  { response: { status: 401, data: 'secret-test Authorization' } },
  { response: { status: 200, data: 'secret-test Authorization' } }]) {
  test(`HTTP/DB/第二批失败不返回部分指标 ${JSON.stringify(Object.keys(options))}`, async () => {
    const result = await setup(options).run()
    assert.notEqual(result.errCode, 0)
    assert.equal(result.supportedParaphrase, undefined)
  })
}
for (const change of [rows => rows.pop(), rows => { rows[0].text += 'changed' },
  rows => { rows[0].embeddingModel = 'wrong' }, rows => { rows[0].embedding = vector(0) }]) {
  test('冻结语料或向量异常在消耗API前拒绝', async () => {
    const app = setup({ records: change })
    assert.equal((await app.run()).errCode, 'ROBUSTNESS_CORPUS_INVALID')
    assert.equal(app.requests.length, 0)
  })
}
test('管理入口拒绝客户端/HTTP来源；event 不能指定query或伪造权限', async () => {
  const code = fs.readFileSync(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag-robustness-eval-admin/index.js'), 'utf8')
  let calls = 0
  const sandbox = { exports: {}, uniCloud: { importObject: name => {
    assert.equal(name, 'rag')
    return { evaluateRobustness: async (...args) => { assert.equal(args.length, 0); calls++; return { errCode: 0 } } }
  } } }
  vm.runInNewContext(code, sandbox)
  for (const SOURCE of ['client', 'http', undefined]) {
    assert.equal((await sandbox.exports.main({ SOURCE: 'server' }, { SOURCE })).errCode, 'ROBUSTNESS_FORBIDDEN')
  }
  assert.equal(calls, 0)
  assert.equal((await sandbox.exports.main({ query: 'ignored' }, { SOURCE: 'server' })).errCode, 0)
  assert.equal(calls, 1)
})
test('rag Robustness 方法拒绝客户端且不转发参数；页面无入口', async () => {
  const code = fs.readFileSync(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag/index.obj.js'), 'utf8')
  let calls = 0
  const sandbox = { module: { exports: {} }, uniCloud: { database: () => ({}), httpclient: {} },
    require: name => name === './robustness-evaluator' ? { evaluateRobustness: async args => {
      assert.deepEqual(Object.keys(args).sort(), ['db', 'httpclient']); calls++; return { errCode: 0 }
    } } : require(name) }
  vm.runInNewContext(code, sandbox)
  for (const source of ['client', 'http', undefined]) {
    assert.equal((await sandbox.module.exports.evaluateRobustness.call({ getClientInfo: () => ({ source }) })).errCode, 'ROBUSTNESS_FORBIDDEN')
  }
  assert.equal(calls, 0)
  await sandbox.module.exports.evaluateRobustness.call({ getClientInfo: () => ({ source: 'function' }) }, { query: 'ignored' })
  assert.equal(calls, 1)
  function check(folder) {
    for (const entry of fs.readdirSync(folder, { withFileTypes: true })) {
      const file = path.join(folder, entry.name)
      if (entry.isDirectory()) check(file)
      else if (/\.(vue|js)$/.test(file)) assert.doesNotMatch(fs.readFileSync(file, 'utf8'), /evaluateRobustness|rag-robustness-eval-admin/)
    }
  }
  check(path.join(root, 'src'))
})
