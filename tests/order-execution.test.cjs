const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const pricing = require('../uniCloud-aliyun/cloudfunctions/orders/order-pricing')
const idempotency = require('../uniCloud-aliyun/cloudfunctions/orders/order-idempotency')
const orderSource = fs.readFileSync('uniCloud-aliyun/cloudfunctions/orders/index.obj.js', 'utf8')
const serviceText = fs.readFileSync('src/services/orders.js', 'utf8')
const pageText = fs.readFileSync('src/pages/agent/index.vue', 'utf8')
const clone = value => JSON.parse(JSON.stringify(value))
const clientId = 'anon-1234567890abcdef'
const items = () => [{ dishId: 'dish-4', quantity: 2 }]
const expected = () => ({ items: [{ dishId: 'dish-4', quantity: 2, unitPrice: 12, lineTotal: 24 }],
  totalQuantity: 2, totalPrice: 24 })
const action = () => ({ type: 'create_order', items: [{ dishId: 'dish-4', name: '柠檬茶', quantity: 2,
  unitPrice: 12, lineTotal: 24 }], totalQuantity: 2, totalPrice: 24, requiresConfirmation: true })

function createDb(options = {}) {
  const dishes = structuredClone(options.dishes || [
    { _id: 'dish-1', name: '鸡腿饭', price: 28, status: 'on_sale' },
    { _id: 'dish-4', name: '柠檬茶', price: 12, status: 'on_sale' },
    { _id: 'dish-8', name: '酸梅汤', price: 14, status: 'sold_out' }
  ])
  const calls = []
  const writes = []
  const db = { command: { in: values => ({ values }) }, collection(name) {
    calls.push({ operation: 'collection', name })
    if (name === 'dishes') {
      let ids = []
      return { where(query) { ids = query._id.values; return this }, async get() {
        calls.push({ operation: 'get', name })
        if (options.readError) throw new Error('database Authorization internal')
        return { data: dishes.filter(dish => ids.includes(dish._id)) }
      } }
    }
    if (name === 'orders') return { async add(order) {
      calls.push({ operation: 'add', name }); if (options.writeError) throw new Error('database stack secret')
      writes.push(structuredClone(order)); return { id: 'order-created' }
    }, where() { return this }, orderBy() { return this }, async get() { return { data: [] } } }
    throw new Error(`unexpected collection ${name}`)
  } }
  return { db, dishes, calls, writes }
}

function loadOrders(options = {}) {
  const data = createDb(options)
  const pricingModule = options.pricing || pricing
  const sandbox = { module: { exports: {} }, uniCloud: { database: () => data.db }, require(name) {
    if (name === 'crypto') return { randomBytes: () => Buffer.from([1, 2, 3]) }
    if (name === './order-pricing') return pricingModule
    if (name === './order-idempotency') return idempotency
    throw new Error(`unexpected require ${name}`)
  } }
  vm.runInNewContext(orderSource, sandbox)
  return { orders: sandbox.module.exports, ...data }
}

function payload(overrides = {}) {
  return { clientId, items: items(), expectedPreview: expected(), remark: '', ...overrides }
}

test('orders云对象提供createConfirmedOrder且legacy createOrder仍存在', () => {
  const orders = loadOrders().orders
  assert.equal(typeof orders.createConfirmedOrder, 'function'); assert.equal(typeof orders.createOrder, 'function')
})

test('实时计价与确认Preview一致时只写入一条订单', async () => {
  const loaded = loadOrders(); const result = await loaded.orders.createConfirmedOrder(payload())
  assert.equal(result.errCode, 0); assert.equal(loaded.writes.length, 1)
  assert.equal(result.order.orderNo.startsWith('OD'), true); assert.equal(result.order.totalPrice, 24)
})

test('Confirmed订单快照只使用服务器名称和价格', async () => {
  const loaded = loadOrders(); loaded.dishes.find(dish => dish._id === 'dish-4').name = '实时柠檬茶'
  const result = await loaded.orders.createConfirmedOrder(payload())
  assert.deepEqual(clone(result.order.items), [{ dishId: 'dish-4', name: '实时柠檬茶', price: 12, quantity: 2, subtotal: 24 }])
})

for (const [label, mutate] of [
  ['expectedPreview缺失', value => { delete value.expectedPreview }],
  ['payload额外字段', value => { value.price = 1 }],
  ['Preview额外字段', value => { value.expectedPreview.orderNo = 'fake' }],
  ['item额外字段', value => { value.expectedPreview.items[0].name = 'fake' }],
  ['unitPrice非法', value => { value.expectedPreview.items[0].unitPrice = '12' }],
  ['lineTotal非法', value => { value.expectedPreview.items[0].lineTotal = 23 }],
  ['totalQuantity非法', value => { value.expectedPreview.totalQuantity = 3 }],
  ['totalPrice非法', value => { value.expectedPreview.totalPrice = 25 }],
  ['重复dishId', value => { value.expectedPreview.items.push({ ...value.expectedPreview.items[0] }); value.expectedPreview.totalQuantity = 4; value.expectedPreview.totalPrice = 48 }]
]) {
  test(`严格拒绝不可信确认输入：${label}`, async () => {
    const value = payload(); mutate(value); const loaded = loadOrders()
    assert.equal((await loaded.orders.createConfirmedOrder(value)).errCode, 'ORDER_ITEMS_INVALID')
    assert.equal(loaded.writes.length, 0)
  })
}

test('服务器单价变化即使客户端旧Preview合法也返回STALE且不写入', async () => {
  const loaded = loadOrders(); loaded.dishes.find(dish => dish._id === 'dish-4').price = 13
  assert.deepEqual(clone(await loaded.orders.createConfirmedOrder(payload())), {
    errCode: 'ORDER_CONFIRMATION_STALE', errMsg: '订单信息已发生变化，请重新确认'
  })
  assert.equal(loaded.writes.length, 0)
})

test('菜品价格互相抵消但总价相同时仍逐项判定STALE', async () => {
  const dishes = [{ _id: 'a', name: 'A', price: 11, status: 'on_sale' }, { _id: 'b', name: 'B', price: 19, status: 'on_sale' }]
  const loaded = loadOrders({ dishes })
  const value = payload({ items: [{ dishId: 'a', quantity: 1 }, { dishId: 'b', quantity: 1 }], expectedPreview: {
    items: [{ dishId: 'a', quantity: 1, unitPrice: 10, lineTotal: 10 },
      { dishId: 'b', quantity: 1, unitPrice: 20, lineTotal: 20 }], totalQuantity: 2, totalPrice: 30
  } })
  assert.equal((await loaded.orders.createConfirmedOrder(value)).errCode, 'ORDER_CONFIRMATION_STALE')
  assert.equal(loaded.writes.length, 0)
})

for (const [label, changedItems, changedExpected] of [
  ['quantity变化', [{ dishId: 'dish-4', quantity: 1 }], expected()],
  ['item新增', [{ dishId: 'dish-4', quantity: 2 }, { dishId: 'dish-1', quantity: 1 }], expected()],
  ['item删除', [{ dishId: 'dish-4', quantity: 2 }], { items: [...expected().items,
    { dishId: 'dish-1', quantity: 1, unitPrice: 28, lineTotal: 28 }], totalQuantity: 3, totalPrice: 52 }]
]) {
  test(`${label}时确认已过期且不写订单`, async () => {
    const loaded = loadOrders()
    assert.equal((await loaded.orders.createConfirmedOrder(payload({ items: changedItems,
      expectedPreview: changedExpected }))).errCode, 'ORDER_CONFIRMATION_STALE')
    assert.equal(loaded.writes.length, 0)
  })
}

test('相同项目不同数组顺序仍允许创建', async () => {
  const loaded = loadOrders(); const value = payload({
    items: [{ dishId: 'dish-1', quantity: 1 }, { dishId: 'dish-4', quantity: 2 }],
    expectedPreview: { items: [{ dishId: 'dish-4', quantity: 2, unitPrice: 12, lineTotal: 24 },
      { dishId: 'dish-1', quantity: 1, unitPrice: 28, lineTotal: 28 }], totalQuantity: 3, totalPrice: 52 }
  })
  assert.equal((await loaded.orders.createConfirmedOrder(value)).errCode, 0); assert.equal(loaded.writes.length, 1)
})

test('最终创建时售罄返回安全业务错误并保留零写入', async () => {
  const loaded = loadOrders()
  const value = payload({ items: [{ dishId: 'dish-8', quantity: 1 }], expectedPreview: {
    items: [{ dishId: 'dish-8', quantity: 1, unitPrice: 14, lineTotal: 14 }], totalQuantity: 1, totalPrice: 14 } })
  assert.equal((await loaded.orders.createConfirmedOrder(value)).errCode, 'ORDER_DISH_UNAVAILABLE')
  assert.equal(loaded.writes.length, 0)
})

test('最终创建时菜品不存在返回安全业务错误', async () => {
  const loaded = loadOrders(); const value = payload({ items: [{ dishId: 'missing', quantity: 1 }], expectedPreview: {
    items: [{ dishId: 'missing', quantity: 1, unitPrice: 1, lineTotal: 1 }], totalQuantity: 1, totalPrice: 1 } })
  assert.equal((await loaded.orders.createConfirmedOrder(value)).errCode, 'ORDER_DISH_NOT_FOUND')
  assert.equal(loaded.writes.length, 0)
})

test('未知数据库读取和写入异常均泛化且不泄露', async () => {
  for (const options of [{ readError: true }, { writeError: true }]) {
    const loaded = loadOrders(options); const result = await loaded.orders.createConfirmedOrder(payload())
    assert.deepEqual(clone(result), { errCode: 'ORDER_CREATE_FAILED', errMsg: '订单创建未完成，请稍后重试' })
    assert.equal(JSON.stringify(result).includes('database'), false)
  }
})

test('legacy createOrder返回结构和订单快照保持兼容', async () => {
  const loaded = loadOrders(); const result = await loaded.orders.createOrder({ clientId, items: items(), remark: ' 少冰 ' })
  assert.equal(result._id, 'order-created'); assert.equal(result.totalPrice, 24); assert.equal(result.totalCount, 2)
  assert.equal(result.remark, '少冰'); assert.equal(result.status, 'pending'); assert.equal(loaded.writes.length, 1)
})

test('legacy和confirmed入口复用同一个pricing核心及persist helper', async () => {
  const calls = []
  const mockedPricing = { ...pricing, async validateAndPriceOrderItems(value, options) {
    calls.push({ value: clone(value), strict: options.strictItems })
    return { items: [{ dishId: 'dish-4', name: '柠檬茶', quantity: 2, unitPrice: 12, lineTotal: 24 }],
      totalQuantity: 2, totalPrice: 24 }
  } }
  const loaded = loadOrders({ pricing: mockedPricing })
  await loaded.orders.createOrder({ clientId, items: items(), remark: '' })
  await loaded.orders.createConfirmedOrder(payload())
  assert.deepEqual(calls.map(call => call.strict), [undefined, true]); assert.equal(loaded.writes.length, 2)
  assert.equal((orderSource.match(/db\.collection\('orders'\)\.add/g) || []).length, 1)
})

function validOrderResponse() {
  return { errCode: 0, order: { _id: 'order-created', orderNo: 'OD1780000000000010203',
    items: [{ dishId: 'dish-4', name: '柠檬茶', price: 12, quantity: 2, subtotal: 24 }],
    totalPrice: 24, totalCount: 2, remark: '', status: 'pending', clientId, createTime: 1780000000000 } }
}

function loadService(options = {}) {
  const calls = { confirmed: [], create: 0, imports: [] }
  const cloud = { async createConfirmedOrder(value) {
    calls.confirmed.push(clone(value)); if (options.throwValue) throw options.throwValue
    return options.reply === undefined ? validOrderResponse() : options.reply
  }, async createOrder() { calls.create += 1; throw new Error('legacy create forbidden') } }
  const context = { getClientId: () => clientId, uniCloud: { importObject(name, config) {
    calls.imports.push({ name, config: config ? clone(config) : undefined }); return cloud
  } } }
  const source = serviceText.replace(/^import .*$/gm, '')
    .replaceAll('export async function ', 'async function ').replaceAll('export function ', 'function ')
  vm.runInNewContext(source + '\nthis.api={buildExpectedPreview,buildConfirmedOrderSubmission,createConfirmedOrder,generateOrderRequestId}', context)
  return { ...context.api, calls }
}

test('前端正式调用orders.createConfirmedOrder且不调用旧createOrder', async () => {
  const service = loadService(); const result = await service.createConfirmedOrder([
    { id: 'dish-4', name: '本地假名', price: 0, quantity: 2 }
  ], action())
  assert.deepEqual(clone(result), { orderNo: 'OD1780000000000010203' }); assert.equal(service.calls.create, 0)
  assert.deepEqual(service.calls.imports, [{ name: 'orders', config: { customUI: true } }])
})

test('前端最终参数不发送Cart名称价格，expected也不发送name', async () => {
  const service = loadService(); await service.createConfirmedOrder([{ id: 'dish-4', name: '伪造', price: 0, quantity: 2 }], action())
  assert.deepEqual(service.calls.confirmed[0], { clientId, items: items(), expectedPreview: expected(), remark: '' })
})

for (const [code, message, invalidate] of [
  ['ORDER_ITEMS_INVALID', '订单内容无效，请重新生成预览。', true],
  ['ORDER_DISH_NOT_FOUND', '购物车中有菜品已下架，请重新生成预览。', true],
  ['ORDER_DISH_UNAVAILABLE', '购物车中有菜品当前不可用，请重新生成预览。', true],
  ['ORDER_CONFIRMATION_STALE', '订单信息已变化，请重新生成预览并确认。', true],
  ['ORDER_CREATE_FAILED', '暂时无法创建订单，请稍后重试。', false]
]) {
  test(`前端安全映射Confirmed错误 ${code}`, async () => {
    const service = loadService({ reply: { errCode: code, errMsg: 'database Authorization stack' } })
    await assert.rejects(() => service.createConfirmedOrder([{ id: 'dish-4', quantity: 2 }], action()), error =>
      error.errCode === code && error.message === message && error.invalidateProposal === invalidate)
  })
}

test('前端拒绝异常成功响应并且不暴露数据库_id', async () => {
  const reply = validOrderResponse(); reply.order.orderNo = 'bad'
  await assert.rejects(() => loadService({ reply }).createConfirmedOrder([{ id: 'dish-4', quantity: 2 }], action()),
    error => error.errCode === 'ORDER_CREATE_FAILED')
})

function loadPage(options = {}) {
  const calls = { create: 0, clear: 0, run: 0, preview: 0, execute: 0, navigation: [], generated: 0, built: 0, payloads: [] }
  const cartStore = { items: options.cartItems || [{ id: 'dish-4', quantity: 2 }],
    addDish() { return true }, clearCart() { calls.clear += 1; cartStore.items = [] } }
  const context = {
    ref: value => ({ value }), computed: getter => ({ get value() { return getter() } }),
    runOrderingAgent: async query => { calls.run += 1; return { query, answer: 'ok' } },
    executePendingCartAction: async () => { calls.execute += 1; return { name: '柠檬茶', quantity: 1 } },
    getDishes: async () => [], previewOrder: async () => { calls.preview += 1; return { orderPendingAction: action(), cartSnapshot: items() } },
    generateOrderRequestId: () => { calls.generated += 1; return `ord-test-${String(calls.generated).padStart(8, '0')}` },
    buildConfirmedOrderSubmission: (cartItems, pendingAction, remark, requestId) => {
      calls.built += 1
      return { requestId, clientId, items: cartItems.map(item => ({ dishId: item.id, quantity: item.quantity })),
        expectedPreview: { items: pendingAction.items.map(item => ({ dishId: item.dishId, quantity: item.quantity,
          unitPrice: item.unitPrice, lineTotal: item.lineTotal })), totalQuantity: pendingAction.totalQuantity,
        totalPrice: pendingAction.totalPrice }, remark }
    },
    createConfirmedOrder: async (...args) => { calls.create += 1; calls.payloads.push(clone(args[0]));
      return options.create ? options.create(...args) : { orderNo: 'OD1780000000000010203' } },
    isSameCartSnapshot: (current, snapshot) => current.length === snapshot.length && current.every(item =>
      snapshot.some(saved => saved.dishId === item.id && saved.quantity === item.quantity)),
    useCartStore: () => cartStore, uni: { switchTab: target => calls.navigation.push(target) }
  }
  const script = pageText.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  vm.runInNewContext(script + `\nthis.state={query,orderPendingAction,orderCartSnapshot,orderProposalConfirmed,
    orderStatus,orderStatusType,submittingOrder,createdOrderNo,orderRequestId,orderSubmissionPayload,
    orderOutcomeUnknown,generateOrderPreview,confirmOrderProposal,submitConfirmedOrder,cancelOrderProposal,
    submitQuery,confirmAction,cancelAction,fillExample,goToOrders}`, context)
  return { ...context.state, calls, cartStore }
}

async function preparePage(options = {}) {
  const page = loadPage(options); await page.generateOrderPreview(); page.confirmOrderProposal(); return page
}

test('最终确认前不会调用createConfirmedOrder', async () => {
  const page = await preparePage(); assert.equal(page.calls.create, 0); assert.equal(page.calls.clear, 0)
})

test('最终确认成功后显示orderNo、清空Cart并清除Proposal', async () => {
  const page = await preparePage(); await page.submitConfirmedOrder()
  assert.equal(page.calls.create, 1); assert.equal(page.calls.clear, 1); assert.equal(page.cartStore.items.length, 0)
  assert.equal(page.orderPendingAction.value, null); assert.equal(page.orderProposalConfirmed.value, false)
  assert.equal(page.orderStatus.value, '下单成功'); assert.equal(page.createdOrderNo.value, 'OD1780000000000010203')
})

test('最终确认双击只产生一次客户端创建调用', async () => {
  let resolve
  const page = await preparePage({ create: () => new Promise(done => { resolve = done }) })
  const first = page.submitConfirmedOrder(); const second = page.submitConfirmedOrder()
  assert.equal(page.submittingOrder.value, true); assert.equal(page.calls.create, 1)
  resolve({ orderNo: 'OD1780000000000010203' }); await Promise.all([first, second])
  assert.equal(page.calls.create, 1); assert.equal(page.calls.clear, 1)
})

test('购物车变化时最终确认不调用服务器并让旧Proposal失效', async () => {
  const page = await preparePage(); page.cartStore.items[0].quantity = 3; await page.submitConfirmedOrder()
  assert.equal(page.calls.create, 0); assert.equal(page.calls.clear, 0); assert.equal(page.orderPendingAction.value, null)
  assert.equal(page.orderStatus.value, '购物车已发生变化，请重新生成订单预览。')
})

test('普通服务器失败不清Cart并保留Proposal供重试', async () => {
  const error = new Error('暂时无法创建订单，请稍后重试。'); error.invalidateProposal = false
  const page = await preparePage({ create: async () => { throw error } }); await page.submitConfirmedOrder()
  assert.equal(page.calls.clear, 0); assert.notEqual(page.orderPendingAction.value, null); assert.equal(page.orderProposalConfirmed.value, true)
})

for (const code of ['ORDER_CONFIRMATION_STALE', 'ORDER_DISH_UNAVAILABLE']) {
  test(`${code}失败保留Cart但清除旧Proposal`, async () => {
    const error = new Error('订单信息已变化，请重新生成预览并确认。'); error.errCode = code; error.invalidateProposal = true
    const page = await preparePage({ create: async () => { throw error } }); await page.submitConfirmedOrder()
    assert.equal(page.calls.clear, 0); assert.equal(page.cartStore.items.length, 1)
    assert.equal(page.orderPendingAction.value, null); assert.equal(page.orderProposalConfirmed.value, false)
  })
}

test('取消发生在最终创建前时不调用服务器且不清Cart', async () => {
  const page = await preparePage(); page.cancelOrderProposal(); await page.submitConfirmedOrder()
  assert.equal(page.calls.create, 0); assert.equal(page.calls.clear, 0)
})

test('新Agent Query清除已确认的旧Checkout状态', async () => {
  const page = await preparePage(); page.query.value = '新请求'; await page.submitQuery()
  assert.equal(page.orderPendingAction.value, null); assert.equal(page.orderProposalConfirmed.value, false)
  assert.equal(page.calls.create, 0)
})

test('最终订单执行不调用Qwen、菜单Tool或Agent create_order Tool', async () => {
  const page = await preparePage(); const runsBefore = page.calls.run; await page.submitConfirmedOrder()
  assert.equal(page.calls.run, runsBefore); assert.equal(page.calls.execute, 0)
  const agentText = fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent/tools/registry.js', 'utf8')
  assert.equal(agentText.includes("name: 'create_order'"), false)
})

test('成功后Proposal不能再次执行且查看订单使用既有TabBar', async () => {
  const page = await preparePage(); await page.submitConfirmedOrder(); await page.submitConfirmedOrder(); page.goToOrders()
  assert.equal(page.calls.create, 1); assert.deepEqual(clone(page.calls.navigation), [{ url: '/pages/orders/index' }])
})

test('最终链路没有支付、交易或退款API', () => {
  const changed = orderSource + serviceText + pageText
  for (const pattern of [/paymentStatus/, /refund\s*\(/, /trade\s*\(/, /requestPayment\s*\(/]) {
    assert.equal(pattern.test(changed), false, String(pattern))
  }
})

test('V5.6B requestId符合服务端字符与长度规则', () => {
  const requestId = loadService().generateOrderRequestId(1790000000000, () => 0.123456789)
  assert.match(requestId, /^[A-Za-z0-9_-]{8,128}$/)
  assert.equal(requestId.startsWith('ord-'), true)
})

test('V5.6B requestId由时间与多段随机值组成且不同输入不复用', () => {
  const service = loadService()
  const first = service.generateOrderRequestId(1790000000000, () => 0.1)
  const second = service.generateOrderRequestId(1790000000001, () => 0.2)
  assert.notEqual(first, second)
})

test('V5.6B冻结payload只包含requestId、clientId、items、expectedPreview和remark', () => {
  const service = loadService()
  const submission = service.buildConfirmedOrderSubmission(
    [{ id: 'dish-4', name: '本地名称', price: 0, quantity: 2 }], action(), '', 'ord-test-00000001')
  assert.deepEqual(Object.keys(submission).sort(), ['clientId', 'expectedPreview', 'items', 'remark', 'requestId'])
  assert.deepEqual(clone(submission), { requestId: 'ord-test-00000001', clientId, items: items(),
    expectedPreview: expected(), remark: '' })
  assert.equal(Object.isFrozen(submission), true)
  assert.equal(Object.isFrozen(submission.items), true)
  assert.equal(Object.isFrozen(submission.expectedPreview), true)
})

test('V5.6B正式service把冻结payload和requestId发送给orders而不调用admin', async () => {
  const service = loadService()
  const submission = service.buildConfirmedOrderSubmission(
    [{ id: 'dish-4', quantity: 2 }], action(), '', 'ord-test-00000002')
  await service.createConfirmedOrder(submission)
  assert.deepEqual(service.calls.confirmed[0], clone(submission))
  assert.deepEqual(service.calls.imports, [{ name: 'orders', config: { customUI: true } }])
  assert.equal(serviceText.includes("importObject('order-idempotency-admin'"), false)
})

for (const [code, message] of [
  ['ORDER_IDEMPOTENCY_CONFLICT', '订单请求与已提交内容冲突，请重新生成预览。'],
  ['ORDER_REQUEST_ID_INVALID', '订单请求标识无效，请重新生成预览。']
]) {
  test(`V5.6B ${code}属于明确失败并使用安全文案`, async () => {
    const service = loadService({ reply: { errCode: code, errMsg: 'database stack requestId secret' } })
    const submission = service.buildConfirmedOrderSubmission(
      [{ id: 'dish-4', quantity: 2 }], action(), '', 'ord-test-00000003')
    await assert.rejects(() => service.createConfirmedOrder(submission), error =>
      error.errCode === code && error.invalidateProposal === true && error.outcomeUnknown === false &&
      error.message === message && !error.message.includes('database'))
  })
}

test('V5.6B未知transport错误映射为结果未知且不泄露原始内容', async () => {
  const service = loadService({ throwValue: new Error('timeout Authorization database stack') })
  const submission = service.buildConfirmedOrderSubmission(
    [{ id: 'dish-4', quantity: 2 }], action(), '', 'ord-test-00000004')
  await assert.rejects(() => service.createConfirmedOrder(submission), error =>
    error.errCode === 'ORDER_CREATE_FAILED' && error.invalidateProposal === false &&
    error.outcomeUnknown === true && !error.message.includes('Authorization'))
})

test('V5.6B Preview和信息确认阶段不提前生成requestId', async () => {
  const page = await preparePage()
  assert.equal(page.calls.generated, 0)
  assert.equal(page.orderRequestId.value, null)
  assert.equal(page.orderSubmissionPayload.value, null)
})

test('V5.6B第一次最终提交前只生成一次requestId并传入service', async () => {
  const page = await preparePage(); await page.submitConfirmedOrder()
  assert.equal(page.calls.generated, 1); assert.equal(page.calls.built, 1); assert.equal(page.calls.create, 1)
  assert.equal(page.calls.payloads[0].requestId, 'ord-test-00000001')
})

test('V5.6B结果未知保留requestId、冻结payload、Cart和确认状态', async () => {
  const error = new Error('transport timeout'); error.invalidateProposal = false
  const page = await preparePage({ create: async () => { throw error } }); await page.submitConfirmedOrder()
  assert.equal(page.orderRequestId.value, 'ord-test-00000001')
  assert.notEqual(page.orderSubmissionPayload.value, null)
  assert.equal(page.orderPendingAction.value.type, 'create_order')
  assert.equal(page.orderProposalConfirmed.value, true)
  assert.equal(page.orderOutcomeUnknown.value, true)
  assert.equal(page.calls.clear, 0); assert.equal(page.cartStore.items.length, 1)
  assert.equal(page.orderStatus.value, '订单结果暂未确认，请重试确认。重试不会重复创建同一订单。')
})

test('V5.6B timeout后重试复用完全相同requestId和payload对象', async () => {
  let attempt = 0
  const page = await preparePage({ create: async () => {
    attempt += 1
    if (attempt === 1) { const error = new Error('timeout'); error.invalidateProposal = false; throw error }
    return { orderNo: 'OD1780000000000010203' }
  } })
  await page.submitConfirmedOrder()
  const frozen = page.orderSubmissionPayload.value
  const requestId = page.orderRequestId.value
  await page.submitConfirmedOrder()
  assert.equal(page.calls.generated, 1); assert.equal(page.calls.built, 1); assert.equal(page.calls.create, 2)
  assert.equal(page.calls.payloads[0].requestId, requestId)
  assert.deepEqual(page.calls.payloads[1], page.calls.payloads[0])
  assert.notEqual(frozen, null)
})

test('V5.6B Cart后续变化不会改变结果未知重试的冻结payload', async () => {
  let attempt = 0
  const page = await preparePage({ create: async () => {
    attempt += 1
    if (attempt < 2) { const error = new Error('network'); error.invalidateProposal = false; throw error }
    return { orderNo: 'OD1780000000000010203' }
  } })
  await page.submitConfirmedOrder()
  page.cartStore.items[0].quantity = 9
  await page.submitConfirmedOrder()
  assert.equal(page.calls.payloads[1].items[0].quantity, 2)
  assert.deepEqual(page.calls.payloads[1], page.calls.payloads[0])
})

test('V5.6B未知结果重试成功与首次成功一样清Cart和全部提交状态', async () => {
  let attempt = 0
  const page = await preparePage({ create: async () => {
    if (attempt++ === 0) { const error = new Error('network'); error.invalidateProposal = false; throw error }
    return { orderNo: 'OD1780000000000010203' }
  } })
  await page.submitConfirmedOrder(); await page.submitConfirmedOrder()
  assert.equal(page.calls.clear, 1); assert.equal(page.cartStore.items.length, 0)
  assert.equal(page.orderRequestId.value, null); assert.equal(page.orderSubmissionPayload.value, null)
  assert.equal(page.orderOutcomeUnknown.value, false); assert.equal(page.orderPendingAction.value, null)
  assert.equal(page.createdOrderNo.value, 'OD1780000000000010203')
})

for (const code of ['ORDER_CONFIRMATION_STALE', 'ORDER_DISH_UNAVAILABLE', 'ORDER_DISH_NOT_FOUND',
  'ORDER_ITEMS_INVALID', 'ORDER_IDEMPOTENCY_CONFLICT', 'ORDER_REQUEST_ID_INVALID']) {
  test(`V5.6B明确失败 ${code} 保留Cart并清除旧key、payload和Proposal`, async () => {
    const error = new Error('请重新生成预览'); error.errCode = code; error.invalidateProposal = true
    const page = await preparePage({ create: async () => { throw error } }); await page.submitConfirmedOrder()
    assert.equal(page.calls.clear, 0); assert.equal(page.cartStore.items.length, 1)
    assert.equal(page.orderRequestId.value, null); assert.equal(page.orderSubmissionPayload.value, null)
    assert.equal(page.orderOutcomeUnknown.value, false); assert.equal(page.orderPendingAction.value, null)
  })
}

test('V5.6B明确失败后新Preview会为新订单意图生成新requestId', async () => {
  let attempt = 0
  const page = await preparePage({ create: async () => {
    attempt += 1
    if (attempt === 1) { const error = new Error('stale'); error.invalidateProposal = true; throw error }
    return { orderNo: 'OD1780000000000010203' }
  } })
  await page.submitConfirmedOrder()
  await page.generateOrderPreview(); page.confirmOrderProposal(); await page.submitConfirmedOrder()
  assert.equal(page.calls.generated, 2)
  assert.notEqual(page.calls.payloads[0].requestId, page.calls.payloads[1].requestId)
})

test('V5.6B普通取消发生在提交前会清除所有订单意图状态', async () => {
  const page = await preparePage(); page.cancelOrderProposal()
  assert.equal(page.orderPendingAction.value, null); assert.equal(page.orderRequestId.value, null)
  assert.equal(page.orderSubmissionPayload.value, null); assert.equal(page.orderOutcomeUnknown.value, false)
})

test('V5.6B结果未知时本地取消不会清除可能已创建的订单意图', async () => {
  const error = new Error('network'); error.invalidateProposal = false
  const page = await preparePage({ create: async () => { throw error } }); await page.submitConfirmedOrder()
  page.cancelOrderProposal()
  assert.notEqual(page.orderPendingAction.value, null); assert.notEqual(page.orderSubmissionPayload.value, null)
  assert.equal(page.orderOutcomeUnknown.value, true)
})

test('V5.6B结果未知时阻止新Agent Query与新Preview', async () => {
  const error = new Error('network'); error.invalidateProposal = false
  const page = await preparePage({ create: async () => { throw error } }); await page.submitConfirmedOrder()
  const runBefore = page.calls.run; const previewBefore = page.calls.preview
  await page.submitQuery(); await page.generateOrderPreview()
  assert.equal(page.calls.run, runBefore); assert.equal(page.calls.preview, previewBefore)
})

test('V5.6B结果未知时阻止旧加购Action确认和取消', async () => {
  const error = new Error('network'); error.invalidateProposal = false
  const page = await preparePage({ create: async () => { throw error } }); await page.submitConfirmedOrder()
  await page.confirmAction(); page.cancelAction()
  assert.equal(page.calls.execute, 0)
})

test('V5.6B UI显示重试语义但不展示requestId或fingerprint', () => {
  const template = pageText.match(/<template>([\s\S]*?)<\/template>/)[1]
  assert.equal(template.includes('重试确认下单'), true)
  assert.equal(pageText.includes('重试不会重复创建同一订单'), true)
  assert.equal(template.includes('orderRequestId'), false)
  assert.equal(template.includes('requestFingerprint'), false)
})

test('V5.6B不记录requestId且不加入持久化恢复或新依赖', () => {
  assert.equal(/console\.(log|info|warn|error)\([^\n]*requestId/.test(serviceText + pageText), false)
  assert.equal(pageText.includes('setStorageSync'), false)
  assert.equal(serviceText.includes('randomUUID'), false)
})
