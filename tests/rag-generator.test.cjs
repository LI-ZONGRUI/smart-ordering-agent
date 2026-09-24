const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const vm = require('node:vm')
const { testRagGeneration, buildMessages } = require('../uniCloud-aliyun/cloudfunctions/rag/generator')
const sources = require('../docs/rag/knowledge-source.json')
const dishesSource = require('../uniCloud-aliyun/database/dishes.init_data.json')
const frozen = require('./fixtures/rag-generation-frozen-files.json')
const root = path.join(__dirname, '..')
const vector = (x, y = 0) => [x, y, ...Array(510).fill(0)]
const selected = ['dish-3-taste', 'dish-7-taste', 'dish-4-taste']
const validAnswer = () => ({ answerable: true, dishIds: ['dish-3'], usedKnowledgeIds: ['dish-3-taste'] })
const sourceEvidence = id => {
  const { knowledgeId, dishId, title, text } = sources.find(item => item.knowledgeId === id)
  return { knowledgeId, dishId, title, text }
}
const rawReply = content => ({ status: 200, data: JSON.stringify({ choices: [
  { finish_reason: 'stop', message: { content } }
] }) })

function setup(options = {}) {
  const ids = options.selected || selected
  const requests = []
  const dishQueries = []
  let knowledgeReads = 0
  let dishReads = 0
  const dishes = structuredClone(dishesSource)
  if (options.dishes) options.dishes(dishes)
  const records = sources.map(source => ({ ...source, embeddingModel: 'qwen3.7-text-embedding-flash',
    embeddingDimension: 512, embedding: ids.includes(source.knowledgeId)
      ? [vector(1), vector(0.8, 0.6), vector(0.6, 0.8)][ids.indexOf(source.knowledgeId)] : vector(-1) }))
  if (options.records) options.records(records)
  const db = { command: { in: values => ({ testIn: values }) }, collection(name) {
    let requestedIds
    return {
      where(condition) {
        if (name === 'knowledge_chunks') assert.deepEqual(condition, { verified: true })
        else {
          assert.equal(name, 'dishes')
          assert.deepEqual(Object.keys(condition), ['_id'])
          requestedIds = condition._id.testIn
          dishQueries.push(requestedIds)
        }
        return this
      },
      field(fields) {
        if (name === 'dishes') assert.deepEqual(Object.keys(fields).sort(), ['_id', 'name', 'price', 'status', 'description', 'spicyLevel', 'ingredients'].sort())
        return this
      },
      orderBy() { return this }, skip() { return this }, limit() { return this },
      async get() {
        if (name === 'knowledge_chunks') { knowledgeReads++; return { data: records } }
        dishReads++
        if (options.dishFails || (options.recheckFails && dishReads === 2)) throw new Error('Authorization secret-test-generation')
        return { data: structuredClone(dishes.filter(dish => requestedIds.includes(dish._id))) }
      },
      add() { assert.fail('不得写库') }, update() { assert.fail('不得更新') }, remove() { assert.fail('不得删除') }
    }
  } }
  const env = { DASHSCOPE_API_KEY: 'secret-test-generation', LLM_BASE_URL: 'https://example.invalid/v1/',
    EMBEDDING_MODEL: 'qwen3.7-text-embedding-flash', EMBEDDING_DIMENSION: '512',
    RAG_LLM_MODEL: 'test-generation-model', ...options.env }
  const httpclient = { async request(url, config) {
    requests.push({ url, config })
    if (url.endsWith('/embeddings')) {
      assert.equal(config.data.input, '有什么比较清爽的？')
      assert.equal(config.data.model, env.EMBEDDING_MODEL)
      if (options.retrievalFails) throw new Error('Authorization secret-test-generation')
      return { status: 200, data: JSON.stringify({ data: [{ index: 0, embedding: vector(1) }] }) }
    }
    assert.equal(url, 'https://example.invalid/v1/chat/completions')
    if (options.networkFails) throw new Error('Authorization secret-test-generation')
    if (options.afterGeneration) options.afterGeneration(dishes)
    return options.response || rawReply(options.content ?? JSON.stringify(options.answer ?? validAnswer()))
  } }
  return { requests, dishQueries, knowledgeReads: () => knowledgeReads, dishReads: () => dishReads,
    async run() {
      const result = await testRagGeneration({ db, httpclient, env, query: '客户端自定义问题应被忽略' })
      const serialized = JSON.stringify(result)
      assert.ok(!serialized.includes('secret-test-generation'))
      assert.ok(!serialized.includes('Authorization'))
      assert.ok(!serialized.includes('"embedding":'))
      assert.ok(!serialized.includes('"headers":'))
      return result
    }
  }
}

test('冻结文件未变：Retriever、Indexer、Knowledge Source、历史 Evaluation 与 ai 推荐', () => {
  for (const [file, expected] of Object.entries(frozen)) {
    assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex'), expected, file)
  }
})
test('真实检索函数→Top3→限定ID查实时菜品→JSON生成→校验→重新读库', async () => {
  const app = setup({ dishes: rows => { rows.find(row => row._id === 'dish-3').price = 33.25 } })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.query, '有什么比较清爽的？')
  assert.equal(result.retrieval.topK, 3)
  assert.equal(result.retrieval.totalCandidates, 21)
  assert.deepEqual(result.retrieval.knowledgeIds, selected)
  assert.deepEqual(result.retrieval.dishIds, ['dish-3', 'dish-7', 'dish-4'])
  assert.equal(result.generation.model, 'test-generation-model')
  assert.equal(result.generation.answerable, true)
  assert.equal(app.knowledgeReads(), 1)
  assert.equal(app.dishReads(), 2)
  assert.deepEqual(app.dishQueries, [['dish-3', 'dish-7', 'dish-4'], ['dish-3', 'dish-7', 'dish-4']])
  assert.equal(app.requests.length, 2)
  const config = app.requests[1].config
  assert.equal(config.method, 'POST')
  assert.equal(config.data.model, 'test-generation-model')
  assert.deepEqual(config.data.response_format, { type: 'json_object' })
  assert.equal(config.data.enable_thinking, false)
  const messages = config.data.messages
  const prompt = messages.map(x => x.content).join('\n')
  for (const section of ['SYSTEM RULES', 'USER QUERY', 'RETRIEVED KNOWLEDGE', 'LIVE DISH FACTS', 'OUTPUT CONTRACT']) assert.ok(prompt.includes(`[${section}]`))
  const [rawKnowledge, rawLive] = messages[1].content.split('[RETRIEVED KNOWLEDGE]\n')[1].split('\n\n[LIVE DISH FACTS]\n')
  const knowledge = JSON.parse(rawKnowledge)
  const live = JSON.parse(rawLive)
  assert.deepEqual(knowledge.map(x => x.knowledgeId), selected)
  assert.ok(knowledge.every(row => !Object.hasOwn(row, 'similarity') && !Object.hasOwn(row, 'embedding')))
  assert.ok(prompt.includes('鲜蔬沙拉，项目描述为“清爽”。'))
  assert.equal(live.dishes[0].price, 33.25)
  assert.equal(live.dishes[0].priceText, '33.25元')
  assert.equal(live.dishes[1].spicyLevel, 1)
  assert.deepEqual(live.dishes[1].ingredients, ['黄瓜', '蒜', '香醋', '辣椒'])
  assert.ok(live.dishes.every(row => row.status === 'on_sale' && !Object.hasOwn(row, 'image')))
  assert.ok(!prompt.includes('secret-test-generation') && !prompt.includes('embedding'))
})
test('选择dish-4-taste：服务器逐字使用真实柠檬香气证据，不产生清爽的修饰', async () => {
  const app = setup({ answer: { answerable: true, dishIds: ['dish-4'], usedKnowledgeIds: ['dish-4-taste'] } })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.generation.answer, '柠檬茶，项目描述为具有柠檬香气。')
  assert.deepEqual(result.generation.evidence, [sourceEvidence('dish-4-taste')])
  assert.ok(!result.generation.answer.includes('清爽的柠檬香气'))
  assert.ok(!Object.hasOwn(result.generation, 'claims'))
  assert.ok(!Object.hasOwn(result.generation, 'modelAnswerPreview'))
  assert.equal(app.requests.length, 2)
})
test('三条证据原文原序换行拼接，每个字段只来自真实检索快照', async () => {
  const result = await setup({ answer: { answerable: true,
    dishIds: ['dish-3', 'dish-7', 'dish-4'], usedKnowledgeIds: selected } }).run()
  assert.equal(result.errCode, 0)
  const evidence = selected.map(sourceEvidence)
  assert.deepEqual(result.generation.evidence, evidence)
  assert.equal(result.generation.answer, evidence.map(item => item.text).join('\n'))
  for (const row of result.generation.evidence) {
    assert.deepEqual(Object.keys(row).sort(), ['knowledgeId', 'dishId', 'title', 'text'].sort())
  }
})
test('选择ID顺序稳定，不改回Retrieval排名顺序', async () => {
  const ids = [...selected].reverse()
  const result = await setup({ answer: { answerable: true, dishIds: ['dish-4', 'dish-7', 'dish-3'], usedKnowledgeIds: ids } }).run()
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.retrieval.knowledgeIds, selected)
  assert.deepEqual(result.generation.usedKnowledgeIds, ids)
  assert.deepEqual(result.generation.evidence.map(item => item.knowledgeId), ids)
  assert.equal(result.generation.answer, ids.map(id => sourceEvidence(id).text).join('\n'))
})
test('重复知识ID/菜品ID按首次出现去重，不重复渲染证据', async () => {
  const result = await setup({ answer: { answerable: true,
    dishIds: ['dish-4', 'dish-3', 'dish-4'], usedKnowledgeIds: ['dish-4-taste', 'dish-3-taste', 'dish-4-taste'] } }).run()
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.generation.dishIds, ['dish-4', 'dish-3'])
  assert.deepEqual(result.generation.usedKnowledgeIds, ['dish-4-taste', 'dish-3-taste'])
  assert.equal(result.generation.evidence.length, 2)
  assert.equal(result.generation.answer, [sourceEvidence('dish-4-taste').text, sourceEvidence('dish-3-taste').text].join('\n'))
})
test('检索结果改变仍使用新Top3，没有硬编码历史ID', async () => {
  const ids = ['dish-1-description', 'dish-2-taste', 'dish-5-ingredients']
  const app = setup({ selected: ids, answer: { answerable: true, dishIds: ['dish-2'], usedKnowledgeIds: ['dish-2-taste'] } })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.retrieval.knowledgeIds, ids)
  assert.equal(result.generation.answer, sourceEvidence('dish-2-taste').text)
  assert.deepEqual(app.dishQueries[0], ['dish-1', 'dish-2', 'dish-5'])
})
test('关联dishId查询去重但不对Top3知识按dish去重', async () => {
  const app = setup({ selected: ['dish-3-taste', 'dish-3-ingredients', 'dish-4-taste'],
    answer: { answerable: true, dishIds: ['dish-3'], usedKnowledgeIds: ['dish-3-ingredients', 'dish-3-taste'] } })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.retrieval.results.length, 3)
  assert.equal(result.generation.evidence.length, 2)
  assert.deepEqual(app.dishQueries[0], ['dish-3', 'dish-4'])
})
test('restaurant级证据可以不关联菜品，返回真实原文', async () => {
  const app = setup({ selected: ['restaurant-spicy-level-definitions', 'dish-3-taste', 'dish-4-taste'],
    answer: { answerable: true, dishIds: [], usedKnowledgeIds: ['restaurant-spicy-level-definitions'] } })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.generation.evidence[0].dishId, null)
  assert.equal(result.generation.answer, sourceEvidence('restaurant-spicy-level-definitions').text)
  // 只证明原文渲染正确，不把合法ID当成适合“清爽”问题的语义保证。
})
test('原文中的空白和标点不改写、标题不进入事实答案', async () => {
  const text = '  原文测试：“保持标点！”\n保持原文换行。  '
  const result = await setup({ records: rows => { rows.find(row => row.knowledgeId === 'dish-3-taste').text = text } }).run()
  assert.equal(result.errCode, 0)
  assert.equal(result.generation.answer, text)
  assert.equal(result.generation.evidence[0].text, text)
})
test('拒答只返回固定文案和空数组，不需要模型answer', async () => {
  const app = setup({ answer: { answerable: false, dishIds: [], usedKnowledgeIds: [] } })
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.generation, { model: 'test-generation-model', answerable: false,
    answer: '当前提供的知识不足以回答这个问题。', dishIds: [], usedKnowledgeIds: [], evidence: [] })
  assert.equal(app.dishReads(), 1)
})
for (const [field, extra] of [
  ['answer', '柠檬茶具有清爽的柠檬香气。'],
  ['claims', [{ text: '柠檬茶具有清爽的柠檬香气。', supportedByKnowledgeIds: ['dish-4-taste'], supportedByDishIds: ['dish-4'] }]],
  ['text', '柠檬茶解腻。'],
  ['evidence', [{ knowledgeId: 'dish-4-taste', text: '柠檬茶助消化。' }]],
  ['price', 1], ['embedding', vector(1)], ['modelAnswerPreview', '不得透传']
]) test(`模型额外${field}直接拒绝，不作为事实来源`, async () => {
  const result = await setup({ answer: { ...validAnswer(), [field]: extra } }).run()
  assert.equal(result.errCode, 'RAG_GENERATION_RESPONSE_INVALID')
  assert.equal(result.generation, undefined)
  assert.ok(!JSON.stringify(result).includes('清爽的柠檬香气'))
})
for (const [name, patch, code] of [
  ['answerable类型错误', { answerable: 'true' }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['dishIds非数组', { dishIds: 'dish-3' }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['缺少dishIds', { dishIds: undefined }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['usedKnowledgeIds非数组', { usedKnowledgeIds: null }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['ID非字符串', { dishIds: [3] }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['知识ID空字符串', { usedKnowledgeIds: [''] }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['虚构菜品', { dishIds: ['invented'] }, 'RAG_GENERATION_IDS_INVALID'],
  ['真实但非本次菜品', { dishIds: ['dish-1'] }, 'RAG_GENERATION_IDS_INVALID'],
  ['虚构知识', { usedKnowledgeIds: ['invented'] }, 'RAG_GENERATION_IDS_INVALID'],
  ['真实但非本次知识', { usedKnowledgeIds: ['dish-1-description'] }, 'RAG_GENERATION_IDS_INVALID'],
  ['去重不能移除未知ID', { usedKnowledgeIds: ['dish-3-taste', 'dish-3-taste', 'invented'] }, 'RAG_GENERATION_IDS_INVALID'],
  ['引用与菜品不关联', { usedKnowledgeIds: ['dish-4-taste'] }, 'RAG_GENERATION_IDS_INVALID'],
  ['true缺少证据', { usedKnowledgeIds: [] }, 'RAG_GENERATION_IDS_INVALID'],
  ['选菜品知识却省略dishIds', { dishIds: [] }, 'RAG_GENERATION_IDS_INVALID'],
  ['false仍有知识', { answerable: false, dishIds: [] }, 'RAG_GENERATION_IDS_INVALID'],
  ['false仍有菜品', { answerable: false, usedKnowledgeIds: [] }, 'RAG_GENERATION_IDS_INVALID']
]) test(`选择合同拒绝：${name}`, async () => {
  assert.equal((await setup({ answer: { ...validAnswer(), ...patch } }).run()).errCode, code)
})
for (const content of ['not json', 'null', '[]', '```json\n{}\n```']) test(`非法输出 ${content}`, async () => {
  assert.equal((await setup({ content }).run()).errCode, 'RAG_GENERATION_RESPONSE_INVALID')
})
test('Prompt明确仅选ID不写事实，剔除embedding和similarity数值', () => {
  const messages = buildMessages('有什么比较清爽的？', [{ ...sources[0], embedding: vector(1), similarity: 0.9 }], [], [])
  assert.ok(messages[0].content.includes('不负责最终事实措辞，不生成或改写知识文本'))
  assert.ok(messages[0].content.includes('禁止输出 answer、claims、text、evidence、price'))
  assert.ok(!messages.map(item => item.content).join('\n').includes('embedding'))
  assert.ok(!messages[1].content.includes('similarity'))
})
test('已售罄菜品进入实时事实但不能作为推荐', async () => {
  const app = setup({ dishes: rows => { rows.find(row => row._id === 'dish-3').status = 'sold_out' } })
  assert.equal((await app.run()).errCode, 'RAG_GENERATION_IDS_INVALID')
  assert.ok(app.requests[1].config.data.messages[1].content.includes('sold_out'))
})
test('菜品不存在时明确标记缺失，拒绝模型继续推荐', async () => {
  const app = setup({ dishes: rows => rows.splice(rows.findIndex(row => row._id === 'dish-3'), 1) })
  assert.equal((await app.run()).errCode, 'RAG_GENERATION_IDS_INVALID')
  assert.ok(app.requests[1].config.data.messages[1].content.includes('"missingDishIds":["dish-3"]'))
})
test('所有关联菜品已删除，合法拒答安全返回且不伪造菜品', async () => {
  const result = await setup({ dishes: rows => rows.splice(0), answer: { answerable: false,
    dishIds: [], usedKnowledgeIds: [] } }).run()
  assert.equal(result.errCode, 0)
  assert.equal(result.generation.answerable, false)
})
for (const [name, change] of [
  ['生成期间售罄', rows => { rows.find(row => row._id === 'dish-3').status = 'sold_out' }],
  ['生成期间价格变化', rows => { rows.find(row => row._id === 'dish-3').price = 99 }],
  ['生成期间配料变化', rows => { rows.find(row => row._id === 'dish-3').ingredients.push('测试配料') }],
  ['生成期间菜品删除', rows => { rows.splice(rows.findIndex(row => row._id === 'dish-3'), 1) }]
]) test(name + '：拒绝旧回答', async () => {
  const result = await setup({ afterGeneration: change }).run()
  assert.equal(result.errCode, 'RAG_LIVE_FACTS_CHANGED')
  assert.equal(result.generation, undefined)
})
test('实时菜品字段异常不消耗Generation请求', async () => {
  const app = setup({ dishes: rows => { rows.find(row => row._id === 'dish-3').price = '22' } })
  assert.equal((await app.run()).errCode, 'RAG_LIVE_DISH_FAILED')
  assert.equal(app.requests.length, 1)
})
for (const options of [{ dishFails: true }, { recheckFails: true }]) test('数据库异常安全返回', async () => {
  assert.equal((await setup(options).run()).errCode, 'RAG_LIVE_DISH_FAILED')
})
test('检索失败不继续查dishes或Generation', async () => {
  const app = setup({ retrievalFails: true })
  assert.equal((await app.run()).errCode, 'RAG_RETRIEVAL_FAILED')
  assert.equal(app.requests.length, 1)
  assert.equal(app.dishReads(), 0)
})
for (const [name, options, code] of [
  ['网络异常', { networkFails: true }, 'RAG_GENERATION_REQUEST_FAILED'],
  ['HTTP 401', { response: { status: 401, data: 'Authorization secret-test-generation' } }, 'RAG_GENERATION_HTTP_ERROR'],
  ['非JSON响应', { response: { status: 200, data: 'Authorization secret-test-generation' } }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['缺少choices', { response: { status: 200, data: '{}' } }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['API错误', { response: { status: 200, data: '{"error":"secret-test-generation"}' } }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['截断响应', { response: { status: 200, data: JSON.stringify({ choices: [{ finish_reason: 'length', message: { content: JSON.stringify(validAnswer()) } }] }) } }, 'RAG_GENERATION_RESPONSE_INVALID'],
  ['异常正文回显密钥', { answer: { ...validAnswer(), answer: 'secret-test-generation' } }, 'RAG_GENERATION_RESPONSE_INVALID']
]) test(`Generation ${name}，不泄露原始响应/密钥`, async () => {
  assert.equal((await setup(options).run()).errCode, code)
})
for (const env of [{ RAG_LLM_MODEL: '' }, { RAG_LLM_MODEL: '', LLM_MODEL: 'cannot-fallback' },
  { DASHSCOPE_API_KEY: '' }, { LLM_BASE_URL: '' }, { LLM_BASE_URL: 'http://example.invalid' },
  { LLM_BASE_URL: 'https://user:secret@example.invalid' }]) test('配置缺失或不安全地址：调用前拒绝', async () => {
  const app = setup({ env })
  assert.notEqual((await app.run()).errCode, 0)
  assert.equal(app.requests.length, 0)
})
test('管理云函数仅接受server来源；不转发event；异常不泄露', async () => {
  let calls = 0
  let fails = false
  const sandbox = { exports: {}, uniCloud: { importObject: name => {
    assert.equal(name, 'rag')
    return { testRagGeneration: async (...args) => {
      assert.equal(args.length, 0)
      if (fails) throw new Error('Authorization secret-test-generation')
      calls++; return { errCode: 0 }
    } }
  } } }
  vm.runInNewContext(fs.readFileSync(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag-generation-admin/index.js'), 'utf8'), sandbox)
  for (const SOURCE of ['client', 'http', undefined]) {
    assert.equal((await sandbox.exports.main({ SOURCE: 'server' }, { SOURCE })).errCode, 'RAG_GENERATION_FORBIDDEN')
  }
  assert.equal(calls, 0)
  assert.equal((await sandbox.exports.main({ query: 'ignored' }, { SOURCE: 'server' })).errCode, 0)
  assert.equal(calls, 1)
  fails = true
  const result = await sandbox.exports.main({}, { SOURCE: 'server' })
  assert.equal(result.errCode, 'RAG_GENERATION_CALL_FAILED')
  assert.ok(!JSON.stringify(result).includes('secret-test-generation'))
})
test('rag 管理方法拒绝客户端，不接受任意query；前端无测试入口', async () => {
  let calls = 0
  const sandbox = { module: { exports: {} }, uniCloud: { database: () => ({}), httpclient: {} },
    require: name => name === './generator' ? { testRagGeneration: async args => {
      assert.deepEqual(Object.keys(args).sort(), ['db', 'httpclient']); calls++; return { errCode: 0 }
    } } : require(name) }
  vm.runInNewContext(fs.readFileSync(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag/index.obj.js'), 'utf8'), sandbox)
  const method = sandbox.module.exports.testRagGeneration
  for (const source of ['client', 'http', undefined]) assert.equal((await method.call({ getClientInfo: () => ({ source }) })).errCode, 'RAG_GENERATION_FORBIDDEN')
  assert.equal(calls, 0)
  await method.call({ getClientInfo: () => ({ source: 'function' }) }, { query: 'ignored' })
  assert.equal(calls, 1)
  const visit = folder => {
    for (const entry of fs.readdirSync(folder, { withFileTypes: true })) {
      const file = path.join(folder, entry.name)
      if (entry.isDirectory()) visit(file)
      else if (/\.(js|vue)$/.test(file)) assert.doesNotMatch(fs.readFileSync(file, 'utf8'), /testRagGeneration|rag-generation-admin/)
    }
  }
  visit(path.join(root, 'src'))
})
