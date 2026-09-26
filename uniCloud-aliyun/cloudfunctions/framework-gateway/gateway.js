const crypto = require('node:crypto')

const SIGNATURE_VERSION = 'v1'
const CANONICAL_METHOD = 'POST'
const CANONICAL_PATH = '/framework-gateway'
const TIMESTAMP_WINDOW_SECONDS = 300
const MAX_BODY_BYTES = 4096
const NONCE_PATTERN = /^[A-Za-z0-9_-]{16,64}$/
const SIGNATURE_PATTERN = /^[a-f0-9]{64}$/

const messages = Object.freeze({
  FRAMEWORK_GATEWAY_REQUEST_INVALID: '请求格式不正确',
  FRAMEWORK_GATEWAY_OPERATION_NOT_ALLOWED: '不允许执行该操作',
  FRAMEWORK_GATEWAY_AUTH_MISSING: '请求认证信息缺失',
  FRAMEWORK_GATEWAY_AUTH_INVALID: '请求认证失败',
  FRAMEWORK_GATEWAY_AUTH_EXPIRED: '请求认证已过期',
  FRAMEWORK_GATEWAY_AUTH_VERSION_UNSUPPORTED: '不支持该签名版本',
  FRAMEWORK_GATEWAY_CONFIG_MISSING: 'Gateway认证配置缺失',
  FRAMEWORK_GATEWAY_TOOL_FAILED: '菜单查询未完成',
  FRAMEWORK_GATEWAY_INTERNAL_ERROR: 'Gateway暂时无法处理请求'
})

const failure = errCode => ({ errCode, message: messages[errCode] })

class GatewayError extends Error {
  constructor(code) {
    super(code)
    this.code = code
  }
}

function ownData(object, key) {
  if (!object || typeof object !== 'object') return undefined
  const descriptor = Object.getOwnPropertyDescriptor(object, key)
  return descriptor && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined
}

function normalizeHeaders(headers) {
  if (!headers || typeof headers !== 'object' || Array.isArray(headers)) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
  const clean = Object.create(null)
  for (const key of Reflect.ownKeys(headers)) {
    if (typeof key !== 'string') throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
    const value = ownData(headers, key)
    const normalized = key.toLowerCase()
    if (typeof value !== 'string' || Object.hasOwn(clean, normalized)) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
    clean[normalized] = value
  }
  return clean
}

function readBodyBytes(event) {
  const body = ownData(event, 'body')
  const encoded = ownData(event, 'isBase64Encoded')
  if (typeof body !== 'string' || ![undefined, false, true].includes(encoded)) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
  let bytes
  if (encoded === true) {
    if (body.length > Math.ceil(MAX_BODY_BYTES * 4 / 3) + 4) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
    if (!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(body)) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
    bytes = Buffer.from(body, 'base64')
  } else {
    bytes = Buffer.from(body, 'utf8')
  }
  if (bytes.length === 0 || bytes.length > MAX_BODY_BYTES) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
  return bytes
}

function createCanonicalSigningString({ timestamp, nonce, bodySha256 }) {
  return [SIGNATURE_VERSION, CANONICAL_METHOD, CANONICAL_PATH, timestamp, nonce, bodySha256].join('\n')
}

function verifyAuthentication({ event, bodyBytes, secret, nowSeconds, cryptoModule }) {
  const headers = normalizeHeaders(ownData(event, 'headers'))
  const version = headers['x-framework-signature-version']
  const timestamp = headers['x-framework-timestamp']
  const nonce = headers['x-framework-nonce']
  const signature = headers['x-framework-signature']
  if ([version, timestamp, nonce, signature].some(value => value === undefined)) throw new GatewayError('FRAMEWORK_GATEWAY_AUTH_MISSING')
  if (version !== SIGNATURE_VERSION) throw new GatewayError('FRAMEWORK_GATEWAY_AUTH_VERSION_UNSUPPORTED')
  if (!/^\d{10,12}$/.test(timestamp) || !NONCE_PATTERN.test(nonce) || !SIGNATURE_PATTERN.test(signature)) {
    throw new GatewayError('FRAMEWORK_GATEWAY_AUTH_INVALID')
  }
  const timestampNumber = Number(timestamp)
  if (!Number.isSafeInteger(timestampNumber)) throw new GatewayError('FRAMEWORK_GATEWAY_AUTH_INVALID')
  if (!Number.isSafeInteger(nowSeconds)) throw new Error('invalid server time')
  if (Math.abs(nowSeconds - timestampNumber) > TIMESTAMP_WINDOW_SECONDS) throw new GatewayError('FRAMEWORK_GATEWAY_AUTH_EXPIRED')

  const bodySha256 = cryptoModule.createHash('sha256').update(bodyBytes).digest('hex')
  const canonical = createCanonicalSigningString({ timestamp, nonce, bodySha256 })
  const expected = cryptoModule.createHmac('sha256', secret).update(canonical, 'utf8').digest()
  const provided = Buffer.from(signature, 'hex')
  if (expected.length !== provided.length || !cryptoModule.timingSafeEqual(expected, provided)) {
    throw new GatewayError('FRAMEWORK_GATEWAY_AUTH_INVALID')
  }
}

function exactKeys(value, expected) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) return false
  const keys = Reflect.ownKeys(value)
  return keys.length === expected.length && keys.every(key => typeof key === 'string' && expected.includes(key))
}

function cleanString(value, maximum) {
  if (typeof value !== 'string') throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
  const clean = value.trim()
  const length = Array.from(clean).length
  if (length < 1 || length > maximum) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
  return clean
}

const operationDefinitions = Object.freeze({
  search_menu: Object.freeze({
    validate(argumentsValue) {
      if (!exactKeys(argumentsValue, ['query'])) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
      return { query: cleanString(argumentsValue.query, 200) }
    },
    execute: (domain, args) => domain.searchMenu(args)
  }),
  list_available_drinks: Object.freeze({
    validate(argumentsValue) {
      if (!exactKeys(argumentsValue, [])) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
      return {}
    },
    execute: (domain, args) => domain.listAvailableDrinks(args)
  }),
  get_dish_detail: Object.freeze({
    validate(argumentsValue) {
      if (!exactKeys(argumentsValue, ['dishId'])) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
      return { dishId: cleanString(argumentsValue.dishId, 128) }
    },
    execute: (domain, args) => domain.getDishDetail(args)
  })
})

function parseRequest(bodyBytes) {
  let body
  try { body = JSON.parse(bodyBytes.toString('utf8')) }
  catch { throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID') }
  if (!exactKeys(body, ['operation', 'arguments'])) throw new GatewayError('FRAMEWORK_GATEWAY_REQUEST_INVALID')
  if (typeof body.operation !== 'string' || !Object.hasOwn(operationDefinitions, body.operation)) {
    throw new GatewayError('FRAMEWORK_GATEWAY_OPERATION_NOT_ALLOWED')
  }
  const definition = operationDefinitions[body.operation]
  return { operation: body.operation, arguments: definition.validate(body.arguments), definition }
}

function createFrameworkGateway({ domain, getSecret = () => process.env.FRAMEWORK_GATEWAY_SECRET,
  now = () => Math.floor(Date.now() / 1000), cryptoModule = crypto } = {}) {
  if (!domain || typeof domain !== 'object') throw new TypeError('domain is required')
  return async function handle(event) {
    try {
      const secret = getSecret()
      if (typeof secret !== 'string' || secret.length < 32 || secret.length > 256) {
        return failure('FRAMEWORK_GATEWAY_CONFIG_MISSING')
      }
      if (!event || typeof event !== 'object' || ownData(event, 'httpMethod') !== CANONICAL_METHOD ||
          !['', '/'].includes(ownData(event, 'path'))) return failure('FRAMEWORK_GATEWAY_REQUEST_INVALID')
      const bodyBytes = readBodyBytes(event)
      verifyAuthentication({ event, bodyBytes, secret, nowSeconds: now(), cryptoModule })
      const request = parseRequest(bodyBytes)
      try {
        const data = await request.definition.execute(domain, request.arguments)
        if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error()
        return { errCode: 0, operation: request.operation, data }
      } catch {
        return failure('FRAMEWORK_GATEWAY_TOOL_FAILED')
      }
    } catch (error) {
      if (error instanceof GatewayError && Object.hasOwn(messages, error.code)) return failure(error.code)
      return failure('FRAMEWORK_GATEWAY_INTERNAL_ERROR')
    }
  }
}

module.exports = { createFrameworkGateway, createCanonicalSigningString,
  SIGNATURE_VERSION, CANONICAL_METHOD, CANONICAL_PATH, TIMESTAMP_WINDOW_SECONDS, MAX_BODY_BYTES }
