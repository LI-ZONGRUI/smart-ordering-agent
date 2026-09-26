const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const shared = require('../uniCloud-aliyun/cloudfunctions/common/menu-read-domain')
const nativeTools = require('../uniCloud-aliyun/cloudfunctions/agent/tools/menu-tools')
const gatewayDomain = require('../uniCloud-aliyun/cloudfunctions/framework-gateway/menu-domain')
const { createMenuDb } = require('./helpers/menu-db.cjs')

test('Native Agent与Framework Gateway加载同一Shared Domain函数', () => {
  for (const name of ['searchMenu', 'listAvailableDrinks', 'getDishDetail']) {
    assert.equal(nativeTools[name], shared[name])
    assert.equal(gatewayDomain[name], shared[name])
  }
})

test('Shared search_menu可乐保持字面空结果', async () => {
  const { db } = createMenuDb()
  assert.deepEqual(await shared.searchMenu({ query: '可乐' }, { db }), {
    tool: 'search_menu', query: '可乐', count: 0, items: []
  })
})

test('Shared search_menu柠檬茶保持原字段与在售状态', async () => {
  const { db } = createMenuDb()
  const result = await shared.searchMenu({ query: '柠檬茶' }, { db })
  assert.equal(result.count, 1)
  assert.deepEqual(result.items[0], {
    dishId: 'dish-4', name: '柠檬茶', categoryId: 'drink', price: 12,
    status: 'on_sale', spicyLevel: 0
  })
})

test('Shared list_available_drinks保持运行时分类解析与on_sale过滤', async () => {
  const fixture = createMenuDb()
  const result = await shared.listAvailableDrinks({}, { db: fixture.db })
  assert.equal(result.tool, 'list_available_drinks')
  assert.deepEqual(result.items.map(item => item.dishId), ['dish-4'])
  assert.ok(fixture.calls.some(call => call.name === 'categories' && call.condition.name === '饮料'))
})

test('Shared get_dish_detail保持dish-4详情白名单', async () => {
  const { db } = createMenuDb()
  const result = await shared.getDishDetail({ dishId: 'dish-4' }, { db })
  assert.equal(result.found, true)
  assert.deepEqual(result.item, {
    dishId: 'dish-4', name: '柠檬茶', categoryId: 'drink', price: 12,
    status: 'on_sale', spicyLevel: 0, description: '清爽柠檬香气，适合搭配正餐。',
    ingredients: ['红茶', '柠檬']
  })
})

test('Shared详情保持sold_out真实状态', async () => {
  const { db } = createMenuDb()
  const result = await shared.getDishDetail({ dishId: 'dish-8' }, { db })
  assert.equal(result.found, true)
  assert.equal(result.item.status, 'sold_out')
  assert.equal(result.item.price, 14)
})

test('Shared详情不存在保持found=false业务结果', async () => {
  const { db } = createMenuDb()
  assert.deepEqual(await shared.getDishDetail({ dishId: 'missing' }, { db }), {
    tool: 'get_dish_detail', dishId: 'missing', found: false, item: null
  })
})

test('Shared Domain只读取固定集合且数据库失败不泄露为业务结果', async () => {
  const { db } = createMenuDb({ fails: true })
  await assert.rejects(shared.searchMenu({ query: '鸡' }, { db }), /private database detail/)
})

test('Shared Domain不包含网络、模型或数据库写能力', () => {
  const source = fs.readFileSync(
    'uniCloud-aliyun/cloudfunctions/common/menu-read-domain/index.js', 'utf8'
  ).replaceAll('seen.add(row._id)', '')
  for (const pattern of [/httpclient/,/DASHSCOPE/,/chat\/completions/,/\.add\(/,
    /\.update\(/,/\.remove\(/,/createOrder/,/prepareAddToCart/]) {
    assert.ok(!pattern.test(source), String(pattern))
  }
})
