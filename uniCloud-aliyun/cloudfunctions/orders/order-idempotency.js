const crypto = require('crypto')
const { validateExpectedPreview, validateOrderItems } = require('./order-pricing')

const REQUEST_ID_MIN_LENGTH = 8
const REQUEST_ID_MAX_LENGTH = 128
const IDEMPOTENCY_ERROR_MESSAGES = Object.freeze({
  ORDER_REQUEST_ID_INVALID: '订单请求标识无效，请重新发起结算',
  ORDER_IDEMPOTENCY_CONFLICT: '该订单请求已被其他内容使用，请重新发起结算'
})

class OrderIdempotencyError extends Error {
  constructor(errCode) {
    super(IDEMPOTENCY_ERROR_MESSAGES[errCode])
    this.name = 'OrderIdempotencyError'
    this.errCode = errCode
  }
}

function throwIdempotencyError(errCode) {
  throw new OrderIdempotencyError(errCode)
}

function normalizeRequestId(value) {
  if (typeof value !== 'string') throwIdempotencyError('ORDER_REQUEST_ID_INVALID')
  const requestId = value.trim()
  if (requestId.length < REQUEST_ID_MIN_LENGTH || requestId.length > REQUEST_ID_MAX_LENGTH ||
      !/^[A-Za-z0-9_-]+$/.test(requestId)) {
    throwIdempotencyError('ORDER_REQUEST_ID_INVALID')
  }
  return requestId
}

function compareDishId(left, right) {
  return left < right ? -1 : left > right ? 1 : 0
}

function createRequestFingerprint({ clientId, items, expectedPreview, remark }) {
  const quantities = validateOrderItems(items, { strictItems: true })
  const expected = validateExpectedPreview(expectedPreview)

  // 只使用影响创建意图的规范化字段。数组按dishId排序，金额统一使用整数分。
  const canonical = {
    clientId,
    items: [...quantities.entries()]
      .sort(([left], [right]) => compareDishId(left, right))
      .map(([dishId, quantity]) => ({ dishId, quantity })),
    expectedPreview: {
      items: [...expected.itemsByDishId.entries()]
        .sort(([left], [right]) => compareDishId(left, right))
        .map(([dishId, item]) => ({
          dishId,
          quantity: item.quantity,
          unitPriceCents: item.unitCents,
          lineTotalCents: item.lineTotalCents
        })),
      totalQuantity: expected.totalQuantity,
      totalPriceCents: expected.totalCents
    },
    remark: remark.trim()
  }
  return crypto.createHash('sha256').update(JSON.stringify(canonical), 'utf8').digest('hex')
}

function isOrderIdempotencyError(error) {
  return error instanceof OrderIdempotencyError &&
    typeof error.errCode === 'string' && Object.hasOwn(IDEMPOTENCY_ERROR_MESSAGES, error.errCode)
}

function toSafeIdempotencyResult(error) {
  if (!isOrderIdempotencyError(error)) return null
  return { errCode: error.errCode, errMsg: IDEMPOTENCY_ERROR_MESSAGES[error.errCode] }
}

function assertExistingIntentMatches(existing, { clientId, requestFingerprint }) {
  if (!existing || existing.clientId !== clientId || existing.requestFingerprint !== requestFingerprint) {
    throwIdempotencyError('ORDER_IDEMPOTENCY_CONFLICT')
  }
}

module.exports = {
  IDEMPOTENCY_ERROR_MESSAGES,
  REQUEST_ID_MAX_LENGTH,
  REQUEST_ID_MIN_LENGTH,
  assertExistingIntentMatches,
  createRequestFingerprint,
  isOrderIdempotencyError,
  normalizeRequestId,
  toSafeIdempotencyResult
}
