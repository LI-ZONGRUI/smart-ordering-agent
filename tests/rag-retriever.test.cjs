const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { cosineSimilarity, testRetrieval } = require('../uniCloud-aliyun/cloudfunctions/rag/retriever')

const MODEL = 'qwen3.7-text-embedding-flash'
const QUERY = '有什么比较清爽的？'
const vector = (x, y = 0) => [x, y, ...Array(510).fill(0)]
const chunk = (knowledgeId, embedding = vector(1)) => ({
  _id: knowledgeId, knowledgeId, dishId: 'dish-test', scope: 'dish', type: 'taste',
  title: '测试标题', text: '测试知识正文', verified: true, embedding,
  embeddingModel: MODEL, embeddingDimension: 512
})
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-12)

test('cosine 相同方向接近 1', () => close(cosineSimilarity([1, 2, 3], [2, 4, 6]), 1))
test('cosine 正交接近 0', () => close(cosineSimilarity([1, 0], [0, 1]), 0))
test('cosine 相反方向接近 -1', () => close(cosineSimilarity([1, 2], [-1, -2]), -1))
test('cosine 非单位向量遵循 dot / (normA * normB)', () => close(cosineSimilarity([1, 2], [3, 4]), 11 / Math.sqrt(125)))
test('cosine 长度不同拒绝', () => assert.throws(() => cosineSimilarity([1], [1, 2]), /COSINE_LENGTH_MISMATCH/))
for (const [a, b] of [[[0, 0], [1, 0]], [[1, 0], [0, 0]], [[0, 0], [0, 0]]]) {
  test('cosine 任一零向量拒绝', () => assert.throws(() => cosineSimilarity(a, b), /COSINE_ZERO_NORM/))
}
for (const bad of [NaN, Infinity, -Infinity, '1', null, undefined]) {
  test(`cosine 非法元素 ${String(bad)} 拒绝`, () => {
    assert.throws(() => cosineSimilarity([1, bad], [1, 0]), /COSINE_VECTOR_INVALID/)
    assert.throws(() => cosineSimilarity([1, 0], [1, bad]), /COSINE_VECTOR_INVALID/)
  })
}
test('cosine 空数组、非数组及稀疏数组拒绝', () => {
  for (const bad of [[], null, {}, [1, , 2]]) assert.throws(() => cosineSimilarity(bad, [1, 2, 3]), /COSINE_VECTOR_INVALID/)
})
test('cosine 有限大数/小数缩放后仍返回有效结果', () => {
  close(cosineSimilarity([1e308, 1e308], [1e308, 1e308]), 1)
  close(cosineSimilarity([1e-300, 0], [0, 1e-300]), 0)
})

// 本地只模拟 HTTP 和只读数据库。不会调用真实 API，也不使用真实密钥。
function setup(records = [chunk('a'), chunk('b', vector(1, 1)), chunk('c', vector(0, 1))], options = {}) {
  const requests = []
  let reads = 0
  const db = {
    collection(name) {
      assert.equal(name, 'knowledge_chunks')
      let offset = 0, limit = 100
      return {
        where(filter) { assert.deepEqual(filter, { verified: true }); return this },
        orderBy(field, direction) { assert.equal(field, '_id'); assert.equal(direction, 'asc'); return this },
        skip(value) { offset = value; return this },
        limit(value) { limit = value; return this },
        field(fields) { assert.equal(fields.embedding, true); return this },
        async get() {
          reads++
          if (options.databaseFails) throw new Error('Authorization: test-only-secret')
          if (options.databaseResponse) return options.databaseResponse
          const filtered = options.ignoreVerifiedFilter ? records : records.filter(item => item?.verified === true)
          return { data: structuredClone(filtered.slice(offset, offset + limit)) }
        },
        add() { assert.fail('Retrieval 不允许写库') },
        update() { assert.fail('Retrieval 不允许更新') },
        remove() { assert.fail('Retrieval 不允许删除') }
      }
    }
  }
  const httpclient = { async request(url, config) {
    requests.push({ url, config })
    if (options.networkFails) throw new Error('Authorization: test-only-secret')
    if (options.response) return options.response
    return { status: 200, data: JSON.stringify({ data: [{ index: 0, embedding: options.queryVector || vector(1) }] }) }
  } }
  return {
    requests, reads: () => reads,
    async run() {
      const result = await testRetrieval({ db, httpclient, env: {
        DASHSCOPE_API_KEY: 'test-only-secret', LLM_BASE_URL: 'https://example.invalid/v1/',
        EMBEDDING_MODEL: MODEL, EMBEDDING_DIMENSION: '512', ...options.env
      } })
      const serialized = JSON.stringify(result)
      assert.ok(!serialized.includes('test-only-secret'))
      assert.ok(!serialized.includes('Authorization'))
      assert.ok(!serialized.includes('"embedding":'))
      assert.ok(!serialized.includes('vectorPreview'))
      return result
    }
  }
}

test('固定 query 一次 Embedding，21 条完整评分后取正确 Top-3', async () => {
  const records = [chunk('low', vector(-1)), chunk('second', vector(1, 1)), chunk('first', vector(1)),
    chunk('third', vector(1, 2)), ...Array.from({ length: 17 }, (_, i) => chunk(`orthogonal-${i}`, vector(0, 1)))]
  const before = structuredClone(records)
  const app = setup(records)
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.totalCandidates, 21)
  assert.equal(result.topK, 3)
  assert.equal(result.query, QUERY)
  assert.equal(result.embeddingModel, MODEL)
  assert.equal(result.embeddingDimension, 512)
  assert.deepEqual(result.results.map(item => item.knowledgeId), ['first', 'second', 'third'])
  assert.deepEqual(result.results.map(item => item.rank), [1, 2, 3])
  assert.deepEqual(result.results.map(item => item.similarity), [1, 0.707107, 0.447214])
  assert.deepEqual(Object.keys(result.results[0]).sort(), ['rank', 'knowledgeId', 'dishId', 'scope', 'type', 'title', 'text', 'similarity'].sort())
  assert.deepEqual(records, before)
  assert.equal(app.requests.length, 1)
  assert.equal(app.requests[0].url, 'https://example.invalid/v1/embeddings')
  assert.equal(app.requests[0].config.method, 'POST')
  assert.equal(app.requests[0].config.followRedirect, false)
  assert.deepEqual(app.requests[0].config.data, { model: MODEL, input: QUERY, dimensions: 512, encoding_format: 'float' })
})

test('完全相同分数按 knowledgeId 稳定升序，同一 dish 可占多个位置', async () => {
  const app = setup(['z', 'c', 'a', 'b'].map(id => chunk(id)))
  const result = await app.run()
  assert.deepEqual(result.results.map(item => item.knowledgeId), ['a', 'b', 'c'])
  assert.equal(new Set(result.results.map(item => item.dishId)).size, 1)
})

test('先按完整精度排序，再四舍五入；不按显示分数误判并列', async () => {
  const app = setup([chunk('a', vector(1, 0.0002)), chunk('z', vector(1, 0.0001))])
  const result = await app.run()
  assert.deepEqual(result.results.map(item => item.knowledgeId), ['z', 'a'])
  assert.deepEqual(result.results.map(item => item.similarity), [1, 1])
})

test('没有 threshold：负分也原样返回；候选不足三条不补造', async () => {
  const result = await setup([chunk('a', vector(-1)), chunk('b', vector(-1, 1))]).run()
  assert.equal(result.topK, 3)
  assert.equal(result.results.length, 2)
  assert.ok(result.results.every(item => item.similarity < 0))
})

test('type/菜名/正文不加权，restaurant 级也参与同一排序', async () => {
  const records = [chunk('z', vector(1)), { ...chunk('a', vector(1)), scope: 'restaurant', dishId: null,
    type: 'ingredients', title: '普通标题', text: '普通文本' }]
  records[0].text = '清爽清爽清爽'
  const result = await setup(records).run()
  assert.deepEqual(result.results.map(item => item.knowledgeId), ['a', 'z'])
})

test('非 verified 知识不参与，即使数据库过滤未生效也不参与', async () => {
  const result = await setup([chunk('a'), { ...chunk('bad', null), verified: false },
    { ...chunk('not-boolean', null), verified: 'true' }], { ignoreVerifiedFilter: true }).run()
  assert.equal(result.totalCandidates, 1)
  assert.deepEqual(result.results.map(item => item.knowledgeId), ['a'])
})

for (const [name, patch] of [
  ['模型不一致', { embeddingModel: 'another-model' }],
  ['维度不一致', { embeddingDimension: 256 }],
  ['维度类型不对', { embeddingDimension: '512' }],
  ['向量511维', { embedding: Array(511).fill(1) }],
  ['向量非数组', { embedding: null }],
  ['向量非有限数字', { embedding: [Infinity, ...Array(511).fill(0)] }],
  ['向量非数字', { embedding: ['1', ...Array(511).fill(0)] }],
  ['零向量', { embedding: Array(512).fill(0) }],
  ['knowledgeId 空', { knowledgeId: ' ' }],
  ['text 空', { text: '' }],
  ['title 无效', { title: null }],
  ['dishId 无效', { dishId: null }]
]) {
  test(`损坏候选 ${name}：整次明确报错，不返回部分排名`, async () => {
    const app = setup([chunk('a'), chunk('b'), chunk('c'), { ...chunk('bad', vector(-1)), ...patch }])
    const result = await app.run()
    assert.equal(result.errCode, 'RETRIEVAL_DATA_INVALID')
    assert.equal(result.results, undefined)
  })
}

test('重复 knowledgeId 明确数据错误', async () => {
  assert.equal((await setup([chunk('a'), chunk('a')]).run()).errCode, 'RETRIEVAL_DATA_INVALID')
})
test('空集合/全未审核明确返回无候选错误', async () => {
  for (const data of [[], [{ ...chunk('a'), verified: false }]]) {
    assert.equal((await setup(data).run()).errCode, 'RETRIEVAL_EMPTY')
  }
})
test('分页读完候选，不丢失后续页最高分', async () => {
  const data = Array.from({ length: 100 }, (_, i) => chunk(`low-${i}`, vector(0, 1)))
  data.push(chunk('best', vector(1)))
  const app = setup(data)
  const result = await app.run()
  assert.equal(app.reads(), 2)
  assert.equal(result.totalCandidates, 101)
  assert.equal(result.results[0].knowledgeId, 'best')
})
test('数据库异常安全返回', async () => {
  for (const options of [{ databaseFails: true }, { databaseResponse: { data: null } }]) {
    assert.equal((await setup(undefined, options).run()).errCode, 'RETRIEVAL_DATABASE_FAILED')
  }
})

for (const [name, options, code] of [
  ['网络异常', { networkFails: true }, 'RETRIEVAL_QUERY_REQUEST_FAILED'],
  ['HTTP401', { response: { status: 401, data: 'Authorization test-only-secret' } }, 'RETRIEVAL_QUERY_HTTP_ERROR'],
  ['HTTP429', { response: { status: 429, data: 'test-only-secret' } }, 'RETRIEVAL_QUERY_HTTP_ERROR'],
  ['API错误', { response: { status: 200, data: '{"error":"test-only-secret"}' } }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  ['非法JSON', { response: { status: 200, data: 'test-only-secret' } }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  ['data非数组', { response: { status: 200, data: '{"data":{}}' } }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  ['返回数量异常', { response: { status: 200, data: '{"data":[]}' } }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  ['向量维度错误', { queryVector: [1] }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  ['向量非数组', { queryVector: {} }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  ['向量数字错误', { queryVector: ['1', ...Array(511).fill(0)] }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  ['零向量', { queryVector: Array(512).fill(0) }, 'RETRIEVAL_QUERY_RESPONSE_INVALID']
]) {
  test(`Query Embedding ${name}：安全失败、不继续查库`, async () => {
    const app = setup(undefined, options)
    assert.equal((await app.run()).errCode, code)
    assert.equal(app.requests.length, 1)
    assert.equal(app.reads(), 0)
  })
}
test('Query 非有限数字拒绝，不输出响应正文', async () => {
  const raw = JSON.stringify({ data: [{ index: 0, embedding: ['overflow', ...Array(511).fill(0)] }] }).replace('"overflow"', '1e400')
  assert.equal((await setup(undefined, { response: { status: 200, data: raw } }).run()).errCode, 'RETRIEVAL_QUERY_RESPONSE_INVALID')
})

for (const patch of [
  { DASHSCOPE_API_KEY: '' }, { LLM_BASE_URL: '' }, { EMBEDDING_MODEL: '' },
  { EMBEDDING_MODEL: 'qwen3.8-flash' }, { EMBEDDING_DIMENSION: '256' },
  { LLM_BASE_URL: 'http://example.invalid' }, { LLM_BASE_URL: 'https://user:test-only-secret@example.invalid/v1' }
]) {
  test('非法配置在请求前拒绝', async () => {
    const app = setup(undefined, { env: patch })
    assert.equal((await app.run()).errCode, 'RETRIEVAL_CONFIG_INVALID')
    assert.equal(app.requests.length, 0)
  })
}

test('云对象入口不转发客户端任意 query', async () => {
  const code = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag/index.obj.js'), 'utf8')
  let received
  const db = {}
  const httpclient = {}
  const sandbox = { module: { exports: {} }, uniCloud: { database: () => db, httpclient },
    require: name => name === './retriever' ? { testRetrieval: async deps => { received = deps; return { errCode: 0 } } } : require(name) }
  vm.runInNewContext(code, sandbox)
  await sandbox.module.exports.testRetrieval('不要采用客户端输入')
  assert.deepEqual(Object.keys(received).sort(), ['db', 'httpclient'])
  assert.equal(received.db, db)
})

test('profile 已移除临时检索调用和评测入口', () => {
  const page = fs.readFileSync(path.join(__dirname, '../src/pages/profile/index.vue'), 'utf8')
  assert.ok(!/testRetrieval|evaluateRetrieval|RAG retrieval test|rag retrieval test/.test(page))
})
