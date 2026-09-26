const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const pricing = require('../uniCloud-aliyun/cloudfunctions/orders/order-pricing')
const idempotency = require('../uniCloud-aliyun/cloudfunctions/orders/order-idempotency')
const orderSource = fs.readFileSync('uniCloud-aliyun/cloudfunctions/orders/index.obj.js', 'utf8')
const adminSource = fs.readFileSync('uniCloud-aliyun/cloudfunctions/order-idempotency-admin/index.js', 'utf8')
const schema = JSON.parse(fs.readFileSync('uniCloud-aliyun/database/orders.schema.json', 'utf8'))
const indexes = JSON.parse(fs.readFileSync('uniCloud-aliyun/database/orders.index.json', 'utf8'))
const clone = value => JSON.parse(JSON.stringify(value))
const clientId = 'anon-1234567890abcdef'
const requestId = 'test-id-001'

function items() {
  return [{ dishId: 'dish-4', quantity: 2 }]
}

function expected() {
  return { items: [{ dishId: 'dish-4', quantity: 2, unitPrice: 12, lineTotal: 24 }],
    totalQuantity: 2, totalPrice: 24 }
}

function payload(overrides = {}) {
  return { clientId, items: items(), expectedPreview: expected(), remark: '', requestId, ...overrides }
}

function createDb(options = {}) {
  const dishes = structuredClone(options.dishes || [
    { _id: 'dish-1', name: '招牌鸡腿饭', price: 28, status: 'on_sale' },
    { _id: 'dish-4', name: '柠檬茶', price: 12, status: 'on_sale' },
    { _id: 'dish-8', name: '酸梅汤', price: 14, status: 'sold_out' }
  ])
  const records = structuredClone(options.records || [])
  const calls = []
  let nextId = 1
  let initialLookupCount = 0
  let releaseInitialLookups
  const initialLookupsReady = options.concurrent
    ? new Promise(resolve => { releaseInitialLookups = resolve })
    : null

  const db = {
    command: { in: values => ({ values }) },
    collection(name) {
      calls.push({ operation: 'collection', name })
      if (name === 'dishes') {
        let ids = []
        return {
          where(query) { ids = query._id.values; return this },
          async get() {
            calls.push({ operation: 'dish-get' })
            if (options.readError) throw new Error('database password stack')
            return { data: dishes.filter(dish => ids.includes(dish._id)) }
          }
        }
      }
      if (name !== 'orders') throw new Error(`unexpected collection ${name}`)

      let query = null
      return {
        where(value) { query = value; return this },
        limit() { return this },
        orderBy() { return this },
        async get() {
          calls.push({ operation: 'order-get', query: clone(query) })
          if (options.lookupError) throw new Error('database lookup secret')
          if (options.concurrent && query?.requestId && records.length === 0 && initialLookupCount < 2) {
            initialLookupCount += 1
            if (initialLookupCount === 2) releaseInitialLookups()
            await initialLookupsReady
          }
          const data = query?.requestId
            ? records.filter(order => order.requestId === query.requestId)
            : query?.clientId ? records.filter(order => order.clientId === query.clientId) : records
          return { data: structuredClone(data) }
        },
        async add(order) {
          calls.push({ operation: 'add', requestId: order.requestId })
          if (options.writeError) throw Object.assign(new Error('database raw secret'), { code: options.writeCode })
          if (options.raceWinnerOnAdd && order.requestId) {
            records.push({ _id: 'race-winner', ...structuredClone(order) })
            throw Object.assign(new Error('duplicate request_id_unique internal'), { code: 'DUPLICATE_KEY' })
          }
          if (order.requestId && records.some(existing => existing.requestId === order.requestId)) {
            throw Object.assign(new Error('duplicate request_id_unique internal'), { code: 'DUPLICATE_KEY' })
          }
          if (options.orderNoCollision) {
            throw Object.assign(new Error('duplicate order_no_unique internal'), { code: 'DUPLICATE_KEY' })
          }
          const stored = { _id: `order-${nextId++}`, ...structuredClone(order) }
          records.push(stored)
          return { id: stored._id }
        }
      }
    }
  }
  return { db, dishes, records, calls }
}

function loadOrders(options = {}) {
  const data = createDb(options)
  const sandbox = {
    module: { exports: {} },
    uniCloud: { database: () => data.db },
    require(name) {
      if (name === 'crypto') return require('node:crypto')
      if (name === './order-pricing') return pricing
      if (name === './order-idempotency') return idempotency
      throw new Error(`unexpected require ${name}`)
    }
  }
  vm.runInNewContext(orderSource, sandbox)
  return { orders: sandbox.module.exports, ...data }
}

function fingerprint(value = payload()) {
  return idempotency.createRequestFingerprint(value)
}

test('orders schema将requestId和fingerprint设为可选字段，历史订单无需迁移', () => {
  assert.equal(schema.required.includes('requestId'), false)
  assert.equal(schema.required.includes('requestFingerprint'), false)
  assert.equal(schema.properties.requestId.minLength, 8)
  assert.equal(schema.properties.requestFingerprint.pattern, '^[a-f0-9]{64}$')
})

test('requestId使用阿里云稀疏唯一索引，embedding等字段不相关', () => {
  const index = indexes.find(item => item.IndexName === 'request_id_unique')
  assert.deepEqual(index, { IndexName: 'request_id_unique', MgoKeySchema: {
    MgoIndexKeys: [{ Name: 'requestId', Direction: '1' }], MgoIsUnique: true, MgoIsSparse: true
  } })
})

test('requestId可选：无requestId保持V5.5C成功结构且不保存幂等字段', async () => {
  const loaded = loadOrders(); const value = payload(); delete value.requestId
  const result = await loaded.orders.createConfirmedOrder(value)
  assert.equal(result.errCode, 0); assert.equal(loaded.records.length, 1)
  assert.equal(Object.hasOwn(loaded.records[0], 'requestId'), false)
  assert.equal(Object.hasOwn(loaded.records[0], 'requestFingerprint'), false)
})

test('合法requestId trim后保存，并持久化64位fingerprint', async () => {
  const loaded = loadOrders(); const result = await loaded.orders.createConfirmedOrder(payload({ requestId: '  test-id-001  ' }))
  assert.equal(result.errCode, 0); assert.equal(loaded.records[0].requestId, requestId)
  assert.match(loaded.records[0].requestFingerprint, /^[a-f0-9]{64}$/)
})

for (const [label, value] of [
  ['空字符串', ''], ['过短', 'short'], ['过长', 'a'.repeat(129)], ['非法字符', 'test/id/001'],
  ['换行', 'test-id-001\nnext'], ['非字符串', { value: requestId }]
]) {
  test(`非法requestId被安全拒绝：${label}`, async () => {
    const loaded = loadOrders(); const result = await loaded.orders.createConfirmedOrder(payload({ requestId: value }))
    assert.deepEqual(clone(result), { errCode: 'ORDER_REQUEST_ID_INVALID', errMsg: '订单请求标识无效，请重新发起结算' })
    assert.equal(loaded.records.length, 0)
  })
}

test('fingerprint对同一输入稳定且为SHA-256', () => {
  assert.equal(fingerprint(), fingerprint()); assert.match(fingerprint(), /^[a-f0-9]{64}$/)
})

test('items和expectedPreview数组顺序不影响fingerprint', () => {
  const first = payload({
    items: [{ dishId: 'dish-1', quantity: 1 }, { dishId: 'dish-4', quantity: 2 }],
    expectedPreview: { items: [
      { dishId: 'dish-4', quantity: 2, unitPrice: 12, lineTotal: 24 },
      { dishId: 'dish-1', quantity: 1, unitPrice: 28, lineTotal: 28 }
    ], totalQuantity: 3, totalPrice: 52 }
  })
  const second = clone(first)
  second.items.reverse(); second.expectedPreview.items.reverse()
  assert.equal(fingerprint(first), fingerprint(second))
})

for (const [label, mutate] of [
  ['remark变化', value => { value.remark = '少冰' }],
  ['quantity变化', value => { value.items[0].quantity = 3; value.expectedPreview.items[0].quantity = 3; value.expectedPreview.items[0].lineTotal = 36; value.expectedPreview.totalQuantity = 3; value.expectedPreview.totalPrice = 36 }],
  ['价格预期变化', value => { value.expectedPreview.items[0].unitPrice = 13; value.expectedPreview.items[0].lineTotal = 26; value.expectedPreview.totalPrice = 26 }],
  ['clientId变化', value => { value.clientId = 'anon-fedcba0987654321' }]
]) {
  test(`${label}会改变fingerprint`, () => {
    const changed = payload(); mutate(changed); assert.notEqual(fingerprint(), fingerprint(changed))
  })
}

test('同requestId同fingerprint重试返回首次订单且不再次计价或写入', async () => {
  const loaded = loadOrders(); const first = await loaded.orders.createConfirmedOrder(payload())
  const dishReads = loaded.calls.filter(call => call.operation === 'dish-get').length
  const second = await loaded.orders.createConfirmedOrder(payload())
  assert.equal(first.order.orderNo, second.order.orderNo); assert.equal(loaded.records.length, 1)
  assert.equal(loaded.calls.filter(call => call.operation === 'add').length, 1)
  assert.equal(loaded.calls.filter(call => call.operation === 'dish-get').length, dishReads)
})

test('重放响应和订单列表都不返回requestId或raw fingerprint', async () => {
  const loaded = loadOrders(); await loaded.orders.createConfirmedOrder(payload())
  const replay = await loaded.orders.createConfirmedOrder(payload())
  const listed = await loaded.orders.getOrders(clientId)
  for (const value of [replay.order, listed[0]]) {
    assert.equal(Object.hasOwn(value, 'requestId'), false)
    assert.equal(Object.hasOwn(value, 'requestFingerprint'), false)
    assert.equal(JSON.stringify(value).includes(loaded.records[0].requestFingerprint), false)
  }
})

test('同requestId不同quantity/expectedPreview返回冲突且不创建第二单', async () => {
  const loaded = loadOrders(); await loaded.orders.createConfirmedOrder(payload())
  const changed = payload(); changed.items[0].quantity = 3; changed.expectedPreview.items[0].quantity = 3
  changed.expectedPreview.items[0].lineTotal = 36; changed.expectedPreview.totalQuantity = 3; changed.expectedPreview.totalPrice = 36
  const result = await loaded.orders.createConfirmedOrder(changed)
  assert.deepEqual(clone(result), { errCode: 'ORDER_IDEMPOTENCY_CONFLICT', errMsg: '该订单请求已被其他内容使用，请重新发起结算' })
  assert.equal(loaded.records.length, 1)
})

test('不同clientId碰撞同requestId返回冲突，不泄露已有订单', async () => {
  const loaded = loadOrders(); await loaded.orders.createConfirmedOrder(payload())
  const result = await loaded.orders.createConfirmedOrder(payload({ clientId: 'anon-fedcba0987654321' }))
  assert.equal(result.errCode, 'ORDER_IDEMPOTENCY_CONFLICT')
  assert.equal(Object.hasOwn(result, 'order'), false); assert.equal(loaded.records.length, 1)
})

test('并发同requestId同payload由唯一约束只持久化一次并返回同一orderNo', async () => {
  const loaded = loadOrders({ concurrent: true })
  const [first, second] = await Promise.all([
    loaded.orders.createConfirmedOrder(payload()), loaded.orders.createConfirmedOrder(payload())
  ])
  assert.equal(first.errCode, 0); assert.equal(second.errCode, 0)
  assert.equal(first.order.orderNo, second.order.orderNo); assert.equal(loaded.records.length, 1)
  assert.equal(loaded.calls.filter(call => call.operation === 'add').length, 2)
})

test('唯一冲突后精确查询同requestId和fingerprint可恢复并返回竞争请求创建的订单', async () => {
  const loaded = loadOrders({ raceWinnerOnAdd: true })
  const result = await loaded.orders.createConfirmedOrder(payload())
  assert.equal(result.errCode, 0); assert.equal(result.order.orderNo, loaded.records[0].orderNo)
  assert.equal(loaded.records.length, 1); assert.equal(loaded.calls.filter(call => call.operation === 'add').length, 1)
})

test('其他唯一索引冲突且查不到requestId时不会误判为幂等重放', async () => {
  const loaded = loadOrders({ orderNoCollision: true })
  const result = await loaded.orders.createConfirmedOrder(payload())
  assert.deepEqual(clone(result), { errCode: 'ORDER_CREATE_FAILED', errMsg: '订单创建未完成，请稍后重试' })
  assert.equal(loaded.records.length, 0)
})

test('未知写入或查询异常安全泛化，不返回DB code、stack和fingerprint', async () => {
  for (const options of [{ writeError: true, writeCode: 'SOME_INTERNAL_CODE' }, { lookupError: true }]) {
    const loaded = loadOrders(options); const result = await loaded.orders.createConfirmedOrder(payload())
    assert.deepEqual(clone(result), { errCode: 'ORDER_CREATE_FAILED', errMsg: '订单创建未完成，请稍后重试' })
    const text = JSON.stringify(result)
    assert.equal(/database|stack|fingerprint|SOME_INTERNAL_CODE/i.test(text), false)
  }
})

test('V5.5C stale保护在幂等首次请求中保持', async () => {
  const loaded = loadOrders(); loaded.dishes.find(dish => dish._id === 'dish-4').price = 13
  assert.equal((await loaded.orders.createConfirmedOrder(payload())).errCode, 'ORDER_CONFIRMATION_STALE')
  assert.equal(loaded.records.length, 0)
})

test('V5.5C sold_out保护在幂等首次请求中保持', async () => {
  const loaded = loadOrders(); const value = payload({
    items: [{ dishId: 'dish-8', quantity: 1 }],
    expectedPreview: { items: [{ dishId: 'dish-8', quantity: 1, unitPrice: 14, lineTotal: 14 }], totalQuantity: 1, totalPrice: 14 }
  })
  assert.equal((await loaded.orders.createConfirmedOrder(value)).errCode, 'ORDER_DISH_UNAVAILABLE')
  assert.equal(loaded.records.length, 0)
})

test('成功订单快照继续使用实时服务器名称和价格', async () => {
  const loaded = loadOrders(); loaded.dishes[1].name = '实时柠檬茶'
  const result = await loaded.orders.createConfirmedOrder(payload())
  assert.deepEqual(clone(result.order.items), [{ dishId: 'dish-4', name: '实时柠檬茶', price: 12, quantity: 2, subtotal: 24 }])
})

test('legacy createOrder保持无requestId原结构', async () => {
  const loaded = loadOrders(); const result = await loaded.orders.createOrder({ clientId, items: items(), remark: ' 少冰 ' })
  assert.equal(result._id, 'order-1'); assert.equal(result.remark, '少冰')
  assert.equal(Object.hasOwn(result, 'requestId'), false); assert.equal(Object.hasOwn(loaded.records[0], 'requestId'), false)
})

test('admin只允许server并只转发给正式createConfirmedOrder', async () => {
  let forwarded
  const context = { exports: {}, uniCloud: { importObject(name) {
    assert.equal(name, 'orders')
    return { async createConfirmedOrder(value) { forwarded = clone(value); return { errCode: 0, order: { orderNo: 'OD1' } } } }
  } } }
  vm.runInNewContext(adminSource, context)
  assert.equal((await context.exports.main(payload(), { SOURCE: 'client' })).errCode, 'ORDER_IDEMPOTENCY_FORBIDDEN')
  const result = await context.exports.main(payload(), { SOURCE: 'server' })
  assert.equal(result.errCode, 0); assert.deepEqual(forwarded, payload())
  assert.equal(/validateAndPrice|collection\(|createHash/.test(adminSource), false)
})

test('admin只恢复安全白名单错误，未知异常继续泛化', async () => {
  for (const [thrown, code] of [
    [{ errCode: 'ORDER_IDEMPOTENCY_CONFLICT', message: 'raw database' }, 'ORDER_IDEMPOTENCY_CONFLICT'],
    [{ code: 'UNKNOWN_INTERNAL', message: 'raw database' }, 'ORDER_CREATE_FAILED']
  ]) {
    const context = { exports: {}, uniCloud: { importObject() { return { async createConfirmedOrder() { throw thrown } } } } }
    vm.runInNewContext(adminSource, context)
    const result = await context.exports.main(payload(), { SOURCE: 'server' })
    assert.equal(result.errCode, code); assert.equal(JSON.stringify(result).includes('raw database'), false)
  }
})

test('幂等实现不包含支付、Agent Tool、外部依赖或敏感日志', () => {
  const source = orderSource + fs.readFileSync('uniCloud-aliyun/cloudfunctions/orders/order-idempotency.js', 'utf8')
  for (const pattern of [/requestPayment\s*\(/, /create_order/, /DASHSCOPE/, /Authorization/, /console\.log/]) {
    assert.equal(pattern.test(source), false, String(pattern))
  }
})
