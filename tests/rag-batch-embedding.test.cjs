const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const source = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag/index.obj.js'), 'utf8')
const fixtures = [
  { knowledgeId: 'dish-1-description', text: '招牌鸡腿饭由鸡腿搭配米饭和时蔬。' },
  { knowledgeId: 'dish-3-taste', text: '鲜蔬沙拉，项目描述为“清爽”。' },
  { knowledgeId: 'dish-8-ingredients', text: '酸梅汤记录的主要配料为：乌梅、山楂、冰糖。' }
]

// 仅本地测试模拟 HTTP；不读取真实环境变量、不访问模型或数据库。
function setup(options = {}) {
  const requests = []
  const logs = []
  const sandbox = {
    module: { exports: {} }, require,
    process: { env: {
      DASHSCOPE_API_KEY: 'test-only-secret',
      LLM_BASE_URL: 'https://example.invalid/compatible-mode/v1/',
      EMBEDDING_MODEL: 'qwen3.7-text-embedding-flash',
      EMBEDDING_DIMENSION: '512',
      ...options.env
    } },
    console: { log: (...args) => logs.push(args), error: (...args) => logs.push(args) },
    uniCloud: {
      database() { assert.fail('诊断不应访问数据库') },
      httpclient: { async request(url, config) {
        requests.push({ url, config })
        if (options.networkFails) throw new Error('Authorization: Bearer test-only-secret')
        if ('response' in options) return options.response
        const data = [0, 1, 2].map(index => ({ index, embedding: Array(512).fill(index + 0.125) }))
        if (options.mutate) options.mutate(data)
        return { status: 200, data: JSON.stringify({ data }) }
      } }
    }
  }
  vm.runInNewContext(source, sandbox)
  return { rag: sandbox.module.exports, requests, logs }
}

function assertSafe(result, logs) {
  const output = JSON.stringify({ result, logs })
  assert.ok(!output.includes('test-only-secret'))
  assert.ok(!output.includes('Authorization'))
  assert.deepEqual(logs, [])
}

test('一次 POST 发送三条冻结文本，严格映射知识 ID，仅返回前 3 个数字', async () => {
  const app = setup()
  const result = await app.rag.testBatchEmbedding()
  assert.equal(app.requests.length, 1)
  const { url, config } = app.requests[0]
  assert.equal(url, 'https://example.invalid/compatible-mode/v1/embeddings')
  assert.equal(config.method, 'POST')
  assert.equal(config.followRedirect, false)
  assert.deepEqual(JSON.parse(JSON.stringify(config.data)), {
    model: 'qwen3.7-text-embedding-flash', input: fixtures.map(item => item.text),
    dimensions: 512, encoding_format: 'float'
  })
  assert.deepEqual(JSON.parse(JSON.stringify(result)), {
    errCode: 0, model: 'qwen3.7-text-embedding-flash', dimension: 512, count: 3,
    items: fixtures.map((item, index) => ({
      knowledgeId: item.knowledgeId, index, dimension: 512,
      vectorPreview: Array(3).fill(index + 0.125)
    }))
  })
  assertSafe(result, app.logs)
})

for (const count of [0, 2, 4]) {
  test(`拒绝返回 ${count} 条记录`, async () => {
    const app = setup({ mutate: data => {
      while (data.length < count) data.push({ index: data.length, embedding: Array(512).fill(0) })
      data.length = count
    } })
    assert.equal((await app.rag.testBatchEmbedding()).errCode, 'EMBEDDING_COUNT_INVALID')
  })
}

const invalidItems = [
  ['index 缺失', item => { delete item.index }, 'EMBEDDING_INDEX_INVALID'],
  ['index 为字符串', item => { item.index = '1' }, 'EMBEDDING_INDEX_INVALID'],
  ['index 重复', item => { item.index = 0 }, 'EMBEDDING_INDEX_INVALID'],
  ['index 越界', item => { item.index = 3 }, 'EMBEDDING_INDEX_INVALID'],
  ['embedding 缺失', item => { delete item.embedding }, 'EMBEDDING_RESPONSE_INVALID'],
  ['embedding 非数组', item => { item.embedding = {} }, 'EMBEDDING_RESPONSE_INVALID'],
  ['511 维', item => { item.embedding.pop() }, 'EMBEDDING_LENGTH_INVALID'],
  ['513 维', item => { item.embedding.push(0) }, 'EMBEDDING_LENGTH_INVALID'],
  ['数字字符串', item => { item.embedding[511] = '0.1' }, 'EMBEDDING_NUMBERS_INVALID'],
  ['null 元素', item => { item.embedding[511] = null }, 'EMBEDDING_NUMBERS_INVALID']
]
for (const [name, mutate, code] of invalidItems) {
  test(`拒绝 ${name}，不返回部分成功结果`, async () => {
    const app = setup({ mutate: data => mutate(data[1]) })
    const result = await app.rag.testBatchEmbedding()
    assert.equal(result.errCode, code)
    assert.equal(result.items, undefined)
    assertSafe(result, app.logs)
  })
}

test('拒绝乱序，不自动排序掩盖输入对应关系', async () => {
  const result = await setup({ mutate: data => data.reverse() }).rag.testBatchEmbedding()
  assert.equal(result.errCode, 'EMBEDDING_INDEX_INVALID')
})

for (const value of ['1e400', '-1e400']) {
  test(`拒绝 JSON 解析后产生的非有限数字 ${value}`, async () => {
    const data = [0, 1, 2].map(index => ({ index, embedding: Array(512).fill(0) }))
    data[2].embedding[511] = 'NON_FINITE'
    const app = setup({ response: { status: 200, data: JSON.stringify({ data }).replace('"NON_FINITE"', value) } })
    assert.equal((await app.rag.testBatchEmbedding()).errCode, 'EMBEDDING_NUMBERS_INVALID')
  })
}

const invalidResponses = [
  ['HTTP 响应缺失', null, 'EMBEDDING_RESPONSE_INVALID'],
  ['HTTP 状态异常', { status: '200', data: '{}' }, 'EMBEDDING_RESPONSE_INVALID'],
  ['HTTP 401', { status: 401, data: 'Authorization: test-only-secret' }, 'EMBEDDING_HTTP_ERROR'],
  ['HTTP 429', { status: 429, data: 'test-only-secret' }, 'EMBEDDING_HTTP_ERROR'],
  ['HTTP 500', { status: 500, data: 'test-only-secret' }, 'EMBEDDING_HTTP_ERROR'],
  ['非法 JSON', { status: 200, data: 'test-only-secret' }, 'EMBEDDING_RESPONSE_INVALID'],
  ['API error', { status: 200, data: '{"error":"Authorization: test-only-secret"}' }, 'EMBEDDING_API_ERROR'],
  ['data 缺失', { status: 200, data: '{}' }, 'EMBEDDING_RESPONSE_INVALID'],
  ['data 非数组', { status: 200, data: '{"data":{}}' }, 'EMBEDDING_RESPONSE_INVALID'],
  ['null 记录', { status: 200, data: '{"data":[null,null,null]}' }, 'EMBEDDING_INDEX_INVALID']
]
for (const [name, response, code] of invalidResponses) {
  test(`安全处理 ${name}`, async () => {
    const app = setup({ response })
    const result = await app.rag.testBatchEmbedding()
    assert.equal(result.errCode, code)
    assert.equal(app.requests.length, 1)
    assertSafe(result, app.logs)
  })
}

test('网络异常不泄露敏感信息、不自动重试', async () => {
  const app = setup({ networkFails: true })
  const result = await app.rag.testBatchEmbedding()
  assert.equal(result.errCode, 'EMBEDDING_REQUEST_FAILED')
  assert.equal(app.requests.length, 1)
  assertSafe(result, app.logs)
})

for (const [name, value, code] of [
  ['DASHSCOPE_API_KEY', '', 'EMBEDDING_CONFIG_MISSING'],
  ['LLM_BASE_URL', '', 'EMBEDDING_CONFIG_MISSING'],
  ['EMBEDDING_MODEL', '', 'EMBEDDING_CONFIG_MISSING'],
  ['EMBEDDING_DIMENSION', '', 'EMBEDDING_DIMENSION_INVALID'],
  ['EMBEDDING_DIMENSION', '1024', 'EMBEDDING_DIMENSION_INVALID'],
  ['LLM_BASE_URL', 'http://example.invalid/v1', 'EMBEDDING_CONFIG_INVALID'],
  ['LLM_BASE_URL', 'https://user:test-only-secret@example.invalid/v1', 'EMBEDDING_CONFIG_INVALID']
]) {
  test(`配置校验 ${name}: ${code}`, async () => {
    const app = setup({ env: { [name]: value } })
    const result = await app.rag.testBatchEmbedding()
    assert.equal(result.errCode, code)
    assert.equal(app.requests.length, 0)
    assertSafe(result, app.logs)
  })
}

test('原单条 testEmbedding 保持字符串请求及 5 个数字预览', async () => {
  const app = setup({ mutate: data => { data.length = 1 } })
  const result = await app.rag.testEmbedding()
  assert.equal(result.errCode, 0)
  assert.equal(result.dimension, 512)
  assert.equal(result.hasValidNumbers, true)
  assert.equal(result.vectorPreview.length, 5)
  assert.equal(app.requests.length, 1)
  assert.equal(app.requests[0].config.data.input, fixtures[0].text)
  assertSafe(result, app.logs)
})
