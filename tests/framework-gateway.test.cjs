const { test } = require('node:test')
const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')
const shared = require('../uniCloud-aliyun/cloudfunctions/common/menu-read-domain')
const { createMenuDb } = require('./helpers/menu-db.cjs')
const {
  createFrameworkGateway,
  createCanonicalSigningString,
  CANONICAL_METHOD,
  CANONICAL_PATH,
  SIGNATURE_VERSION,
  TIMESTAMP_WINDOW_SECONDS,
  MAX_BODY_BYTES
} = require('../uniCloud-aliyun/cloudfunctions/framework-gateway/gateway')

const TEST_SECRET = 'test-only-framework-secret-at-least-32-chars'
const NOW = 2000000000
const NONCE = 'test_nonce_1234567890'

function bindSharedDomain(db) {
  return {
    searchMenu: args => shared.searchMenu(args, { db }),
    listAvailableDrinks: args => shared.listAvailableDrinks(args, { db }),
    getDishDetail: args => shared.getDishDetail(args, { db })
  }
}

function signBody(body, { secret = TEST_SECRET, timestamp = String(NOW), nonce = NONCE,
  cryptoModule = crypto } = {}) {
  const bodySha256 = cryptoModule.createHash('sha256').update(Buffer.from(body)).digest('hex')
  const canonical = createCanonicalSigningString({ timestamp, nonce, bodySha256 })
  return cryptoModule.createHmac('sha256', secret).update(canonical, 'utf8').digest('hex')
}

function eventFor(payload, options = {}) {
  const body = options.rawBody || JSON.stringify(payload)
  const timestamp = options.timestamp ?? String(NOW)
  const nonce = options.nonce ?? NONCE
  const signature = options.signature || signBody(body, { secret: options.secret, timestamp, nonce })
  const headers = {
    'x-framework-signature-version': options.version || SIGNATURE_VERSION,
    'x-framework-timestamp': timestamp,
    'x-framework-nonce': nonce,
    'x-framework-signature': signature,
    ...options.headers
  }
  return { path: options.path ?? '/', httpMethod: options.method || 'POST', headers,
    isBase64Encoded: false, body }
}

function setup(options = {}) {
  const fixture = createMenuDb(options.dbOptions)
  const domain = options.domain || bindSharedDomain(fixture.db)
  const handle = createFrameworkGateway({
    domain,
    getSecret: options.getSecret || (() => TEST_SECRET),
    now: options.now || (() => NOW),
    cryptoModule: options.cryptoModule || crypto
  })
  return { handle, fixture }
}

test('canonical signing v1格式固定且不依赖JSON键迭代', () => {
  const hash = 'a'.repeat(64)
  assert.equal(createCanonicalSigningString({ timestamp: '1700000000', nonce: NONCE, bodySha256: hash }),
    `v1\nPOST\n/framework-gateway\n1700000000\n${NONCE}\n${hash}`)
  assert.equal(CANONICAL_METHOD, 'POST')
  assert.equal(CANONICAL_PATH, '/framework-gateway')
})

test('valid v1 signature接受并执行Shared search_menu', async () => {
  const { handle } = setup()
  const result = await handle(eventFor({ operation: 'search_menu', arguments: { query: ' 可乐 ' } }))
  assert.deepEqual(result, { errCode: 0, operation: 'search_menu', data: {
    tool: 'search_menu', query: '可乐', count: 0, items: []
  } })
})

test('uniCloud base64 body按解码后的原始bytes验签', async () => {
  const body = JSON.stringify({ operation: 'list_available_drinks', arguments: {} })
  const event = eventFor({}, { rawBody: body })
  event.body = Buffer.from(body).toString('base64')
  event.isBase64Encoded = true
  const result = await setup().handle(event)
  assert.equal(result.errCode, 0)
  assert.equal(result.data.count, 1)
})

for (const header of ['x-framework-signature-version', 'x-framework-signature',
  'x-framework-timestamp', 'x-framework-nonce']) {
  test(`missing ${header}拒绝`, async () => {
    const event = eventFor({ operation: 'list_available_drinks', arguments: {} })
    delete event.headers[header]
    assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_MISSING')
  })
}

test('wrong signature拒绝', async () => {
  const event = eventFor({ operation: 'list_available_drinks', arguments: {} }, { signature: '0'.repeat(64) })
  assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_INVALID')
})

for (const timestamp of ['bad', '123.5', '-1']) {
  test(`malformed timestamp ${timestamp}拒绝`, async () => {
    const event = eventFor({ operation: 'list_available_drinks', arguments: {} }, { timestamp })
    assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_INVALID')
  })
}

test('expired timestamp拒绝', async () => {
  const timestamp = String(NOW - TIMESTAMP_WINDOW_SECONDS - 1)
  const event = eventFor({ operation: 'list_available_drinks', arguments: {} }, { timestamp })
  assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_EXPIRED')
})

test('future timestamp超出窗口拒绝', async () => {
  const timestamp = String(NOW + TIMESTAMP_WINDOW_SECONDS + 1)
  const event = eventFor({ operation: 'list_available_drinks', arguments: {} }, { timestamp })
  assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_EXPIRED')
})

for (const nonce of ['', 'short', 'bad nonce!', 'a'.repeat(65)]) {
  test(`malformed nonce ${JSON.stringify(nonce).slice(0, 20)}拒绝`, async () => {
    const event = eventFor({ operation: 'list_available_drinks', arguments: {} }, { nonce })
    assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_INVALID')
  })
}

test('unsupported signature version拒绝', async () => {
  const event = eventFor({ operation: 'list_available_drinks', arguments: {} }, { version: 'v2' })
  assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_VERSION_UNSUPPORTED')
})

test('missing server secret fail closed', async () => {
  const { handle } = setup({ getSecret: () => '' })
  const result = await handle(eventFor({ operation: 'list_available_drinks', arguments: {} }))
  assert.deepEqual(result, { errCode: 'FRAMEWORK_GATEWAY_CONFIG_MISSING', message: 'Gateway认证配置缺失' })
})

test('body tampering拒绝', async () => {
  const original = JSON.stringify({ operation: 'search_menu', arguments: { query: '可乐' } })
  const event = eventFor({}, { rawBody: original })
  event.body = JSON.stringify({ operation: 'search_menu', arguments: { query: '柠檬茶' } })
  assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_INVALID')
})

test('operation tampering拒绝', async () => {
  const original = JSON.stringify({ operation: 'search_menu', arguments: { query: '可乐' } })
  const event = eventFor({}, { rawBody: original })
  event.body = JSON.stringify({ operation: 'createOrder', arguments: {} })
  assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_INVALID')
})

test('arguments tampering拒绝', async () => {
  const original = JSON.stringify({ operation: 'search_menu', arguments: { query: '可乐' } })
  const event = eventFor({}, { rawBody: original })
  event.body = JSON.stringify({ operation: 'search_menu', arguments: { query: '牛肉' } })
  assert.equal((await setup().handle(event)).errCode, 'FRAMEWORK_GATEWAY_AUTH_INVALID')
})

test('签名验证真实使用constant-time compare', async () => {
  let comparisons = 0
  const cryptoModule = {
    createHash: crypto.createHash,
    createHmac: crypto.createHmac,
    timingSafeEqual(left, right) { comparisons++; return crypto.timingSafeEqual(left, right) }
  }
  const { handle } = setup({ cryptoModule })
  const result = await handle(eventFor({ operation: 'list_available_drinks', arguments: {} }))
  assert.equal(result.errCode, 0)
  assert.equal(comparisons, 1)
})

test('认证错误不返回secret、signature或内部信息', async () => {
  const result = await setup().handle(eventFor({ operation: 'list_available_drinks', arguments: {} }, {
    signature: '0'.repeat(64)
  }))
  const text = JSON.stringify(result)
  assert.ok(!text.includes(TEST_SECRET))
  assert.ok(!text.includes('0000000000'))
  assert.deepEqual(Object.keys(result).sort(), ['errCode', 'message'])
})

for (const operation of ['prepare_add_to_cart', 'createOrder', 'createConfirmedOrder', 'unknown',
  '__proto__', 'constructor', 'toString']) {
  test(`operation allowlist拒绝 ${operation}`, async () => {
    const result = await setup().handle(eventFor({ operation, arguments: {} }))
    assert.equal(result.errCode, 'FRAMEWORK_GATEWAY_OPERATION_NOT_ALLOWED')
  })
}

test('list_available_drinks允许并返回真实Shared结果', async () => {
  const result = await setup().handle(eventFor({ operation: 'list_available_drinks', arguments: {} }))
  assert.equal(result.errCode, 0)
  assert.equal(result.operation, 'list_available_drinks')
  assert.deepEqual(result.data.items.map(item => item.dishId), ['dish-4'])
})

test('get_dish_detail允许并返回真实Shared结果', async () => {
  const result = await setup().handle(eventFor({ operation: 'get_dish_detail', arguments: { dishId: ' dish-4 ' } }))
  assert.equal(result.errCode, 0)
  assert.equal(result.data.found, true)
  assert.equal(result.data.item.name, '柠檬茶')
})

for (const args of [{ query: '' }, { query: ' ' }, { query: '中'.repeat(201) }, { query: 1 },
  {}, { query: '可乐', filters: {} }]) {
  test(`search_menu参数拒绝 ${JSON.stringify(args).slice(0, 30)}`, async () => {
    const result = await setup().handle(eventFor({ operation: 'search_menu', arguments: args }))
    assert.equal(result.errCode, 'FRAMEWORK_GATEWAY_REQUEST_INVALID')
  })
}

test('search_menu允许200个Unicode字符', async () => {
  const query = '🍋'.repeat(200)
  const result = await setup().handle(eventFor({ operation: 'search_menu', arguments: { query } }))
  assert.equal(result.errCode, 0)
  assert.equal(result.data.query, query)
})

test('list_available_drinks拒绝额外参数', async () => {
  const result = await setup().handle(eventFor({ operation: 'list_available_drinks', arguments: { status: 'on_sale' } }))
  assert.equal(result.errCode, 'FRAMEWORK_GATEWAY_REQUEST_INVALID')
})

for (const args of [{ dishId: '' }, { dishId: ' ' }, { dishId: 4 }, {},
  { dishId: 'dish-4', price: 1 }]) {
  test(`get_dish_detail参数拒绝 ${JSON.stringify(args)}`, async () => {
    const result = await setup().handle(eventFor({ operation: 'get_dish_detail', arguments: args }))
    assert.equal(result.errCode, 'FRAMEWORK_GATEWAY_REQUEST_INVALID')
  })
}

test('顶层额外字段、错误method/path和过大body拒绝', async () => {
  assert.equal((await setup().handle(eventFor({ operation: 'list_available_drinks', arguments: {}, model: 'x' }))).errCode,
    'FRAMEWORK_GATEWAY_REQUEST_INVALID')
  assert.equal((await setup().handle(eventFor({ operation: 'list_available_drinks', arguments: {} }, { method: 'GET' }))).errCode,
    'FRAMEWORK_GATEWAY_REQUEST_INVALID')
  assert.equal((await setup().handle(eventFor({ operation: 'list_available_drinks', arguments: {} }, { path: '/admin' }))).errCode,
    'FRAMEWORK_GATEWAY_REQUEST_INVALID')
  const body = JSON.stringify({ operation: 'search_menu', arguments: { query: 'a'.repeat(MAX_BODY_BYTES) } })
  assert.equal((await setup().handle(eventFor({}, { rawBody: body }))).errCode,
    'FRAMEWORK_GATEWAY_REQUEST_INVALID')
})

test('DB/internal异常统一为安全Tool错误', async () => {
  const result = await setup({ dbOptions: { fails: true } }).handle(
    eventFor({ operation: 'search_menu', arguments: { query: '鸡' } }))
  assert.deepEqual(result, { errCode: 'FRAMEWORK_GATEWAY_TOOL_FAILED', message: '菜单查询未完成' })
  assert.ok(!JSON.stringify(result).includes('database'))
})

test('Gateway源码没有DB查询、动态执行、写操作或管理接口复用', () => {
  const files = ['index.js', 'gateway.js', 'menu-domain.js']
  const text = files.map(file => fs.readFileSync(`uniCloud-aliyun/cloudfunctions/framework-gateway/${file}`, 'utf8')).join('\n')
  for (const pattern of [/uniCloud\.database/,/collection\(/,/sharedDomain\[operation\]/,
    /\badd\s*\(\s*\{/,/\bupdate\s*\(\s*\{/,/\bremove\s*\(/,/importObject/,/agent-admin/,/agent-tool-admin/]) {
    assert.ok(!pattern.test(text), String(pattern))
  }
})

test('云函数入口按真实context.SOURCE识别HTTP且缺少认证进入AUTH_MISSING', async () => {
  const gatewayEntry = require('../uniCloud-aliyun/cloudfunctions/framework-gateway/index.js')
  const event = eventFor({ operation: 'list_available_drinks', arguments: {} })
  const before = process.env.FRAMEWORK_GATEWAY_SECRET
  process.env.FRAMEWORK_GATEWAY_SECRET = TEST_SECRET
  try {
    const unsignedEvent = { ...event, headers: { 'content-type': 'application/json' } }
    assert.equal((await gatewayEntry.main(unsignedEvent, { SOURCE: 'http' })).errCode,
      'FRAMEWORK_GATEWAY_AUTH_MISSING')
    for (const context of [{ SOURCE: 'client' }, { SOURCE: 'function' }, { SOURCE: 'server' },
      {}, { source: 'http' }]) {
      assert.equal((await gatewayEntry.main(event, context)).errCode,
        'FRAMEWORK_GATEWAY_REQUEST_INVALID')
    }
  } finally {
    if (before === undefined) delete process.env.FRAMEWORK_GATEWAY_SECRET
    else process.env.FRAMEWORK_GATEWAY_SECRET = before
  }
})

test('云函数HTTP入口缺少服务器secret时fail closed', async () => {
  const gatewayEntry = require('../uniCloud-aliyun/cloudfunctions/framework-gateway/index.js')
  const event = eventFor({ operation: 'list_available_drinks', arguments: {} })
  const before = process.env.FRAMEWORK_GATEWAY_SECRET
  delete process.env.FRAMEWORK_GATEWAY_SECRET
  try {
    assert.equal((await gatewayEntry.main(event, { SOURCE: 'http' })).errCode,
      'FRAMEWORK_GATEWAY_CONFIG_MISSING')
  } finally {
    if (before === undefined) delete process.env.FRAMEWORK_GATEWAY_SECRET
    else process.env.FRAMEWORK_GATEWAY_SECRET = before
  }
})

test('云函数正式入口经HMAC后调用Shared Domain而非复制查询', async () => {
  const gatewayEntry = require('../uniCloud-aliyun/cloudfunctions/framework-gateway/index.js')
  const fixture = createMenuDb()
  const beforeSecret = process.env.FRAMEWORK_GATEWAY_SECRET
  const beforeUniCloud = global.uniCloud
  process.env.FRAMEWORK_GATEWAY_SECRET = TEST_SECRET
  global.uniCloud = { database: () => fixture.db }
  try {
    const timestamp = String(Math.floor(Date.now() / 1000))
    const result = await gatewayEntry.main(
      eventFor({ operation: 'get_dish_detail', arguments: { dishId: 'dish-4' } }, { timestamp }),
      { SOURCE: 'http' }
    )
    assert.equal(result.errCode, 0)
    assert.equal(result.data.item.name, '柠檬茶')
    assert.deepEqual(fixture.calls.map(call => call.name), ['dishes'])
  } finally {
    if (beforeSecret === undefined) delete process.env.FRAMEWORK_GATEWAY_SECRET
    else process.env.FRAMEWORK_GATEWAY_SECRET = beforeSecret
    if (beforeUniCloud === undefined) delete global.uniCloud
    else global.uniCloud = beforeUniCloud
  }
})
