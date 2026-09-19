const { test } = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')
const fs = require('node:fs')
const path = require('node:path')
const source = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/ai/recommend.js'), 'utf8')
// 仅测试使用初始化数据和模拟接口；生产 recommend 始终查询真实云数据库。
const seed = require('../uniCloud-aliyun/database/dishes.init_data.json')

function setup(answer = { dishIds: ['dish-5', 'dish-4'], reason: '香辣鸡丁配柠檬茶。' }, options = {}) {
  let queryCount = 0
  let request
  const db = {
    command: { in: ids => ids },
    collection() {
      let where = {}, offset = 0, limit = 100
      return {
        where(value) { where = value; return this },
        orderBy() { return this },
        skip(value) { offset = value; return this },
        limit(value) { limit = value; return this },
        async get() {
          queryCount++
          if (options.dbFails) throw new Error('database failure')
          let data = structuredClone(where._id ? (options.fresh || seed) : seed)
          data = data.filter(d => (!where.status || d.status === where.status) && (!where._id || where._id.includes(d._id)))
          return { data: data.slice(offset, offset + limit) }
        }
      }
    }
  }
  const sandbox = {
    module: { exports: {} }, require,
    process: { env: { DASHSCOPE_API_KEY: 'test-only-secret', LLM_BASE_URL: 'https://example.invalid/v1', LLM_MODEL: 'test-model', ...options.env } },
    uniCloud: {
      database: () => db,
      httpclient: { async request(url, config) {
        request = { url, config }
        if (options.networkFails) throw new Error('Authorization: test-only-secret')
        return options.response || { status: 200, data: JSON.stringify({ choices: [{ message: { content: typeof answer === 'string' ? answer : JSON.stringify(answer) }, finish_reason: 'stop' }] }) }
      } }
    }
  }
  vm.runInNewContext(source, sandbox)
  return { recommend: sandbox.module.exports, request: () => request, queryCount: () => queryCount }
}

test('辣味、50元以内、排除牛肉：白名单菜单、真实价格、饮料', async () => {
  const app = setup({ dishIds: ['dish-5', 'dish-4'], reason: '香辣搭配饮料', price: 1, totalPrice: 1 })
  const result = await app.recommend('想吃辣的，50元以内，不要牛肉，最好有饮料')
  assert.equal(result.errCode, 0)
  assert.equal(result.totalPrice, 48)
  assert.equal(result.recommendations[0].name, '香辣鸡丁')
  assert.equal(result.recommendations[0].price, 36)
  const menu = JSON.parse(app.request().config.data.messages[1].content).menu
  assert.ok(menu.every(d => !['dish-2', 'dish-6', 'dish-8'].includes(d._id)))
  assert.ok(menu.every(d => !('image' in d) && !('sales' in d)))
  assert.equal(app.request().config.data.response_format.type, 'json_object')
  assert.equal(app.queryCount(), 2)
})

test('清淡推荐从数据库返回', async () => {
  const result = await setup({ dishIds: ['dish-3'], reason: '清爽蔬菜' }).recommend('随便推荐点清淡的')
  assert.equal(result.recommendations[0].name, '鲜蔬沙拉')
  assert.equal(result.totalPrice, 22)
})

test('预算1元无法满足，不发送无意义的模型请求', async () => {
  const app = setup()
  const result = await app.recommend('预算只有1元')
  assert.equal(result.recommendations.length, 0)
  assert.equal(result.totalPrice, 0)
  assert.equal(app.request(), undefined)
})

for (const id of ['invented-kung-pao', 'dish-8', 'dish-6']) {
  test(`拒绝不存在/售罄/被排除的 ID: ${id}`, async () => {
    const result = await setup({ dishIds: [id], reason: '不可信理由' }).recommend('给我推荐宫保鸡丁，不要牛肉')
    assert.equal(result.recommendations.length, 0)
    assert.equal(result.totalPrice, 0)
  })
}

test('模型明确无法满足时保留说明', async () => {
  const result = await setup({ dishIds: [], reason: '当前菜单没有宫保鸡丁。' }).recommend('给我推荐宫保鸡丁')
  assert.equal(result.recommendations.length, 0)
  assert.equal(result.reason, '当前菜单没有宫保鸡丁。')
})

test('去重且最多三道菜，每道一份', async () => {
  const result = await setup({ dishIds: ['dish-1', 'dish-1', 'dish-3', 'dish-4', 'dish-5'], reason: '组合' }).recommend('随便推荐')
  assert.equal(result.recommendations.length, 3)
  assert.equal(result.totalPrice, 62)
})

test('等待模型期间售罄则拒绝', async () => {
  const fresh = structuredClone(seed)
  fresh.find(d => d._id === 'dish-5').status = 'sold_out'
  const result = await setup(undefined, { fresh }).recommend('推荐辣菜')
  assert.equal(result.recommendations.length, 0)
})

test('二次查询的新价格用于金额计算', async () => {
  const fresh = structuredClone(seed)
  fresh.find(d => d._id === 'dish-5').price = 36.15
  fresh.find(d => d._id === 'dish-4').price = 12.1
  const result = await setup(undefined, { fresh }).recommend('预算50元，想吃辣')
  assert.equal(result.totalPrice, 48.25)
})

test('模型推荐总额超预算时不放行', async () => {
  const result = await setup({ dishIds: ['dish-1', 'dish-5'], reason: '组合' }).recommend('50元以内')
  assert.equal(result.recommendations.length, 0)
})

for (const value of [null, 1, '', '  ', '菜'.repeat(201)]) {
  test(`输入校验 ${String(value).slice(0, 12)}`, async () => {
    const app = setup()
    assert.equal((await app.recommend(value)).errCode, 'AI_INPUT_INVALID')
    assert.equal(app.queryCount(), 0)
  })
}
for (const answer of ['not json', '{}', '{"dishIds":[1],"reason":"x"}', '{"dishIds":[],"reason":null}']) {
  test(`格式校验 ${answer}`, async () => {
    assert.equal((await setup(answer).recommend('推荐菜品')).errCode, 'AI_RESPONSE_INVALID')
  })
}
for (const options of [
  { networkFails: true }, { response: { status: 401, data: 'test-only-secret' } },
  { dbFails: true }, { env: { DASHSCOPE_API_KEY: '' } },
  { response: { status: 200, data: 'invalid JSON test-only-secret' } }
]) {
  test(`安全失败 ${Object.keys(options)[0]}`, async () => {
    const result = await setup(undefined, options).recommend('推荐菜品')
    assert.notEqual(result.errCode, 0)
    assert.ok(!JSON.stringify(result).includes('test-only-secret'))
    assert.ok(!JSON.stringify(result).includes('Authorization'))
  })
}

const serviceSource = fs.readFileSync(path.join(__dirname, '../src/services/ai.js'), 'utf8')
  .replace('export async function recommendDishes', 'async function recommendDishes')
async function callService(response, throws = false) {
  const context = {
    uniCloud: { importObject(name, options) {
      assert.equal(name, 'ai')
      assert.equal(options.customUI, true)
      return { async recommend() {
        if (throws) throw response
        return response
      } }
    } }
  }
  vm.runInNewContext(serviceSource, context)
  return context.recommendDishes('推荐清淡菜品')
}

test('前端 service 正常返回推荐和空结果', async () => {
  const result = { errCode: 0, recommendations: [], totalPrice: 0, reason: '暂无合适菜品' }
  assert.equal(await callService(result), result)
})

test('前端屏蔽原始异常，提供友好错误', async () => {
  await assert.rejects(callService({ errCode: 'HTTP_ERROR', errMsg: 'Authorization: test-only-secret' }, true),
    error => error.message === '智能推荐暂时不可用，请稍后重新尝试')
})

test('前端拒绝异常卡片数据，避免 toFixed/join 渲染错误', async () => {
  await assert.rejects(callService({ errCode: 0, recommendations: [{ dishId: 'dish-1', name: 'x', price: 'bad', ingredients: null }], totalPrice: 1, reason: 'x' }))
})
