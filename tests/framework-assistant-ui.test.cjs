const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

const serviceText = fs.readFileSync('src/services/framework-agent.js', 'utf8')
const storeText = fs.readFileSync('src/stores/assistant.js', 'utf8')
const pageText = fs.readFileSync('src/pages/assistant/index.vue', 'utf8')
const fakeSession = {
  threadId: 'conv_fake_session_01',
  conversationToken: 'fake_conversation_capability_token_000000000001'
}
const validAction = {
  type: 'add_to_cart', dishId: 'dish-4', name: '柠檬茶', quantity: 2,
  unitPrice: 12, totalPrice: 24, requiresConfirmation: true
}
const clone = value => JSON.parse(JSON.stringify(value))

function loadService(replies) {
  const requests = []
  const queue = [...replies]
  const context = {
    FRAMEWORK_AGENT_BASE_URL: 'https://framework.example.test',
    validatePendingAction(action) {
      if (action?.type !== 'add_to_cart' || action?.requiresConfirmation !== true ||
          action?.dishId !== 'dish-4' || action?.quantity !== 2 || action?.unitPrice !== 12 ||
          action?.totalPrice !== 24) throw new Error('invalid action')
      return clone(action)
    },
    uni: {
      request(options) {
        requests.push(options)
        const next = queue.shift()
        if (next?.throw) throw new Error('Authorization secret URL token stack')
        if (next?.fail) options.fail({ errMsg: 'Authorization secret URL token' })
        else options.success(next)
      }
    }
  }
  const source = serviceText
    .replace(/^import .*$/gm, '')
    .replaceAll('export async function ', 'async function ')
  vm.runInNewContext(source + `\nthis.api={createConversation,getConversationMessages,runFrameworkAgent}`, context)
  return { ...context.api, requests }
}

function successful(body) {
  return { statusCode: 200, data: { errCode: 0, ...body } }
}

test('create conversation使用独立POST且严格读取服务端session', async () => {
  const service = loadService([successful(fakeSession)])
  assert.deepEqual(clone(await service.createConversation()), fakeSession)
  assert.equal(service.requests.length, 1)
  assert.equal(service.requests[0].method, 'POST')
  assert.equal(service.requests[0].url, 'https://framework.example.test/v1/conversations')
  assert.equal(service.requests[0].header['X-Conversation-Token'], undefined)
})

test('conversation token只进入Header，不进入URL/query/body', async () => {
  const service = loadService([successful({
    query: '多少钱？', answer: '柠檬茶 12 元，目前在售。', completed: true,
    threadId: fakeSession.threadId
  })])
  await service.runFrameworkAgent('  多少钱？ ', fakeSession.threadId, fakeSession.conversationToken)
  const request = service.requests[0]
  assert.equal(request.url, 'https://framework.example.test/v1/agent/run')
  assert.equal(request.header['X-Conversation-Token'], fakeSession.conversationToken)
  assert.deepEqual(clone(request.data), { query: '多少钱？', threadId: fakeSession.threadId })
  assert.ok(!request.url.includes(fakeSession.conversationToken))
  assert.ok(!JSON.stringify(request.data).includes(fakeSession.conversationToken))
})

test('history API恢复并只投影安全user/assistant消息', async () => {
  const service = loadService([successful({
    threadId: fakeSession.threadId,
    createdAt: '2026-09-28T00:00:00Z',
    updatedAt: '2026-09-28T00:01:00Z',
    messages: [
      { role: 'user', content: '有柠檬茶吗？' },
      { role: 'assistant', content: '有，12 元，目前在售。' }
    ]
  })])
  const history = await service.getConversationMessages(
    fakeSession.threadId, fakeSession.conversationToken
  )
  assert.deepEqual(clone(history.messages), [
    { role: 'user', content: '有柠檬茶吗？' },
    { role: 'assistant', content: '有，12 元，目前在售。' }
  ])
  assert.equal(service.requests[0].header['X-Conversation-Token'], fakeSession.conversationToken)
  assert.ok(!JSON.stringify(history).includes(fakeSession.conversationToken))
})

test('access denied映射友好错误且不泄漏远端内容', async () => {
  const service = loadService([{
    statusCode: 403,
    data: { errCode: 'FRAMEWORK_CONVERSATION_ACCESS_DENIED', errMsg: 'DB token hash stack' }
  }])
  await assert.rejects(
    () => service.getConversationMessages(fakeSession.threadId, fakeSession.conversationToken),
    error => error.accessDenied === true && error.message === '当前会话已失效，请新建对话。' &&
      !error.message.includes('hash')
  )
})

test('malformed pendingAction fail closed，不产生可确认结构', async () => {
  const service = loadService([successful({
    query: '加两杯', answer: '准备好了', completed: true, threadId: fakeSession.threadId,
    pendingAction: { ...validAction, totalPrice: 1 }
  })])
  await assert.rejects(
    () => service.runFrameworkAgent('加两杯', fakeSession.threadId, fakeSession.conversationToken),
    error => error.errCode === 'FRAMEWORK_RESPONSE_INVALID'
  )
})

test('网络失败不回显request config、URL或token', async () => {
  const service = loadService([{ fail: true }])
  await assert.rejects(
    () => service.runFrameworkAgent('你好', fakeSession.threadId, fakeSession.conversationToken),
    error => error.message === '网络连接失败，请稍后重试。' &&
      !error.message.includes('token') && !error.message.includes('https://')
  )
})

test('uni.request同步异常同样映射为安全网络错误', async () => {
  const service = loadService([{ throw: true }])
  await assert.rejects(
    () => service.runFrameworkAgent('你好', fakeSession.threadId, fakeSession.conversationToken),
    error => error.errCode === 'FRAMEWORK_NETWORK_FAILED' &&
      error.message === '网络连接失败，请稍后重试。' &&
      !error.message.includes('Authorization') && !error.message.includes('token')
  )
})

function loadStore(options = {}) {
  const storage = { ...(options.storage || {}) }
  const calls = { create: 0, history: 0, run: [], execute: 0, add: 0, removed: 0 }
  const cartStore = {
    addDish() { calls.add += 1; return true }
  }
  const context = {
    ref: value => ({ value }),
    defineStore: (name, setup) => {
      assert.equal(name, 'assistant')
      return () => setup()
    },
    useCartStore: () => cartStore,
    createConversation: async () => {
      calls.create += 1
      return options.createdSession || fakeSession
    },
    getConversationMessages: async (...args) => {
      calls.history += 1
      if (options.historyError) throw options.historyError
      return options.history || { threadId: args[0], messages: [] }
    },
    runFrameworkAgent: async query => {
      calls.run.push(query)
      if (options.runPromise) return options.runPromise
      if (options.runError) throw options.runError
      return options.runResult || {
        query, answer: '助手回答', completed: true, threadId: fakeSession.threadId
      }
    },
    executePendingCartAction: async (action, dependencies) => {
      calls.execute += 1
      if (options.executeError) throw options.executeError
      dependencies.addDish({ id: action.dishId, status: 'on_sale' }, action.quantity)
      return { name: action.name, quantity: action.quantity }
    },
    getDishes: async () => [],
    uni: {
      getStorageSync(key) { return storage[key] || null },
      setStorageSync(key, value) { storage[key] = clone(value) },
      removeStorageSync(key) { calls.removed += 1; delete storage[key] }
    }
  }
  const source = storeText
    .replace(/^import .*$/gm, '')
    .replace('export const ASSISTANT_SESSION_STORAGE_KEY', 'const ASSISTANT_SESSION_STORAGE_KEY')
    .replace('export const useAssistantStore', 'const useAssistantStore')
  vm.runInNewContext(source + '\nthis.useAssistantStore=useAssistantStore;this.key=ASSISTANT_SESSION_STORAGE_KEY', context)
  return { store: context.useAssistantStore(), storage, calls, key: context.key }
}

test('首次进入创建conversation并只持久化threadId/token', async () => {
  const loaded = loadStore()
  await loaded.store.initializeConversation()
  assert.equal(loaded.calls.create, 1)
  assert.deepEqual(loaded.storage[loaded.key], fakeSession)
  assert.equal(loaded.store.messages.value.length, 0)
})

test('页面重进使用本地capability恢复History，不重新创建', async () => {
  const loaded = loadStore({
    storage: { framework_agent_conversation_v1: fakeSession },
    history: { threadId: fakeSession.threadId, messages: [
      { role: 'user', content: '有柠檬茶吗？' },
      { role: 'assistant', content: '有，12 元，目前在售。' }
    ] }
  })
  await loaded.store.initializeConversation()
  assert.equal(loaded.calls.create, 0)
  assert.equal(loaded.calls.history, 1)
  assert.deepEqual(clone(loaded.store.messages.value.map(item => item.role)), ['user', 'assistant'])
  assert.equal(loaded.store.pendingAction.value, null)
})

test('sending在第一个await前阻止重复发送并保留user message', async () => {
  let resolveRun
  const runPromise = new Promise(resolve => { resolveRun = resolve })
  const loaded = loadStore({ runPromise })
  await loaded.store.initializeConversation()
  const first = loaded.store.sendMessage('有柠檬茶吗？')
  const second = await loaded.store.sendMessage('重复消息')
  assert.equal(loaded.store.sending.value, true)
  assert.equal(second, false)
  assert.deepEqual(loaded.calls.run, ['有柠檬茶吗？'])
  assert.equal(loaded.store.messages.value[0].role, 'user')
  resolveRun({ query: '有柠檬茶吗？', answer: '有。', completed: true, threadId: fakeSession.threadId })
  await first
  assert.deepEqual(clone(loaded.store.messages.value.map(item => item.role)), ['user', 'assistant'])
})

test('请求失败不删除user message，并追加安全error bubble', async () => {
  const failure = new Error('Authorization URL token stack')
  const loaded = loadStore({ runError: failure })
  await loaded.store.initializeConversation()
  await loaded.store.sendMessage('有柠檬茶吗？')
  assert.deepEqual(clone(loaded.store.messages.value.map(item => item.role)), ['user', 'assistant'])
  assert.equal(loaded.store.messages.value[0].content, '有柠檬茶吗？')
  assert.equal(loaded.store.messages.value[1].content, '请求失败，请重试。')
  assert.equal(loaded.store.messages.value[1].status, 'error')
  assert.ok(!JSON.stringify(loaded.store.messages.value).includes('Authorization'))
})

test('pendingAction挂到assistant消息并由现有deterministic helper确认', async () => {
  const loaded = loadStore({ runResult: {
    query: '加两杯', answer: '请在界面确认。', completed: true,
    threadId: fakeSession.threadId, pendingAction: validAction
  } })
  await loaded.store.initializeConversation()
  await loaded.store.sendMessage('加两杯')
  const message = loaded.store.messages.value[1]
  assert.equal(message.actionStatus, 'pending')
  assert.deepEqual(clone(message.pendingAction), validAction)
  await loaded.store.confirmPendingAction(message.id)
  assert.equal(loaded.calls.execute, 1)
  assert.equal(loaded.calls.add, 1)
  assert.equal(loaded.calls.run.length, 1)
  assert.equal(message.actionStatus, 'added')
})

test('取消pendingAction只更新UI，无Agent或Cart副作用', async () => {
  const loaded = loadStore({ runResult: {
    query: '加两杯', answer: '请确认。', completed: true,
    threadId: fakeSession.threadId, pendingAction: validAction
  } })
  await loaded.store.initializeConversation()
  await loaded.store.sendMessage('加两杯')
  const message = loaded.store.messages.value[1]
  const runCount = loaded.calls.run.length
  loaded.store.cancelPendingAction(message.id)
  assert.equal(message.actionStatus, 'cancelled')
  assert.equal(loaded.calls.run.length, runCount)
  assert.equal(loaded.calls.execute, 0)
  assert.equal(loaded.calls.add, 0)
})

test('输入文字确认仍作为普通Query发送，不执行Cart helper', async () => {
  const loaded = loadStore()
  await loaded.store.initializeConversation()
  await loaded.store.sendMessage('确认')
  assert.deepEqual(loaded.calls.run, ['确认'])
  assert.equal(loaded.calls.execute, 0)
  assert.equal(loaded.calls.add, 0)
})

test('新对话清空UI和旧storage后创建新capability，不删除服务端旧会话', async () => {
  const next = {
    threadId: 'conv_fake_session_02',
    conversationToken: 'fake_conversation_capability_token_000000000002'
  }
  const loaded = loadStore({
    storage: { framework_agent_conversation_v1: fakeSession },
    createdSession: next
  })
  loaded.store.messages.value = [{ id: 'old', role: 'user', content: '旧消息' }]
  await loaded.store.startNewConversation()
  assert.equal(loaded.calls.removed, 1)
  assert.equal(loaded.calls.create, 1)
  assert.equal(loaded.store.messages.value.length, 0)
  assert.deepEqual(loaded.storage[loaded.key], next)
})

test('History access denied停止恢复且等待用户显式新建', async () => {
  const denied = new Error('当前会话已失效，请新建对话。')
  denied.accessDenied = true
  const loaded = loadStore({
    storage: { framework_agent_conversation_v1: fakeSession }, historyError: denied
  })
  loaded.store.messages.value = [{ id: 'stale', role: 'assistant', content: '旧内容' }]
  await loaded.store.initializeConversation()
  assert.equal(loaded.store.conversationInvalid.value, true)
  assert.equal(loaded.calls.create, 0)
  assert.equal(loaded.store.messages.value.length, 0)
  assert.equal(loaded.store.error.value, '当前会话已失效，请新建对话。')
})

test('聊天页面注册、首页入口存在且TabBar仍为5项', () => {
  const pages = JSON.parse(fs.readFileSync('src/pages.json', 'utf8'))
  assert.equal(pages.pages.find(item => item.path === 'pages/assistant/index').style.navigationBarTitleText, 'AI 点餐助手')
  assert.equal(pages.tabBar.list.length, 5)
  assert.ok(!pages.tabBar.list.some(item => item.pagePath === 'pages/assistant/index'))
  assert.ok(fs.readFileSync('src/pages/home/index.vue', 'utf8').includes('/pages/assistant/index'))
})

test('页面显示安全消息与Action卡，不渲染HTML或内部协议', () => {
  const template = pageText.split('<script setup>')[0]
  for (const expected of [
    '{{ message.content }}', '{{ message.pendingAction.name }}',
    '{{ message.pendingAction.quantity }}', '确认加入购物车', '正在思考…'
  ]) assert.ok(template.includes(expected), expected)
  for (const forbidden of ['v-html', '<rich-text', 'conversationToken', 'knowledgeId', 'similarity', 'reasoning']) {
    assert.ok(!template.includes(forbidden), forbidden)
  }
})

test('前端没有conversation list、Agent执行确认或敏感日志', () => {
  const combined = serviceText + storeText + pageText
  for (const forbidden of [
    'console.log', 'console.error', 'createConfirmedOrder', 'process_payment',
    'execute_pending_action', 'listConversations', 'GET /v1/conversations'
  ]) assert.ok(!combined.includes(forbidden), forbidden)
  assert.ok(combined.includes('executePendingCartAction'))
  assert.ok(combined.includes("X-Conversation-Token"))
})
