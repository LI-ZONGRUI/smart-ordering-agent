const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { answer } = require('../uniCloud-aliyun/cloudfunctions/rag/generator')
const sources = require('../docs/rag/knowledge-source.json')
const dishes = require('../uniCloud-aliyun/database/dishes.init_data.json')
const vector = () => [1, ...Array(511).fill(0)]
const good = () => ({ answerable: true, dishIds: ['dish-4'], usedKnowledgeIds: ['dish-4-taste'] })
function setup(options = {}) {
  const requests = []
  const reads = []
  const records = (options.ids || ['dish-4-taste', 'dish-3-taste', 'dish-7-taste']).map(id => ({
    ...sources.find(s => s.knowledgeId === id), embedding: vector(), embeddingDimension: 512,
    embeddingModel: 'qwen3.7-text-embedding-flash'
  }))
  const db = { command: { in: ids => ids }, collection(name) {
    let condition
    return { where(c) { condition = c; return this }, orderBy() { return this }, skip() { return this },
      limit() { return this }, field() { return this }, async get() {
        reads.push(name)
        if (options.dbFails) throw new Error('sensitive upstream error')
        return { data: name === 'knowledge_chunks' ? records : dishes.filter(d => condition._id.includes(d._id)) }
      } }
  } }
  const env = { DASHSCOPE_API_KEY: 'secret-test', LLM_BASE_URL: 'https://example.invalid/v1',
    EMBEDDING_MODEL: 'qwen3.7-text-embedding-flash', EMBEDDING_DIMENSION: '512', RAG_LLM_MODEL: 'test-model', ...options.env }
  const httpclient = { async request(url, config) {
    requests.push({ url, config })
    await Promise.resolve()
    if (url.endsWith('/embeddings')) {
      if (options.embeddingFails) throw new Error('Authorization secret-test')
      if (options.embeddingResponse) return options.embeddingResponse
      return { status: 200, data: JSON.stringify({ data: [{ index: 0, embedding: vector() }] }) }
    }
    if (options.generationFails) throw new Error('Authorization secret-test')
    return options.response || { status: 200, data: JSON.stringify({ choices: [{ finish_reason: 'stop',
      message: { content: JSON.stringify(options.contract || good()) } }] }) }
  } }
  return { requests, reads, run: query => answer(query, { db, httpclient, env }) }
}

test('任意Query传入Embedding和Prompt；Top3固定且正式字段白名单', async () => {
  const app = setup()
  const result = await app.run('想喝柠檬味的')
  assert.equal(result.errCode, 0)
  assert.equal(result.query, '想喝柠檬味的')
  assert.equal(app.requests[0].config.data.input, result.query)
  assert.equal(app.requests[0].config.data.dimensions, 512)
  const prompt = app.requests[1].config.data.messages[1].content
  assert.ok(prompt.startsWith('[USER QUERY]\n"想喝柠檬味的"'))
  const knowledge = JSON.parse(prompt.split('[RETRIEVED KNOWLEDGE]\n')[1].split('\n\n[LIVE DISH FACTS]')[0])
  assert.equal(knowledge.length, 3)
  assert.deepEqual(Object.keys(result).sort(), ['errCode','query','answerable','answer','dishIds','usedKnowledgeIds','evidence'].sort())
  assert.deepEqual(Object.keys(result.evidence[0]).sort(), ['knowledgeId','dishId','scope','type','title','text'].sort())
  for (const field of ['embedding','similarity','headers','messages','choices','model','retrieval']) assert.ok(!JSON.stringify(result).includes(`"${field}":`))
  assert.ok(!JSON.stringify(result).includes('secret-test'))
})
test('trim Query', async () => assert.equal((await setup().run('  柠檬茶 \n')).query, '柠檬茶'))
for (const query of ['', ' \n ', null, undefined, 123, {}, [], { query: '牛肉' }, '中'.repeat(201)]) {
  test(`输入拒绝 ${JSON.stringify(query)?.slice(0, 30)}`, async () => {
    const app = setup()
    assert.equal((await app.run(query)).errCode, 'RAG_QUERY_INVALID')
    assert.equal(app.requests.length, 0); assert.equal(app.reads.length, 0)
  })
}
for (const query of ['中'.repeat(200), '🍋'.repeat(200)]) {
  test('200个Unicode字符允许', async () => assert.equal((await setup().run(query)).errCode, 0))
}
test('餐厅证据允许空dishIds', async () => {
  const id = 'restaurant-spicy-level-definitions'
  const app = setup({ ids: [id], contract: { answerable: true, dishIds: [], usedKnowledgeIds: [id] } })
  const result = await app.run('辣度如何定义？')
  assert.equal(result.errCode, 0)
  assert.equal(result.evidence[0].scope, 'restaurant')
  assert.equal(result.evidence[0].dishId, null)
  assert.ok(!app.reads.includes('dishes'))
})
test('拒答固定文案和空证据', async () => {
  const result = await setup({ contract: { answerable: false, dishIds: [], usedKnowledgeIds: [] } }).run('能开发票吗？')
  assert.equal(result.errCode, 0); assert.equal(result.answerable, false)
  assert.equal(result.answer, '当前提供的知识不足以回答这个问题。')
  assert.deepEqual(result.evidence, [])
})
const invalid = [
  { ...good(), usedKnowledgeIds: [] },
  { ...good(), usedKnowledgeIds: ['dish-2-taste'] },
  { ...good(), dishIds: ['unknown'] },
  { ...good(), dishIds: ['dish-3'] },
  { ...good(), dishIds: [] },
  { ...good(), answerable: false },
  { answerable: false, dishIds: ['dish-4'], usedKnowledgeIds: [] },
  { answerable: false, dishIds: [], usedKnowledgeIds: ['dish-4-taste'] },
  ...['answer','claims','text','evidence','price','reason','explanation','embedding'].map(key => ({ ...good(), [key]: '不可信内容' }))
]
invalid.forEach((contract, i) => test(`非法合同/引用拒绝 ${i}`, async () => {
  const result = await setup({ contract }).run('柠檬茶')
  assert.notEqual(result.errCode, 0)
  assert.ok(!Object.hasOwn(result, 'answer'))
}))
test('去重保序；答案逐字来自真实证据', async () => {
  const result = await setup({ contract: { answerable: true,
    dishIds: ['dish-4','dish-3','dish-4'], usedKnowledgeIds: ['dish-4-taste','dish-3-taste','dish-4-taste'] } }).run('清爽的饮料')
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.dishIds, ['dish-4','dish-3'])
  assert.deepEqual(result.usedKnowledgeIds, ['dish-4-taste','dish-3-taste'])
  assert.equal(result.answer, result.usedKnowledgeIds.map(id => sources.find(s => s.knowledgeId === id).text).join('\n'))
  assert.ok(!result.answer.includes('清爽的柠檬香气'))
})
for (const [options, code] of [
  [{ embeddingFails: true }, 'RETRIEVAL_QUERY_REQUEST_FAILED'],
  [{ embeddingResponse: { status: 403 } }, 'RETRIEVAL_QUERY_HTTP_ERROR'],
  [{ embeddingResponse: { status: 200, data: '{}' } }, 'RETRIEVAL_QUERY_RESPONSE_INVALID'],
  [{ dbFails: true }, 'RETRIEVAL_DATABASE_FAILED'],
  [{ generationFails: true }, 'RAG_GENERATION_REQUEST_FAILED'],
  [{ response: { status: 500 } }, 'RAG_GENERATION_HTTP_ERROR'],
  [{ response: { status: 200, data: '{}' } }, 'RAG_GENERATION_RESPONSE_INVALID'],
  [{ env: { RAG_LLM_MODEL: '' } }, 'RAG_GENERATION_CONFIG_MISSING']
]) test(`安全错误 ${code}`, async () => {
  const result = await setup(options).run('牛肉')
  assert.equal(result.errCode, code)
  assert.deepEqual(Object.keys(result).sort(), ['errCode','errMsg'])
  assert.ok(!JSON.stringify(result).includes('secret-test'))
  assert.ok(!JSON.stringify(result).includes('Authorization'))
})
test('并发请求Query与证据互不污染', async () => {
  const a = setup()
  const b = setup({ contract: { answerable: false, dishIds: [], usedKnowledgeIds: [] } })
  const [ra, rb] = await Promise.all([a.run('柠檬茶'), b.run('开发票')])
  assert.equal(ra.query, '柠檬茶'); assert.equal(rb.query, '开发票')
  assert.equal(ra.answerable, true); assert.equal(rb.answerable, false)
  assert.equal(a.requests[0].config.data.input, '柠檬茶')
  assert.equal(b.requests[0].config.data.input, '开发票')
})
test('管理入口只允许server；只转发event.query', async () => {
  const calls = []
  const sandbox = { exports: {}, uniCloud: { importObject(name) {
    assert.equal(name, 'rag'); return { answer: async (...args) => { calls.push(args); return { errCode: 0 } } }
  } } }
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/rag-answer-admin/index.js','utf8'), sandbox)
  for (const SOURCE of ['client','http',undefined]) assert.equal((await sandbox.exports.main({ query: 'a' }, { SOURCE })).errCode, 'RAG_ANSWER_FORBIDDEN')
  assert.equal(calls.length, 0)
  await sandbox.exports.main({ query: '牛肉', model: 'override', topK: 99 }, { SOURCE: 'server' })
  assert.deepEqual(calls, [['牛肉']])
})
test('云对象answer只将Query和服务器依赖交给共享实现', async () => {
  let received
  const sandbox = { module: { exports: {} }, require: name => name === './generator' ? {
    answer: async (...args) => { received = args; return { errCode: 0 } }
  } : require(name), uniCloud: { database: () => 'db', httpclient: 'http' } }
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/rag/index.obj.js','utf8'), sandbox)
  await sandbox.module.exports.answer('牛肉', { model: 'override' })
  assert.equal(received[0], '牛肉')
  assert.equal(received[1].db, 'db'); assert.equal(received[1].httpclient, 'http')
  assert.equal(received.length, 2)
})
