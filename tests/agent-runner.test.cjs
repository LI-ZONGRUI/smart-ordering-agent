const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const dishesSource = require('../uniCloud-aliyun/database/dishes.init_data.json')
const categoriesSource = require('../uniCloud-aliyun/database/categories.init_data.json')
const { getToolDefinitions } = require('../uniCloud-aliyun/cloudfunctions/agent/tools/registry')
const { readAgentConfig, parseModelResponse, callAgentModel } = require('../uniCloud-aliyun/cloudfunctions/agent/model-client')
const { MAX_AGENT_STEPS, MAX_TOOL_CALLS, SYSTEM_PROMPT, runAgent } = require('../uniCloud-aliyun/cloudfunctions/agent/runner')

const env = { DASHSCOPE_API_KEY: 'local-test-placeholder', LLM_BASE_URL: 'https://example.invalid/compatible-mode/v1', AGENT_LLM_MODEL: 'model-placeholder' }
const toolCall = (id, name, args) => ({
  type: 'tool_calls',
  message: { role: 'assistant', content: null, tool_calls: [{ id, type: 'function', function: { name, arguments: args } }] }
})
const final = content => ({ type: 'final', content })

function setupDb(options = {}) {
  const calls = []
  const dishes = structuredClone(options.dishes || dishesSource)
  const categories = structuredClone(options.categories || categoriesSource)
  const db = { collection(name) {
    assert.ok(['dishes', 'categories'].includes(name))
    let condition = {}, offset = 0, size = 100
    return {
      where(value) { condition = value; return this },
      field() { return this },
      orderBy(key, direction) { assert.equal(key, '_id'); assert.equal(direction, 'asc'); return this },
      skip(value) { offset = value; return this },
      limit(value) { size = value; return this },
      async get() {
        calls.push({ name, condition, offset, size })
        const rows = name === 'dishes' ? dishes : categories
        return { data: rows.filter(row => Object.entries(condition).every(([key, value]) => row[key] === value))
          .sort((a, b) => a._id.localeCompare(b._id)).slice(offset, offset + size) }
      },
      add() { assert.fail('write forbidden') },
      update() { assert.fail('write forbidden') },
      remove() { assert.fail('write forbidden') }
    }
  } }
  return { db, calls, dishes }
}

function scripted(decisions, snapshots = []) {
  let index = 0
  const client = async input => {
    snapshots.push(structuredClone({ messages: input.messages, tools: input.tools }))
    assert.ok(index < decisions.length, 'unexpected model request')
    const value = decisions[index]
    index += 1
    if (value instanceof Error) throw value
    return value
  }
  client.count = () => index
  return client
}

function options(modelClient, db = setupDb().db, extra = {}) {
  return { db, httpclient: {}, env, modelClient, ...extra }
}

test('Agent配置只读取三个独立环境变量并构造chat/completions地址', () => {
  const value = readAgentConfig(env)
  assert.equal(value.model, 'model-placeholder')
  assert.equal(value.endpoint, 'https://example.invalid/compatible-mode/v1/chat/completions')
})

for (const invalid of [{}, { ...env, DASHSCOPE_API_KEY: '' }, { ...env, LLM_BASE_URL: 'http://example.invalid' }, { ...env, AGENT_LLM_MODEL: '' }]) {
  test('Agent配置缺失或不安全时拒绝', () => assert.throws(() => readAgentConfig(invalid), { code: 'AGENT_CONFIG_MISSING' }))
}

test('Model Client使用原生tools、tool_choice=auto并关闭thinking', async () => {
  let request
  const httpclient = { async request(url, value) {
    request = { url, value }
    return { status: 200, data: JSON.stringify({ choices: [{ message: { role: 'assistant', content: '你好' } }] }) }
  } }
  const tools = getToolDefinitions()
  const result = await callAgentModel({ httpclient, config: readAgentConfig(env), messages: [{ role: 'user', content: '你好' }], tools })
  assert.deepEqual(result, final('你好'))
  assert.equal(request.value.data.tool_choice, 'auto')
  assert.equal(request.value.data.enable_thinking, false)
  assert.deepEqual(request.value.data.tools, tools)
  assert.deepEqual(tools.map(item => item.function.name), ['search_menu', 'list_available_drinks', 'get_dish_detail'])
  assert.equal(request.value.followRedirect, false)
})

test('Model Client保留协议需要的assistant tool_calls并丢弃reasoning_content', () => {
  const response = { status: 200, data: JSON.stringify({ choices: [{ message: {
    role: 'assistant', content: '', reasoning_content: 'hidden', tool_calls: [{ id: 'call-1', type: 'function',
      function: { name: 'search_menu', arguments: '{"query":"可乐"}' }, extra: 'ignore' }]
  } }] }) }
  const result = parseModelResponse(response)
  const expected = toolCall('call-1', 'search_menu', '{"query":"可乐"}')
  expected.message.content = ''
  assert.deepEqual(result, expected)
  assert.ok(!JSON.stringify(result).includes('hidden'))
})

for (const response of [null, {}, { status: 200, data: 'not-json' }, { status: 200, data: '{}' },
  { status: 200, data: JSON.stringify({ choices: [{ message: { role: 'assistant', content: '', tool_calls: 'bad' } }] }) },
  { status: 200, data: JSON.stringify({ choices: [{ message: { role: 'assistant', content: '', tool_calls: [{ id: '', type: 'function', function: { name: 'x', arguments: '{}' } }] } }] }) }]) {
  test('异常Model响应被安全拒绝', () => assert.throws(() => parseModelResponse(response), { code: 'AGENT_MODEL_RESPONSE_INVALID' }))
}

test('非2xx Model响应映射为安全请求错误', () => {
  assert.throws(() => parseModelResponse({ status: 401, data: '{"error":{}}' }), { code: 'AGENT_MODEL_REQUEST_FAILED' })
})

test('Case A：可乐无匹配后再查饮料，完整两步Agent Loop', async () => {
  const snapshots = []
  const model = scripted([
    toolCall('call-search', 'search_menu', '{"query":"可乐"}'),
    toolCall('call-drinks', 'list_available_drinks', '{}'),
    final('当前菜单没有查到可乐，不过目前有柠檬茶可以选择，价格是 12 元。')
  ], snapshots)
  const result = await runAgent('  有可乐吗？没有的话推荐点别的喝的。 ', options(model, setupDb().db, { includeTrace: true }))
  assert.equal(result.errCode, 0)
  assert.equal(result.query, '有可乐吗？没有的话推荐点别的喝的。')
  assert.equal(result.trace.filter(item => item.type === 'tool_call').length, 2)
  assert.deepEqual(result.trace.filter(item => item.type === 'tool_call').map(item => item.toolName), ['search_menu', 'list_available_drinks'])
  const secondMessages = snapshots[1].messages
  assert.deepEqual(secondMessages.at(-2).tool_calls[0].id, 'call-search')
  assert.equal(secondMessages.at(-1).role, 'tool')
  assert.equal(secondMessages.at(-1).tool_call_id, 'call-search')
  assert.deepEqual(JSON.parse(secondMessages.at(-1).content), { errCode: 0, tool: 'search_menu', query: '可乐', count: 0, items: [] })
  assert.equal(JSON.parse(snapshots[2].messages.at(-1).content).items[0].name, '柠檬茶')
})

test('Case B：商品存在时完成回答，不调用饮料列表', async () => {
  const model = scripted([toolCall('one', 'search_menu', '{"query":"柠檬茶"}'), final('当前有柠檬茶，价格是 12 元。')])
  const result = await runAgent('有柠檬茶吗？', options(model, setupDb().db, { includeTrace: true }))
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.trace.filter(item => item.type === 'tool_call').map(item => item.toolName), ['search_menu'])
})

test('Case C：sold_out真实Tool Context进入下一次模型请求', async () => {
  const snapshots = []
  const model = scripted([toolCall('acid', 'search_menu', '{"query":"酸梅汤"}'), final('菜单中有酸梅汤，但当前售罄。')], snapshots)
  const result = await runAgent('有酸梅汤吗？', options(model, setupDb().db))
  assert.equal(result.errCode, 0)
  const context = JSON.parse(snapshots[1].messages.at(-1).content)
  assert.equal(context.items[0].name, '酸梅汤')
  assert.equal(context.items[0].status, 'sold_out')
  assert.match(SYSTEM_PROMPT, /存在但当前售罄/)
})

test('Case D：search_menu可与get_dish_detail串联', async () => {
  const snapshots = []
  const model = scripted([toolCall('find', 'search_menu', '{"query":"柠檬茶"}'),
    toolCall('detail', 'get_dish_detail', '{"dishId":"dish-4"}'), final('柠檬茶的配料是红茶和柠檬。')], snapshots)
  const result = await runAgent('柠檬茶有什么配料？', options(model, setupDb().db, { includeTrace: true }))
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.trace.filter(item => item.type === 'tool_call').map(item => item.toolName), ['search_menu', 'get_dish_detail'])
  assert.deepEqual(JSON.parse(snapshots[2].messages.at(-1).content).item.ingredients, ['红茶', '柠檬'])
})

test('Case E：简单问候可以不调用工具', async () => {
  const state = setupDb()
  const result = await runAgent('你好', options(scripted([final('你好，我可以帮你查询菜单。')]), state.db, { includeTrace: true }))
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.trace, [])
  assert.equal(state.calls.length, 0)
})

test('Case F：未知Tool继续由Executor allowlist拒绝', async () => {
  const result = await runAgent('危险请求', options(scripted([toolCall('bad', 'delete_database', '{}')]), setupDb().db))
  assert.deepEqual(result, { errCode: 'AGENT_TOOL_NOT_FOUND', errMsg: '工具未注册' })
})

test('Case G：非法arguments JSON安全失败', async () => {
  const result = await runAgent('查菜单', options(scripted([toolCall('bad-json', 'search_menu', '{query:')]), setupDb().db))
  assert.equal(result.errCode, 'AGENT_TOOL_ARGUMENT_PARSE_FAILED')
})

test('Case H：合法JSON仍必须经过Executor Schema校验', async () => {
  const args = JSON.stringify({ query: '', collection: 'orders' })
  const result = await runAgent('查菜单', options(scripted([toolCall('bad-schema', 'search_menu', args)]), setupDb().db))
  assert.deepEqual(result, { errCode: 'AGENT_TOOL_ARGUMENT_INVALID', errMsg: '工具参数格式不正确' })
})

test('Case I：持续调用工具在最大模型轮次停止', async () => {
  const decisions = Array.from({ length: MAX_AGENT_STEPS }, (_, index) => toolCall(`loop-${index}`, 'search_menu', '{"query":"可乐"}'))
  const model = scripted(decisions)
  const result = await runAgent('循环', options(model, setupDb().db))
  assert.equal(result.errCode, 'AGENT_MAX_STEPS_EXCEEDED')
  assert.equal(model.count(), MAX_AGENT_STEPS)
})

test('单轮Tool Calls超过总上限时不执行工具', async () => {
  const calls = Array.from({ length: MAX_TOOL_CALLS + 1 }, (_, index) => ({ id: `many-${index}`, type: 'function', function: { name: 'search_menu', arguments: '{"query":"可乐"}' } }))
  const state = setupDb()
  const result = await runAgent('太多调用', options(scripted([{ type: 'tool_calls', message: { role: 'assistant', content: null, tool_calls: calls } }]), state.db))
  assert.equal(result.errCode, 'AGENT_MAX_TOOL_CALLS_EXCEEDED')
  assert.equal(state.calls.length, 0)
})

test('同一轮多个tool_calls按协议逐个执行并关联各自ID', async () => {
  const calls = [
    { id: 'multi-1', type: 'function', function: { name: 'search_menu', arguments: '{"query":"柠檬茶"}' } },
    { id: 'multi-2', type: 'function', function: { name: 'list_available_drinks', arguments: '{}' } }
  ]
  const snapshots = []
  const result = await runAgent('查饮料', options(scripted([{ type: 'tool_calls', message: { role: 'assistant', content: null, tool_calls: calls } }, final('当前有柠檬茶。')], snapshots), setupDb().db, { includeTrace: true }))
  assert.equal(result.errCode, 0)
  assert.deepEqual(snapshots[1].messages.slice(-2).map(item => item.tool_call_id), ['multi-1', 'multi-2'])
})

test('Case J：模型API failure映射成安全Agent错误', async () => {
  const error = new Error('internal URL Authorization secret')
  error.code = 'AGENT_MODEL_REQUEST_FAILED'
  const result = await runAgent('你好', options(scripted([error])))
  assert.deepEqual(result, { errCode: 'AGENT_MODEL_REQUEST_FAILED', errMsg: 'Agent 模型请求失败，请检查网络、模型权限和配额后重试' })
  assert.ok(!JSON.stringify(result).includes('internal URL'))
})

for (const query of [null, 1, '', '   ', '中'.repeat(201)]) {
  test('无效query不调用模型：' + String(query).slice(0, 12), async () => {
    const model = scripted([])
    assert.equal((await runAgent(query, options(model))).errCode, 'AGENT_QUERY_INVALID')
    assert.equal(model.count(), 0)
  })
}

test('200个Unicode字符合法且正式结果不含内部字段', async () => {
  const result = await runAgent('🍋'.repeat(200), options(scripted([final('收到。')])))
  assert.deepEqual(result, { errCode: 0, query: '🍋'.repeat(200), answer: '收到。', completed: true })
  for (const key of ['messages', 'trace', 'rawResponse', 'reasoning', 'systemPrompt']) assert.equal(Object.hasOwn(result, key), false)
})

test('System Prompt约束菜单事实、空结果、售罄和只读边界', () => {
  for (const text of ['真实菜单', '工具结果', 'count=0', 'sold_out', '价格', '配料', '只读菜单查询能力']) assert.ok(SYSTEM_PROMPT.includes(text), text)
  assert.ok(!SYSTEM_PROMPT.includes('delete_database'))
})

test('System Prompt要求最终回答隐藏内部字段并转为自然状态表达', () => {
  for (const text of ['不得主动暴露内部实现字段', 'dishId', 'on_sale', 'sold_out', 'Tool名称', 'tool_call_id', 'collection名称',
    '在售', '可以购买', '已售罄', '暂时无法购买']) assert.ok(SYSTEM_PROMPT.includes(text), text)
  // Mock只证明最终回答路径没有改变；真实模型是否遵循Prompt仍需远程复验。
  assert.match(SYSTEM_PROMPT, /不要显示dishId/)
})

test('Case L：管理Trace仅含清洗后的调用与结果', async () => {
  const result = await runAgent('有可乐吗？', options(scripted([toolCall('safe', 'search_menu', '{"query":"可乐"}'), final('当前菜单没有查到可乐。')]), setupDb().db, { includeTrace: true }))
  assert.equal(result.errCode, 0)
  assert.deepEqual(result.trace.map(item => item.type), ['tool_call', 'tool_result'])
  const serialized = JSON.stringify(result.trace)
  for (const forbidden of ['local-test-placeholder', 'Authorization', SYSTEM_PROMPT, 'reasoning_content', 'rawResponse']) assert.ok(!serialized.includes(forbidden))
})

function loadAgentRunAdmin(result) {
  const calls = []
  const sandbox = { exports: {}, uniCloud: { importObject(name) {
    assert.equal(name, 'agent')
    return { async runForAdmin(...args) { calls.push(args); return structuredClone(result) } }
  } } }
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent-run-admin/index.js', 'utf8'), sandbox)
  return { main: sandbox.exports.main, calls }
}

test('agent-run-admin只允许server并仅向同一个runForAdmin转发query', async () => {
  const admin = loadAgentRunAdmin({ errCode: 0, query: '有可乐吗？', answer: '完整回答', completed: true, trace: [] })
  for (const SOURCE of ['client', 'http', undefined]) assert.equal((await admin.main({ query: '你好' }, { SOURCE })).errCode, 'AGENT_TOOL_FORBIDDEN')
  await admin.main({ query: '有可乐吗？', traceOnly: true, apiKey: 'ignored', model: 'ignored' }, { SOURCE: 'server' })
  assert.deepEqual(admin.calls, [['有可乐吗？']])
})

test('traceOnly压缩真实sanitized trace且不返回完整answer', async () => {
  const sourceResult = {
    errCode: 0, query: '有可乐吗？没有的话推荐点别的喝的。', answer: '一段可能很长的完整回答', completed: true,
    trace: [
      { step: 1, type: 'tool_call', toolName: 'search_menu', arguments: { query: '可乐' } },
      { step: 1, type: 'tool_result', toolName: 'search_menu', result: { errCode: 0, tool: 'search_menu', query: '可乐', count: 0, items: [], description: 'drop' } },
      { step: 2, type: 'tool_call', toolName: 'list_available_drinks', arguments: {} },
      { step: 2, type: 'tool_result', toolName: 'list_available_drinks', result: { errCode: 0, count: 1, items: [
        { dishId: 'dish-4', name: '柠檬茶', price: 12, status: 'on_sale', description: 'drop', ingredients: ['drop'] }
      ] } },
      { step: 3, type: 'tool_result', toolName: 'get_dish_detail', result: { found: true, item: {
        dishId: 'dish-4', name: '柠檬茶', price: 12, status: 'on_sale', description: 'drop', ingredients: ['drop']
      } } }
    ],
    messages: ['drop'], systemPrompt: 'drop', rawResponse: 'drop', reasoning_content: 'drop', Authorization: 'drop', apiKey: 'drop'
  }
  const admin = loadAgentRunAdmin(sourceResult)
  const result = JSON.parse(JSON.stringify(await admin.main({ query: sourceResult.query, traceOnly: true }, { SOURCE: 'server' })))
  assert.equal(admin.calls.length, 1)
  assert.equal(Object.hasOwn(result, 'answer'), false)
  assert.deepEqual(result, {
    errCode: 0, query: sourceResult.query, completed: true,
    trace: [
      { step: 1, type: 'tool_call', toolName: 'search_menu', arguments: { query: '可乐' } },
      { step: 1, type: 'tool_result', toolName: 'search_menu', summary: { count: 0, items: [] } },
      { step: 2, type: 'tool_call', toolName: 'list_available_drinks', arguments: {} },
      { step: 2, type: 'tool_result', toolName: 'list_available_drinks', summary: { count: 1,
        items: [{ dishId: 'dish-4', name: '柠檬茶', status: 'on_sale', price: 12 }] } },
      { step: 3, type: 'tool_result', toolName: 'get_dish_detail', summary: { found: true,
        item: { dishId: 'dish-4', name: '柠檬茶', status: 'on_sale', price: 12 } } }
    ]
  })
  const serialized = JSON.stringify(result)
  for (const forbidden of ['完整回答', 'description', 'ingredients', 'messages', 'systemPrompt', 'rawResponse', 'reasoning', 'Authorization', 'apiKey']) {
    assert.equal(serialized.includes(forbidden), false, forbidden)
  }
})

test('traceOnly未提供或为false时保持原有完整返回', async () => {
  const sourceResult = { errCode: 0, query: '你好', answer: '你好', completed: true, trace: [{ step: 1 }] }
  const admin = loadAgentRunAdmin(sourceResult)
  assert.deepEqual(JSON.parse(JSON.stringify(await admin.main({ query: '你好' }, { SOURCE: 'server' }))), sourceResult)
  assert.deepEqual(JSON.parse(JSON.stringify(await admin.main({ query: '你好', traceOnly: false }, { SOURCE: 'server' }))), sourceResult)
  assert.deepEqual(admin.calls, [['你好'], ['你好']])
})

test('Agent Runner与Model Client不包含数据库写调用、动态代码或模型日志', () => {
  const text = ['runner.js', 'model-client.js'].map(file => fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent/' + file, 'utf8')).join('\n')
  for (const pattern of [/collection\([^)]*\)\.add\(/, /collection\([^)]*\)\.update\(/, /collection\([^)]*\)\.remove\(/, /eval\(/, /new Function/, /console\./]) assert.ok(!pattern.test(text), String(pattern))
})
