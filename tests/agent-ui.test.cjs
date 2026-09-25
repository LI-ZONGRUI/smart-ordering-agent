const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const serviceText = fs.readFileSync('src/services/agent.js', 'utf8')
const pageText = fs.readFileSync('src/pages/agent/index.vue', 'utf8')
const clone = value => JSON.parse(JSON.stringify(value))
const validAction = overrides => ({ type: 'add_to_cart', dishId: 'dish-4', name: '柠檬茶', quantity: 2,
  unitPrice: 12, totalPrice: 24, requiresConfirmation: true, ...overrides })
const validResponse = overrides => ({ errCode: 0, query: '把柠檬茶加两杯到购物车', answer: '已准备，请确认。',
  completed: true, ...overrides })

function loadService(options = {}) {
  const calls = []
  const cloud = {
    async run(query) {
      calls.push({ method: 'run', query })
      if (options.throws) throw options.reply
      return options.reply === undefined ? validResponse() : options.reply
    },
    async runForAdmin() { calls.push({ method: 'runForAdmin' }); throw new Error('forbidden test path') }
  }
  const context = { setTimeout, clearTimeout, uniCloud: { importObject(name, config) {
    assert.equal(name, 'agent'); assert.equal(config.customUI, true); return cloud
  } } }
  const source = serviceText.replaceAll('export async function ', 'async function ').replaceAll('export function ', 'function ')
  vm.runInNewContext(source + '\nthis.api={runOrderingAgent,validatePendingAction,executePendingCartAction}', context)
  return { ...context.api, calls }
}

function loadPage(options = {}) {
  const calls = { run: 0, execute: 0, add: 0, menu: 0, preview: 0, clear: 0, navigation: [] }
  const cartStore = {
    items: options.cartItems || [],
    addDish(dish, quantity) { calls.add += 1; return options.addDish ? options.addDish(dish, quantity) : true },
    clearCart() { calls.clear += 1; cartStore.items = [] }
  }
  const context = {
    ref: value => ({ value }),
    computed: getter => ({ get value() { return getter() } }),
    runOrderingAgent: async query => {
      calls.run += 1
      return options.run ? options.run(query) : validResponse()
    },
    executePendingCartAction: async (action, dependencies) => {
      calls.execute += 1
      return options.execute ? options.execute(action, dependencies) : { name: action.name, quantity: action.quantity }
    },
    previewOrder: async items => { calls.preview += 1; return options.preview ? options.preview(items) : {
      orderPendingAction: { type: 'create_order', items: [], totalQuantity: 0, totalPrice: 0, requiresConfirmation: true },
      cartSnapshot: []
    } },
    isSameCartSnapshot: (items, snapshot) => options.sameSnapshot ? options.sameSnapshot(items, snapshot) : true,
    getDishes: async () => { calls.menu += 1; return options.dishes || [] },
    useCartStore: () => cartStore,
    uni: { switchTab: target => calls.navigation.push(target) }
  }
  const script = pageText.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  vm.runInNewContext(script + `\nthis.state={query,loading,result,errorMessage,cartPendingAction,confirming,
    actionStatus,actionStatusType,orderPreviewLoading,orderPendingAction,orderCartSnapshot,
    orderProposalConfirmed,orderStatus,orderStatusType,cartItems,cartItemCount,queryLength,
    submitQuery,confirmAction,cancelAction,fillExample,goToCart,generateOrderPreview,
    confirmOrderProposal,cancelOrderProposal}`, context)
  return { ...context.state, calls, cartStore }
}

test('Agent service trim query并调用正式agent.run', async () => {
  const service = loadService()
  const result = await service.runOrderingAgent('  把柠檬茶加两杯到购物车\n')
  assert.deepEqual(service.calls, [{ method: 'run', query: '把柠檬茶加两杯到购物车' }])
  assert.equal(result.answer, '已准备，请确认。')
})

for (const query of ['', ' \n ', null, 1, '中'.repeat(201)]) {
  test('Agent service拒绝非法Query且不调用云对象 ' + String(query).slice(0, 10), async () => {
    const service = loadService()
    await assert.rejects(() => service.runOrderingAgent(query), error => error.message === '请输入 1～200 字的问题。')
    assert.equal(service.calls.length, 0)
  })
}

test('Agent service按Unicode字符允许200字', async () => {
  const service = loadService(); await service.runOrderingAgent('🍋'.repeat(200)); assert.equal(service.calls.length, 1)
})

test('Agent service不调用runForAdmin且过滤Trace和内部字段', async () => {
  const service = loadService({ reply: validResponse({ trace: [{ secret: true }], messages: ['secret'], rawResponse: 'secret' }) })
  const result = await service.runOrderingAgent('你好')
  assert.deepEqual(service.calls, [{ method: 'run', query: '你好' }])
  assert.deepEqual(clone(result), { query: '你好', answer: '已准备，请确认。', completed: true })
})

for (const [code, message] of [
  ['AGENT_QUERY_INVALID', '请输入 1～200 字的问题。'],
  ['AGENT_CONFIG_MISSING', '点餐助手暂时不可用，请稍后重试。'],
  ['AGENT_MODEL_REQUEST_FAILED', '点餐助手暂时无法响应，请稍后重试。'],
  ['AGENT_MODEL_RESPONSE_INVALID', '点餐助手返回异常，请重新尝试。'],
  ['AGENT_MAX_STEPS_EXCEEDED', '本次请求未能完成，请换一种说法重试。'],
  ['AGENT_MAX_TOOL_CALLS_EXCEEDED', '本次请求未能完成，请换一种说法重试。'],
  ['AGENT_ACTION_DISH_NOT_FOUND', '没有找到对应菜品，请重新选择。'],
  ['AGENT_ACTION_DISH_UNAVAILABLE', '当前菜品不可用，请重新选择。']
]) {
  test('Agent service安全映射 ' + code, async () => {
    const service = loadService({ reply: { errCode: code, errMsg: 'Authorization secret database stack' } })
    await assert.rejects(() => service.runOrderingAgent('测试'), error => error.message === message && !error.message.includes('secret'))
  })
}

test('合法add_to_cart Pending Action被清洗并返回', async () => {
  const service = loadService({ reply: validResponse({ pendingAction: validAction() }) })
  assert.deepEqual(clone((await service.runOrderingAgent('加两杯')).pendingAction), validAction())
})

for (const [label, action] of [
  ['非法type', validAction({ type: 'create_order' })],
  ['quantity=0', validAction({ quantity: 0, totalPrice: 0 })],
  ['quantity>20', validAction({ quantity: 21, totalPrice: 252 })],
  ['quantity小数', validAction({ quantity: 1.5, totalPrice: 18 })],
  ['unitPrice非数字', validAction({ unitPrice: '12' })],
  ['totalPrice非数字', validAction({ totalPrice: NaN })],
  ['金额不一致', validAction({ totalPrice: 25 })],
  ['requiresConfirmation错误', validAction({ requiresConfirmation: false })],
  ['额外动态字段', { ...validAction(), method: 'clearCart' }]
]) {
  test('Pending Action拒绝：' + label, () => {
    const service = loadService()
    assert.throws(() => service.validatePendingAction(action), error =>
      error.message === '待确认操作无效，请重新发起。' && error.invalidateAction === true)
  })
}

test('确认动作必定重新读取实时菜单', async () => {
  const service = loadService(); let reads = 0, adds = 0
  await service.executePendingCartAction(validAction(), {
    loadDishes: async () => { reads += 1; return [{ id: 'dish-4', name: '柠檬茶', price: 12, status: 'on_sale' }] },
    addDish: () => { adds += 1; return true }
  })
  assert.equal(reads, 1); assert.equal(adds, 1)
})

for (const [label, dishes, message] of [
  ['菜品不存在', [], '菜品状态已变化，目前无法加入购物车，请重新选择。'],
  ['菜品售罄', [{ id: 'dish-4', name: '柠檬茶', price: 12, status: 'sold_out' }], '菜品状态已变化，目前无法加入购物车，请重新选择。'],
  ['价格变化', [{ id: 'dish-4', name: '柠檬茶', price: 13, status: 'on_sale' }], '菜品价格已变化，请重新确认最新价格。']
]) {
  test('确认失败不修改购物车：' + label, async () => {
    const service = loadService(); let adds = 0
    await assert.rejects(() => service.executePendingCartAction(validAction(), {
      loadDishes: async () => dishes, addDish: () => { adds += 1; return true }
    }), error => error.message === message && error.invalidateAction === true)
    assert.equal(adds, 0)
  })
}

test('实时在售且价格一致时复用Cart addDish并精确增加quantity=2', async () => {
  const service = loadService(); const calls = []
  const result = await service.executePendingCartAction(validAction(), {
    loadDishes: async () => [{ id: 'dish-4', name: '实时柠檬茶', price: 12, status: 'on_sale' }],
    addDish: (dish, quantity) => { calls.push({ dish, quantity }); return true }
  })
  assert.equal(calls.length, 1); assert.equal(calls[0].quantity, 2); assert.equal(calls[0].dish.name, '实时柠檬茶')
  assert.deepEqual(clone(result), { name: '实时柠檬茶', quantity: 2 })
})

test('现有Pinia Cart Store一次addDish确切增加2件', () => {
  const source = fs.readFileSync('src/stores/cart.js', 'utf8')
    .replace(/^import .*$/gm, '').replace('export const useCartStore', 'const useCartStore')
  const context = {
    ref: value => ({ value }),
    computed: getter => ({ get value() { return getter() } }),
    defineStore: (name, setup) => { assert.equal(name, 'cart'); return setup }
  }
  vm.runInNewContext(source + '\nthis.useCartStore=useCartStore', context)
  const cart = context.useCartStore()
  assert.equal(cart.addDish({ id: 'dish-4', name: '柠檬茶', price: 12, status: 'on_sale' }, 2), true)
  assert.equal(cart.items.value.length, 1); assert.equal(cart.items.value[0].quantity, 2); assert.equal(cart.itemCount.value, 2)
})

test('菜单加载失败不修改购物车且不泄露原始错误', async () => {
  const service = loadService(); let adds = 0
  await assert.rejects(() => service.executePendingCartAction(validAction(), {
    loadDishes: async () => { throw new Error('Authorization database secret') }, addDish: () => { adds += 1 }
  }), error => error.message === '暂时无法确认菜品状态，请重试。' && error.invalidateAction === false)
  assert.equal(adds, 0)
})

test('普通Answer展示且无Pending Action时不出现可执行状态', async () => {
  const page = loadPage({ run: async () => validResponse({ answer: '你好，有什么可以帮你？' }) })
  page.query.value = '你好'; await page.submitQuery()
  assert.equal(page.result.value.answer, '你好，有什么可以帮你？'); assert.equal(page.cartPendingAction.value, null)
  assert.equal(page.calls.execute, 0); assert.equal(page.calls.add, 0)
})

test('合法Pending Action进入确认卡状态，确认前不修改购物车', async () => {
  const action = validAction()
  const page = loadPage({ run: async () => validResponse({ pendingAction: action }) })
  page.query.value = '加两杯'; await page.submitQuery()
  assert.deepEqual(clone(page.cartPendingAction.value), action); assert.equal(page.calls.execute, 0); assert.equal(page.calls.add, 0)
})

test('双击确认只执行一次', async () => {
  let resolve
  const page = loadPage({ execute: () => new Promise(done => { resolve = done }) })
  page.cartPendingAction.value = validAction()
  const first = page.confirmAction(); const second = page.confirmAction()
  assert.equal(page.confirming.value, true); assert.equal(page.calls.execute, 1)
  resolve({ name: '柠檬茶', quantity: 2 }); await Promise.all([first, second])
  assert.equal(page.calls.execute, 1); assert.equal(page.confirming.value, false)
})

test('成功后清除提案、显示已加入且不能再次执行', async () => {
  const page = loadPage(); page.cartPendingAction.value = validAction()
  await page.confirmAction(); await page.confirmAction()
  assert.equal(page.cartPendingAction.value, null); assert.equal(page.calls.execute, 1)
  assert.equal(page.actionStatus.value, '已加入购物车：柠檬茶 × 2'); assert.equal(page.actionStatusType.value, 'success')
})

test('取消只清除提案，不调用Agent或购物车', () => {
  const page = loadPage(); page.cartPendingAction.value = validAction(); page.cancelAction()
  assert.equal(page.cartPendingAction.value, null); assert.equal(page.actionStatus.value, '已取消。')
  assert.equal(page.calls.run, 0); assert.equal(page.calls.execute, 0); assert.equal(page.calls.add, 0)
})

test('新Query立即清理旧结果、旧提案和动作状态', async () => {
  let resolve
  const page = loadPage({ run: () => new Promise(done => { resolve = done }) })
  page.result.value = validResponse(); page.cartPendingAction.value = validAction(); page.actionStatus.value = '旧状态'; page.query.value = '新请求'
  const request = page.submitQuery()
  assert.equal(page.result.value, null); assert.equal(page.cartPendingAction.value, null); assert.equal(page.actionStatus.value, '')
  resolve(validResponse({ answer: '新回答' })); await request; assert.equal(page.result.value.answer, '新回答')
})

test('确认失败按安全标记让旧提案失效', async () => {
  const error = new Error('菜品价格已变化，请重新确认最新价格。'); error.invalidateAction = true
  const page = loadPage({ execute: async () => { throw error } }); page.cartPendingAction.value = validAction()
  await page.confirmAction()
  assert.equal(page.cartPendingAction.value, null); assert.equal(page.actionStatusType.value, 'error')
})

test('页面只展示用户字段，不展示内部协议与诊断数据', () => {
  const template = pageText.split('<script setup>')[0]
  for (const expected of ['{{ result.answer }}', '{{ cartPendingAction.name }}', '{{ cartPendingAction.quantity }}',
    '{{ cartPendingAction.unitPrice.toFixed(2) }}', '{{ cartPendingAction.totalPrice.toFixed(2) }}']) assert.ok(template.includes(expected), expected)
  for (const hidden of ['on_sale', 'sold_out', 'toolName', 'tool_call_id', 'trace', 'messages', 'JSON']) {
    assert.ok(!template.includes(hidden), hidden)
  }
  assert.ok(!pageText.includes('console.')); assert.ok(!serviceText.includes('runForAdmin')); assert.ok(!serviceText.includes('traceOnly'))
})

test('Agent独立页面已注册，首页入口存在，TabBar仍为5项', () => {
  const pages = JSON.parse(fs.readFileSync('src/pages.json', 'utf8'))
  assert.equal(pages.pages.find(page => page.path === 'pages/agent/index').style.navigationBarTitleText, '智能点餐 Agent')
  assert.equal(pages.tabBar.list.length, 5); assert.ok(!pages.tabBar.list.some(item => item.pagePath === 'pages/agent/index'))
  assert.ok(fs.readFileSync('src/pages/home/index.vue', 'utf8').includes('/pages/agent/index'))
})

test('现有RAG和AI推荐页面不依赖Agent确认逻辑', () => {
  for (const file of ['src/pages/rag-qa/index.vue', 'src/pages/ai-recommend/index.vue', 'src/services/rag.js', 'src/services/ai.js']) {
    const text = fs.readFileSync(file, 'utf8')
    assert.ok(!text.includes("services/agent"), file); assert.ok(!text.includes('executePendingCartAction'), file)
  }
})

test('前端没有动态执行、云端写Tool或Pending Action持久化', () => {
  const text = serviceText + pageText
  for (const forbidden of ['eval(', 'new Function', 'execute_add_to_cart', 'create_order', 'setStorageSync', 'runForAdmin', 'testTool', 'traceOnly']) {
    assert.ok(!text.includes(forbidden), forbidden)
  }
  assert.ok(text.includes("action.type !== 'add_to_cart'"))
  assert.ok(text.includes('cartStore.addDish(dish, quantity)'))
})
