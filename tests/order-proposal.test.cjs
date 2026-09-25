const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const serviceText = fs.readFileSync('src/services/orders.js', 'utf8')
const pageText = fs.readFileSync('src/pages/agent/index.vue', 'utf8')
const clone = value => JSON.parse(JSON.stringify(value))
const cart = () => [{ id: 'dish-4', name: '客户端名称', price: 0.01, status: 'sold_out', quantity: 2 }]
const requestItems = () => [{ dishId: 'dish-4', quantity: 2 }]
const validResponse = () => ({ errCode: 0, preview: {
  items: [{ dishId: 'dish-4', name: '柠檬茶', quantity: 2, unitPrice: 12, lineTotal: 24 }],
  totalQuantity: 2, totalPrice: 24, requiresConfirmation: true
} })

function loadService(options = {}) {
  const calls = { imports: [], preview: [], create: 0 }
  const cloud = {
    async previewOrder(items) {
      calls.preview.push(clone(items))
      if (options.throwValue) throw options.throwValue
      return options.reply === undefined ? validResponse() : options.reply
    },
    async createOrder() { calls.create += 1; throw new Error('createOrder must not run') }
  }
  const context = {
    getClientId: () => 'anon-test',
    uniCloud: { importObject(name, config) {
      calls.imports.push({ name, config: config ? clone(config) : undefined })
      return cloud
    } }
  }
  const source = serviceText.replace(/^import .*$/gm, '')
    .replaceAll('export async function ', 'async function ').replaceAll('export function ', 'function ')
  vm.runInNewContext(source + `\nthis.api={buildOrderPreviewItems,validateOrderPreview,
    isSameCartSnapshot,previewOrder}`, context)
  return { ...context.api, calls }
}

function validProposal() {
  return {
    orderPendingAction: { type: 'create_order', items: validResponse().preview.items,
      totalQuantity: 2, totalPrice: 24, requiresConfirmation: true },
    cartSnapshot: requestItems()
  }
}

function loadPage(options = {}) {
  const calls = { run: 0, preview: 0, execute: 0, add: 0, clear: 0, navigation: [] }
  const cartStore = {
    items: options.cartItems || [],
    addDish() { calls.add += 1; return true },
    clearCart() { calls.clear += 1; cartStore.items = [] }
  }
  const snapshotService = loadService()
  const context = {
    ref: value => ({ value }),
    computed: getter => ({ get value() { return getter() } }),
    runOrderingAgent: async query => { calls.run += 1; return options.agentReply ||
      { errCode: 0, query, answer: '已处理', completed: true } },
    executePendingCartAction: async () => { calls.execute += 1; return { name: '柠檬茶', quantity: 1 } },
    getDishes: async () => [],
    previewOrder: async items => { calls.preview += 1; return options.preview ? options.preview(items) : validProposal() },
    isSameCartSnapshot: snapshotService.isSameCartSnapshot,
    useCartStore: () => cartStore,
    uni: { switchTab: target => calls.navigation.push(target) }
  }
  const script = pageText.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  vm.runInNewContext(script + `\nthis.state={query,cartPendingAction,orderPendingAction,orderCartSnapshot,
    orderProposalConfirmed,orderStatus,orderStatusType,orderPreviewLoading,cartItemCount,
    generateOrderPreview,confirmOrderProposal,cancelOrderProposal,submitQuery}`, context)
  return { ...context.state, calls, cartStore }
}

test('正式Service调用orders.previewOrder并启用customUI', async () => {
  const service = loadService()
  await service.previewOrder(cart())
  assert.deepEqual(service.calls.imports, [{ name: 'orders', config: { customUI: true } }])
  assert.deepEqual(service.calls.preview, [requestItems()])
})

test('结算请求只提取dishId和quantity', () => {
  assert.deepEqual(clone(loadService().buildOrderPreviewItems(cart())), requestItems())
})

for (const [name, value] of [
  ['非数组', null], ['空购物车', []], ['超过30种', Array.from({ length: 31 }, (_, index) => ({ id: `d-${index}`, quantity: 1 }))],
  ['dishId缺失', [{ quantity: 1 }]], ['dishId空白', [{ id: '  ', quantity: 1 }]],
  ['数量为0', [{ id: 'dish-4', quantity: 0 }]], ['数量小数', [{ id: 'dish-4', quantity: 1.5 }]],
  ['数量字符串', [{ id: 'dish-4', quantity: '2' }]], ['数量超过99', [{ id: 'dish-4', quantity: 100 }]],
  ['重复菜品', [{ id: 'dish-4', quantity: 1 }, { id: 'dish-4', quantity: 2 }]]
]) {
  test(`购物车基础校验拒绝${name}且不调用云对象`, async () => {
    const service = loadService()
    await assert.rejects(() => service.previewOrder(value), error => error.errCode === 'ORDER_ITEMS_INVALID')
    assert.equal(service.calls.imports.length, 0)
  })
}

test('合法Preview形成最小Order Pending Action和快照', async () => {
  const result = await loadService().previewOrder(cart())
  assert.deepEqual(clone(result), validProposal())
  assert.deepEqual(Object.keys(result.orderPendingAction).sort(),
    ['items', 'requiresConfirmation', 'totalPrice', 'totalQuantity', 'type'])
})

for (const [name, mutate] of [
  ['dishId不匹配', value => { value.preview.items[0].dishId = 'dish-7' }],
  ['菜名为空', value => { value.preview.items[0].name = '' }],
  ['quantity错误', value => { value.preview.items[0].quantity = 3 }],
  ['unitPrice非法', value => { value.preview.items[0].unitPrice = '12' }],
  ['unitPrice超过两位小数', value => { value.preview.items[0].unitPrice = 12.345 }],
  ['lineTotal不等于单价乘数量', value => { value.preview.items[0].lineTotal = 25 }],
  ['totalQuantity错误', value => { value.preview.totalQuantity = 3 }],
  ['totalPrice错误', value => { value.preview.totalPrice = 25 }],
  ['requiresConfirmation非true', value => { value.preview.requiresConfirmation = false }],
  ['Preview项目为空', value => { value.preview.items = [] }],
  ['项目包含未知字段', value => { value.preview.items[0].orderId = 'fake' }],
  ['Preview包含未知字段', value => { value.preview.orderNo = 'fake' }],
  ['外层包含未知字段', value => { value.raw = 'unsafe' }]
]) {
  test(`畸形Preview被拒绝：${name}`, async () => {
    const reply = validResponse(); mutate(reply)
    await assert.rejects(() => loadService({ reply }).previewOrder(cart()), error =>
      error.errCode === 'ORDER_PREVIEW_FAILED' && error.message === '暂时无法生成订单预览，请稍后重试。')
  })
}

for (const [code, message] of [
  ['ORDER_ITEMS_INVALID', '购物车内容无效，请返回购物车检查。'],
  ['ORDER_DISH_NOT_FOUND', '购物车中有菜品已下架，请重新选择。'],
  ['ORDER_DISH_UNAVAILABLE', '购物车中有菜品当前不可用，请返回购物车处理。'],
  ['ORDER_PREVIEW_FAILED', '暂时无法生成订单预览，请稍后重试。']
]) {
  test(`安全映射订单预览错误 ${code}`, async () => {
    const service = loadService({ reply: { errCode: code, errMsg: 'database Authorization stack' } })
    await assert.rejects(() => service.previewOrder(cart()), error => error.errCode === code && error.message === message)
    assert.equal(service.calls.create, 0)
  })
}

test('未知云端错误被泛化且不泄露内部信息', async () => {
  const service = loadService({ throwValue: Object.assign(new Error('database Authorization stack'), { errCode: 'DB_SECRET' }) })
  await assert.rejects(() => service.previewOrder(cart()), error =>
    error.errCode === 'ORDER_PREVIEW_FAILED' && !error.message.includes('database') && !error.message.includes('Authorization'))
})

test('快照比较忽略顺序但精确比较dishId和quantity', () => {
  const service = loadService()
  const current = [{ id: 'b', quantity: 2 }, { id: 'a', quantity: 1 }]
  assert.equal(service.isSameCartSnapshot(current, [{ dishId: 'a', quantity: 1 }, { dishId: 'b', quantity: 2 }]), true)
})

for (const [name, changed] of [
  ['数量变化', [{ id: 'dish-4', quantity: 3 }]],
  ['新增菜品', [{ id: 'dish-4', quantity: 2 }, { id: 'dish-7', quantity: 1 }]],
  ['删除菜品', []]
]) {
  test(`购物车${name}时快照失效`, () => {
    assert.equal(loadService().isSameCartSnapshot(changed, requestItems()), false)
  })
}

test('空购物车不能在页面生成Preview', async () => {
  const page = loadPage()
  await page.generateOrderPreview()
  assert.equal(page.calls.preview, 0); assert.equal(page.orderPendingAction.value, null)
})

test('页面成功生成订单预览卡且不调用Agent或购物车写方法', async () => {
  const page = loadPage({ cartItems: cart() })
  await page.generateOrderPreview()
  assert.equal(page.calls.preview, 1); assert.equal(page.calls.run, 0); assert.equal(page.calls.add, 0); assert.equal(page.calls.clear, 0)
  assert.equal(page.orderPendingAction.value.totalPrice, 24)
})

test('确认订单信息只修改页面状态且不清空购物车', async () => {
  const page = loadPage({ cartItems: cart() })
  await page.generateOrderPreview(); page.confirmOrderProposal()
  assert.equal(page.orderProposalConfirmed.value, true)
  assert.equal(page.orderStatus.value, '订单信息已确认，尚未创建订单。')
  assert.equal(page.calls.clear, 0); assert.equal(page.cartStore.items.length, 1)
})

test('取消只清除Order Pending Action且保留购物车', async () => {
  const page = loadPage({ cartItems: cart() })
  await page.generateOrderPreview(); page.cancelOrderProposal()
  assert.equal(page.orderPendingAction.value, null); assert.equal(page.orderStatus.value, '已取消订单预览。')
  assert.equal(page.calls.run, 0); assert.equal(page.calls.add, 0); assert.equal(page.calls.clear, 0)
})

for (const [name, mutate] of [
  ['数量变化', store => { store.items[0].quantity = 3 }],
  ['新增菜品', store => { store.items.push({ id: 'dish-7', quantity: 1 }) }],
  ['删除菜品', store => { store.items.splice(0, 1) }]
]) {
  test(`页面确认时检测${name}并清除旧Preview`, async () => {
    const page = loadPage({ cartItems: cart() })
    await page.generateOrderPreview(); mutate(page.cartStore); page.confirmOrderProposal()
    assert.equal(page.orderPendingAction.value, null)
    assert.equal(page.orderStatus.value, '购物车已发生变化，请重新生成订单预览。')
    assert.equal(page.calls.clear, 0)
  })
}

test('新Agent Query清理旧Order Pending Action', async () => {
  const page = loadPage({ cartItems: cart() })
  await page.generateOrderPreview(); page.query.value = '新问题'; await page.submitQuery()
  assert.equal(page.orderPendingAction.value, null); assert.deepEqual(clone(page.orderCartSnapshot.value), [])
})

test('Cart Pending Action与Order Pending Action保持独立', async () => {
  const cartAction = { type: 'add_to_cart', dishId: 'dish-4' }
  const page = loadPage({ cartItems: cart(), agentReply: { answer: '待确认', pendingAction: cartAction } })
  await page.generateOrderPreview()
  page.cartPendingAction.value = cartAction
  page.cancelOrderProposal()
  assert.deepEqual(page.cartPendingAction.value, cartAction); assert.equal(page.orderPendingAction.value, null)
})

test('V5.5B信息确认仍不调用旧createOrder，V5.5C只接正式confirmed接口', () => {
  const pageScript = pageText.match(/<script setup>([\s\S]*?)<\/script>/)[1]
  assert.equal(/\bcreateOrder\s*\(/.test(pageScript), false)
  assert.equal(pageScript.includes('createConfirmedOrder'), true)
  assert.equal(pageText.includes('确认订单信息'), true)
  assert.equal(pageText.includes('确认下单'), true)
})

test('正式Service不引用order-preview-admin且Preview路径不调用createOrder', async () => {
  const service = loadService()
  await service.previewOrder(cart())
  assert.equal(service.calls.create, 0)
  assert.equal(serviceText.includes('order-preview-admin'), true) // 仅中文注释说明禁止正式调用。
  assert.equal(service.calls.imports.some(call => call.name === 'order-preview-admin'), false)
})

test('RAG与AI页面未接入订单提案状态', () => {
  for (const file of ['src/pages/rag-qa/index.vue', 'src/pages/ai-recommend/index.vue']) {
    const text = fs.readFileSync(file, 'utf8')
    assert.equal(text.includes('orderPendingAction'), false); assert.equal(text.includes('previewOrder'), false)
  }
})
