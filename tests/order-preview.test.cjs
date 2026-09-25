const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const pricingPath = '../uniCloud-aliyun/cloudfunctions/orders/order-pricing'
const pricingModule = require(pricingPath)
const { validateAndPriceOrderItems } = pricingModule
const orderSource = fs.readFileSync('uniCloud-aliyun/cloudfunctions/orders/index.obj.js', 'utf8')
const adminSource = fs.readFileSync('uniCloud-aliyun/cloudfunctions/order-preview-admin/index.js', 'utf8')

const seedDishes = [
  { _id: 'dish-1', name: '招牌鸡腿饭', price: 28.15, status: 'on_sale' },
  { _id: 'dish-4', name: '柠檬茶', price: 12, status: 'on_sale' },
  { _id: 'dish-8', name: '酸梅汤', price: 14, status: 'sold_out' }
]

function createDb(options = {}) {
  const dishes = structuredClone(options.dishes || seedDishes)
  const calls = []
  const writes = []
  const db = {
    command: { in: values => ({ operator: 'in', values }) },
    collection(name) {
      calls.push({ operation: 'collection', name })
      if (name === 'dishes') {
        let condition
        return {
          where(value) { condition = value; calls.push({ operation: 'where', name, value }); return this },
          async get() {
            calls.push({ operation: 'get', name })
            if (options.readError) throw new Error('database password Authorization secret')
            if (options.badResponse) return { data: null }
            const ids = condition?._id?.values || []
            return { data: dishes.filter(dish => ids.includes(dish._id)) }
          },
          add() { assert.fail('preview must not add dishes') },
          update() { assert.fail('preview must not update dishes') },
          remove() { assert.fail('preview must not remove dishes') }
        }
      }
      if (name === 'orders') {
        return {
          async add(order) {
            calls.push({ operation: 'add', name })
            writes.push(structuredClone(order))
            if (options.writeError) throw new Error('database internal secret')
            return { id: 'order-created' }
          },
          where() { return this }, orderBy() { return this }, async get() { return { data: [] } },
          update() { assert.fail('orders update is outside this flow') },
          remove() { assert.fail('orders remove is outside this flow') }
        }
      }
      assert.fail(`unexpected collection: ${name}`)
    }
  }
  return { db, dishes, calls, writes }
}

function loadOrders(options = {}) {
  const data = options.data || createDb(options)
  const pricing = options.pricing || pricingModule
  const sandbox = {
    module: { exports: {} },
    uniCloud: { database: () => data.db },
    require(name) {
      if (name === 'crypto') return { randomBytes: () => Buffer.from([1, 2, 3]) }
      if (name === './order-pricing') return pricing
      throw new Error(`unexpected require: ${name}`)
    }
  }
  vm.runInNewContext(orderSource, sandbox)
  return { orders: sandbox.module.exports, ...data }
}

function json(value) {
  return JSON.parse(JSON.stringify(value))
}

const validClientId = 'anon-1234567890abcdef'

test('orders云对象提供正式previewOrder方法', () => {
  assert.equal(typeof loadOrders().orders.previewOrder, 'function')
})

for (const [label, items] of [
  ['非数组', null],
  ['空数组', []],
  ['超过30种', Array.from({ length: 31 }, (_, index) => ({ dishId: `dish-${index}`, quantity: 1 }))]
]) {
  test(`Preview拒绝${label}`, async () => {
    const loaded = loadOrders()
    assert.deepEqual(json(await loaded.orders.previewOrder(items)), {
      errCode: 'ORDER_ITEMS_INVALID', errMsg: '订单菜品或数量无效'
    })
    assert.equal(loaded.calls.some(call => call.operation === 'get'), false)
  })
}

for (const [label, item] of [
  ['缺少dishId', { quantity: 1 }],
  ['dishId非字符串', { dishId: 4, quantity: 1 }],
  ['dishId空字符串', { dishId: '', quantity: 1 }],
  ['quantity缺失', { dishId: 'dish-4' }],
  ['quantity为0', { dishId: 'dish-4', quantity: 0 }],
  ['quantity为负数', { dishId: 'dish-4', quantity: -1 }],
  ['quantity为小数', { dishId: 'dish-4', quantity: 1.5 }],
  ['quantity为字符串', { dishId: 'dish-4', quantity: '2' }],
  ['quantity超过99', { dishId: 'dish-4', quantity: 100 }]
]) {
  test(`Preview拒绝非法项目：${label}`, async () => {
    assert.deepEqual(json(await loadOrders().orders.previewOrder([item])), {
      errCode: 'ORDER_ITEMS_INVALID', errMsg: '订单菜品或数量无效'
    })
  })
}

test('Preview与Create共享数量上限1～99', async () => {
  const preview = loadOrders()
  assert.equal((await preview.orders.previewOrder([{ dishId: 'dish-4', quantity: 99 }])).preview.totalQuantity, 99)
  const create = loadOrders()
  assert.equal((await create.orders.createOrder({ clientId: validClientId,
    items: [{ dishId: 'dish-4', quantity: 99 }] })).totalCount, 99)
  await assert.rejects(() => loadOrders().orders.createOrder({ clientId: validClientId,
    items: [{ dishId: 'dish-4', quantity: 100 }] }), /菜品或数量无效/)
})

test('Preview严格拒绝客户端name、price、status和lineTotal', async () => {
  for (const extra of [{ name: '伪造' }, { price: 0 }, { status: 'on_sale' }, { lineTotal: 0 }]) {
    assert.equal((await loadOrders().orders.previewOrder([
      { dishId: 'dish-4', quantity: 2, ...extra }
    ])).errCode, 'ORDER_ITEMS_INVALID')
  }
})

test('Preview拒绝重复dishId，与Create规则一致', async () => {
  const items = [{ dishId: 'dish-4', quantity: 1 }, { dishId: 'dish-4', quantity: 2 }]
  assert.deepEqual(json(await loadOrders().orders.previewOrder(items)), {
    errCode: 'ORDER_ITEMS_INVALID', errMsg: '订单菜品或数量无效'
  })
  await assert.rejects(() => loadOrders().orders.createOrder({ clientId: validClientId, items }), error =>
    error.message === '菜品或数量无效，请返回购物车检查' && !Object.hasOwn(error, 'errCode'))
})

test('不存在菜品时拒绝且不使用客户端缓存事实', async () => {
  assert.deepEqual(json(await loadOrders().orders.previewOrder([{ dishId: 'missing', quantity: 1 }])), {
    errCode: 'ORDER_DISH_NOT_FOUND', errMsg: '未找到对应菜品'
  })
})

test('sold_out菜品拒绝生成Preview', async () => {
  const result = await loadOrders().orders.previewOrder([{ dishId: 'dish-8', quantity: 1 }])
  assert.deepEqual(json(result), { errCode: 'ORDER_DISH_UNAVAILABLE', errMsg: '当前菜品不可用' })
  assert.equal(Object.hasOwn(result, 'preview'), false)
})

test('正常Preview的名称、单价、行金额和总额全部由服务器生成', async () => {
  const loaded = loadOrders()
  const dish = loaded.dishes.find(item => item._id === 'dish-4')
  dish.name = '实时柠檬茶'; dish.price = 12.34
  const result = await loaded.orders.previewOrder([{ dishId: 'dish-4', quantity: 2 }])
  assert.deepEqual(json(result), { errCode: 0, preview: { items: [{ dishId: 'dish-4', name: '实时柠檬茶',
    quantity: 2, unitPrice: 12.34, lineTotal: 24.68 }], totalQuantity: 2,
  totalPrice: 24.68, requiresConfirmation: true } })
})

test('金额按整数分计算，多菜品总价和总数量准确', async () => {
  const loaded = loadOrders({ dishes: [
    { _id: 'a', name: 'A', price: 0.1, status: 'on_sale' },
    { _id: 'b', name: 'B', price: 0.2, status: 'on_sale' }
  ] })
  const result = await loaded.orders.previewOrder([{ dishId: 'a', quantity: 3 }, { dishId: 'b', quantity: 1 }])
  assert.equal(result.preview.items[0].lineTotal, 0.3)
  assert.equal(result.preview.items[1].lineTotal, 0.2)
  assert.equal(result.preview.totalPrice, 0.5)
  assert.equal(result.preview.totalQuantity, 4)
})

test('Preview只返回允许字段，不生成orderId、状态或支付字段', async () => {
  const result = await loadOrders().orders.previewOrder([{ dishId: 'dish-4', quantity: 1 }])
  assert.deepEqual(Object.keys(result.preview).sort(), ['items', 'requiresConfirmation', 'totalPrice', 'totalQuantity'])
  assert.deepEqual(Object.keys(result.preview.items[0]).sort(), ['dishId', 'lineTotal', 'name', 'quantity', 'unitPrice'])
  const text = JSON.stringify(result)
  for (const key of ['orderId', 'orderNo', 'status', 'paymentStatus']) assert.equal(text.includes(key), false)
})

test('Preview仅读取dishes，不访问orders或cart且不产生写操作', async () => {
  const loaded = loadOrders()
  await loaded.orders.previewOrder([{ dishId: 'dish-4', quantity: 2 }])
  assert.deepEqual(loaded.calls.filter(call => call.operation === 'collection').map(call => call.name), ['dishes'])
  assert.equal(loaded.writes.length, 0)
  assert.equal(loaded.calls.some(call => ['add', 'update', 'remove'].includes(call.operation)), false)
})

test('Create成功路径保持原订单快照与返回结构', async () => {
  const loaded = loadOrders()
  const result = await loaded.orders.createOrder({ clientId: validClientId,
    items: [{ dishId: 'dish-4', quantity: 2 }], remark: ' 少冰 ' })
  assert.equal(result._id, 'order-created')
  assert.match(result.orderNo, /^OD\d+010203$/)
  assert.deepEqual(json(result.items), [{ dishId: 'dish-4', name: '柠檬茶', price: 12, quantity: 2, subtotal: 24 }])
  assert.equal(result.totalPrice, 24); assert.equal(result.totalCount, 2)
  assert.equal(result.remark, '少冰'); assert.equal(result.status, 'pending'); assert.equal(result.clientId, validClientId)
  assert.equal(loaded.writes.length, 1)
  assert.deepEqual(json(loaded.writes[0]), json({ ...result, _id: undefined }))
})

test('Create继续拒绝售罄并在每次调用时读取实时价格', async () => {
  await assert.rejects(() => loadOrders().orders.createOrder({ clientId: validClientId,
    items: [{ dishId: 'dish-8', quantity: 1 }] }), error =>
    error.message === '酸梅汤 已售罄，请返回购物车删除' && !Object.hasOwn(error, 'errCode'))
  const loaded = loadOrders()
  loaded.dishes.find(item => item._id === 'dish-4').price = 13
  const order = await loaded.orders.createOrder({ clientId: validClientId, items: [{ dishId: 'dish-4', quantity: 2 }] })
  assert.equal(order.items[0].price, 13); assert.equal(order.items[0].subtotal, 26); assert.equal(order.totalPrice, 26)
})

test('Preview和Create调用同一个validation/pricing核心，Create也每次重新调用', async () => {
  const calls = []
  const pricing = { ...pricingModule, async validateAndPriceOrderItems(items, options) {
    calls.push({ items: json(items), strictItems: options.strictItems })
    return { items: [{ dishId: 'dish-4', name: '柠檬茶', quantity: 1, unitPrice: 12, lineTotal: 12 }],
      totalQuantity: 1, totalPrice: 12 }
  } }
  const loaded = loadOrders({ pricing })
  await loaded.orders.previewOrder([{ dishId: 'dish-4', quantity: 1 }])
  await loaded.orders.createOrder({ clientId: validClientId, items: [{ dishId: 'dish-4', quantity: 1 }] })
  assert.deepEqual(calls, [
    { items: [{ dishId: 'dish-4', quantity: 1 }], strictItems: true },
    { items: [{ dishId: 'dish-4', quantity: 1 }], strictItems: undefined }
  ])
})

test('数据库读取异常只返回固定安全错误，不泄露内部信息', async () => {
  for (const options of [{ readError: true }, { badResponse: true }]) {
    const result = await loadOrders(options).orders.previewOrder([{ dishId: 'dish-4', quantity: 1 }])
    assert.deepEqual(json(result), { errCode: 'ORDER_PREVIEW_FAILED', errMsg: '订单预览未完成，请稍后重试' })
    assert.ok(!JSON.stringify(result).includes('Authorization'))
    assert.ok(!JSON.stringify(result).includes('password'))
  }
})

function loadAdmin(previewOrder) {
  const calls = []
  const sandbox = { exports: {}, uniCloud: { importObject(name) {
    assert.equal(name, 'orders')
    return { async previewOrder(items) { calls.push(json(items)); return previewOrder(items) } }
  } } }
  vm.runInNewContext(adminSource, sandbox)
  return { main: sandbox.exports.main, calls }
}

test('order-preview-admin仅允许server并只转发items给正式previewOrder', async () => {
  const admin = loadAdmin(async items => ({ errCode: 0, preview: { items } }))
  for (const SOURCE of ['client', 'http', undefined]) {
    assert.equal((await admin.main({ items: [] }, { SOURCE })).errCode, 'ORDER_PREVIEW_FORBIDDEN')
  }
  const items = [{ dishId: 'dish-4', quantity: 2 }]
  const result = await admin.main({ items, ignored: 'value' }, { SOURCE: 'server' })
  assert.deepEqual(admin.calls, [items]); assert.deepEqual(json(result.preview.items), items)
})

test('order-preview-admin异常使用安全固定结果', async () => {
  const admin = loadAdmin(async () => { throw new Error('database collection Authorization secret stack') })
  const result = await admin.main({ items: [{ dishId: 'dish-4', quantity: 1 }] }, { SOURCE: 'server' })
  assert.deepEqual(json(result), { errCode: 'ORDER_PREVIEW_FAILED', errMsg: '订单预览未完成，请检查菜品状态和输入' })
  assert.ok(!JSON.stringify(result).includes('database'))
})

test('order-preview-admin只恢复白名单订单业务错误且使用固定文案', async () => {
  for (const [errCode, errMsg] of Object.entries({
    ORDER_ITEMS_INVALID: '订单菜品或数量无效',
    ORDER_DISH_NOT_FOUND: '未找到对应菜品',
    ORDER_DISH_UNAVAILABLE: '当前菜品不可用'
  })) {
    const returned = loadAdmin(async () => ({ errCode, errMsg: 'database Authorization secret', stack: 'secret stack' }))
    assert.deepEqual(json(await returned.main({ items: [] }, { SOURCE: 'server' })), { errCode, errMsg })

    const thrown = loadAdmin(async () => { throw { errCode, errMsg: 'database Authorization secret', stack: 'secret stack' } })
    assert.deepEqual(json(await thrown.main({ items: [] }, { SOURCE: 'server' })), { errCode, errMsg })
  }
})

test('order-preview-admin不透传未知自定义错误码', async () => {
  for (const failure of [
    { errCode: 'CUSTOM_DATABASE_ERROR', errMsg: 'database internals', stack: 'secret stack' },
    Object.assign(new Error('database internals'), { code: 'CUSTOM_DATABASE_ERROR' })
  ]) {
    const admin = loadAdmin(async () => {
      if (failure instanceof Error) throw failure
      return failure
    })
    const result = await admin.main({ items: [] }, { SOURCE: 'server' })
    assert.deepEqual(json(result), { errCode: 'ORDER_PREVIEW_FAILED', errMsg: '订单预览未完成，请检查菜品状态和输入' })
    assert.ok(!JSON.stringify(result).includes('database'))
    assert.equal(Object.hasOwn(result, 'stack'), false)
  }
})

test('admin不复制校验、查库、计价或订单写入逻辑', () => {
  for (const pattern of [/collection\s*\(/, /unitCents/, /lineTotal/, /totalPrice/, /\.add\s*\(/, /\.update\s*\(/, /\.remove\s*\(/]) {
    assert.equal(pattern.test(adminSource), false, String(pattern))
  }
  assert.match(adminSource, /orders\.previewOrder\(event\?\.items\)/)
})

test('Order Preview实现不包含Agent、模型API或购物车依赖', () => {
  const source = fs.readFileSync('uniCloud-aliyun/cloudfunctions/orders/order-pricing.js', 'utf8') + orderSource + adminSource
  for (const pattern of [/importObject\(['"]agent/, /DASHSCOPE_API_KEY/, /chat\/completions/, /Pinia/, /cartStore/, /collection\(['"]cart/]) {
    assert.equal(pattern.test(source), false, String(pattern))
  }
})
