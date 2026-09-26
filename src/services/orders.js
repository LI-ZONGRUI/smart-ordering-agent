import { getClientId } from './clientId'

const MAX_ORDER_ITEM_TYPES = 30
const MAX_ITEM_QUANTITY = 99
const PREVIEW_KEYS = ['items', 'requiresConfirmation', 'totalPrice', 'totalQuantity']
const PREVIEW_ITEM_KEYS = ['dishId', 'lineTotal', 'name', 'quantity', 'unitPrice']
const ORDER_ACTION_KEYS = ['items', 'requiresConfirmation', 'totalPrice', 'totalQuantity', 'type']
const ORDER_SUBMISSION_KEYS = ['clientId', 'expectedPreview', 'items', 'remark', 'requestId']
const ORDER_SUBMISSION_ITEM_KEYS = ['dishId', 'quantity']
const EXPECTED_PREVIEW_KEYS = ['items', 'totalPrice', 'totalQuantity']
const EXPECTED_PREVIEW_ITEM_KEYS = ['dishId', 'lineTotal', 'quantity', 'unitPrice']
const CREATED_ORDER_KEYS = ['_id', 'clientId', 'createTime', 'items', 'orderNo', 'remark', 'status', 'totalCount', 'totalPrice']
const CREATED_ORDER_ITEM_KEYS = ['dishId', 'name', 'price', 'quantity', 'subtotal']
const PREVIEW_ERROR_MESSAGES = Object.freeze({
  ORDER_ITEMS_INVALID: '购物车内容无效，请返回购物车检查。',
  ORDER_DISH_NOT_FOUND: '购物车中有菜品已下架，请重新选择。',
  ORDER_DISH_UNAVAILABLE: '购物车中有菜品当前不可用，请返回购物车处理。',
  ORDER_PREVIEW_FAILED: '暂时无法生成订单预览，请稍后重试。'
})
const CREATE_ERROR_MESSAGES = Object.freeze({
  ORDER_ITEMS_INVALID: '订单内容无效，请重新生成预览。',
  ORDER_DISH_NOT_FOUND: '购物车中有菜品已下架，请重新生成预览。',
  ORDER_DISH_UNAVAILABLE: '购物车中有菜品当前不可用，请重新生成预览。',
  ORDER_CONFIRMATION_STALE: '订单信息已变化，请重新生成预览并确认。',
  ORDER_IDEMPOTENCY_CONFLICT: '订单请求与已提交内容冲突，请重新生成预览。',
  ORDER_REQUEST_ID_INVALID: '订单请求标识无效，请重新生成预览。',
  ORDER_CREATE_FAILED: '暂时无法创建订单，请稍后重试。'
})
const DEFINITIVE_CREATE_ERROR_CODES = Object.freeze([
  'ORDER_ITEMS_INVALID',
  'ORDER_DISH_NOT_FOUND',
  'ORDER_DISH_UNAVAILABLE',
  'ORDER_CONFIRMATION_STALE',
  'ORDER_IDEMPOTENCY_CONFLICT',
  'ORDER_REQUEST_ID_INVALID'
])

function createPreviewError(errCode = 'ORDER_PREVIEW_FAILED') {
  const safeCode = Object.hasOwn(PREVIEW_ERROR_MESSAGES, errCode) ? errCode : 'ORDER_PREVIEW_FAILED'
  const error = new Error(PREVIEW_ERROR_MESSAGES[safeCode])
  error.errCode = safeCode
  return error
}

function readErrorCode(error) {
  const code = error?.errCode || error?.code || error?.data?.errCode
  return typeof code === 'string' ? code : ''
}

function createOrderError(errCode = 'ORDER_CREATE_FAILED') {
  const safeCode = Object.hasOwn(CREATE_ERROR_MESSAGES, errCode) ? errCode : 'ORDER_CREATE_FAILED'
  const error = new Error(CREATE_ERROR_MESSAGES[safeCode])
  error.errCode = safeCode
  error.invalidateProposal = DEFINITIVE_CREATE_ERROR_CODES.includes(safeCode)
  error.outcomeUnknown = !error.invalidateProposal
  return error
}

function hasExactKeys(value, expectedKeys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const keys = Object.keys(value).sort()
  return keys.length === expectedKeys.length && expectedKeys.every((key, index) => keys[index] === key)
}

function toCents(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return null
  const cents = Math.round(value * 100)
  if (!Number.isSafeInteger(cents) || Math.abs(cents - value * 100) > 0.000001) return null
  return cents
}

// 结算请求只从Pinia购物车提取菜品ID和数量，不上传名称、价格或本地总价。
export function buildOrderPreviewItems(cartItems) {
  if (!Array.isArray(cartItems) || cartItems.length === 0 || cartItems.length > MAX_ORDER_ITEM_TYPES) {
    throw createPreviewError('ORDER_ITEMS_INVALID')
  }
  const seen = new Set()
  return cartItems.map((item) => {
    const dishId = typeof item?.id === 'string' ? item.id.trim() : ''
    const quantity = item?.quantity
    if (!dishId || seen.has(dishId) || !Number.isInteger(quantity) || quantity < 1 || quantity > MAX_ITEM_QUANTITY) {
      throw createPreviewError('ORDER_ITEMS_INVALID')
    }
    seen.add(dishId)
    return { dishId, quantity }
  })
}

// Preview金额全部转成整数分验证，避免用浮点数直接比较订单金额。
export function validateOrderPreview(response, requestedItems) {
  if (!hasExactKeys(response, ['errCode', 'preview']) || response.errCode !== 0 ||
      !hasExactKeys(response.preview, PREVIEW_KEYS)) throw createPreviewError()

  const preview = response.preview
  if (!Array.isArray(preview.items) || preview.items.length === 0 ||
      preview.items.length !== requestedItems.length || preview.requiresConfirmation !== true) {
    throw createPreviewError()
  }

  const expectedQuantities = new Map(requestedItems.map(item => [item.dishId, item.quantity]))
  const returnedIds = new Set()
  let calculatedQuantity = 0
  let calculatedCents = 0
  const items = preview.items.map((item) => {
    const unitCents = toCents(item?.unitPrice)
    const lineCents = toCents(item?.lineTotal)
    if (!hasExactKeys(item, PREVIEW_ITEM_KEYS) || typeof item.dishId !== 'string' || !item.dishId ||
        typeof item.name !== 'string' || !item.name.trim() || returnedIds.has(item.dishId) ||
        !Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > MAX_ITEM_QUANTITY ||
        expectedQuantities.get(item.dishId) !== item.quantity || unitCents === null || lineCents === null ||
        !Number.isSafeInteger(unitCents * item.quantity) || unitCents * item.quantity !== lineCents) {
      throw createPreviewError()
    }
    returnedIds.add(item.dishId)
    calculatedQuantity += item.quantity
    calculatedCents += lineCents
    if (!Number.isSafeInteger(calculatedQuantity) || !Number.isSafeInteger(calculatedCents)) throw createPreviewError()
    return { dishId: item.dishId, name: item.name.trim(), quantity: item.quantity,
      unitPrice: unitCents / 100, lineTotal: lineCents / 100 }
  })

  const totalCents = toCents(preview.totalPrice)
  if (!Number.isInteger(preview.totalQuantity) || preview.totalQuantity !== calculatedQuantity ||
      totalCents === null || totalCents !== calculatedCents) throw createPreviewError()

  return { type: 'create_order', items, totalQuantity: calculatedQuantity,
    totalPrice: calculatedCents / 100, requiresConfirmation: true }
}

export function isSameCartSnapshot(cartItems, snapshot) {
  let current
  try {
    current = buildOrderPreviewItems(cartItems)
  } catch {
    return false
  }
  if (!Array.isArray(snapshot) || current.length !== snapshot.length) return false
  const snapshotMap = new Map()
  for (const item of snapshot) {
    if (!item || typeof item.dishId !== 'string' || !item.dishId ||
        !Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > MAX_ITEM_QUANTITY ||
        snapshotMap.has(item.dishId) || Object.keys(item).sort().join(',') !== 'dishId,quantity') return false
    snapshotMap.set(item.dishId, item.quantity)
  }
  return current.every(item => snapshotMap.get(item.dishId) === item.quantity)
}

export function buildExpectedPreview(orderPendingAction) {
  if (!hasExactKeys(orderPendingAction, ORDER_ACTION_KEYS) || orderPendingAction.type !== 'create_order' ||
      orderPendingAction.requiresConfirmation !== true || !Array.isArray(orderPendingAction.items) ||
      orderPendingAction.items.length === 0 || orderPendingAction.items.length > MAX_ORDER_ITEM_TYPES) {
    throw createOrderError('ORDER_ITEMS_INVALID')
  }

  let totalQuantity = 0
  let totalCents = 0
  const seen = new Set()
  const items = orderPendingAction.items.map((item) => {
    const unitCents = toCents(item?.unitPrice)
    const lineTotalCents = toCents(item?.lineTotal)
    if (!hasExactKeys(item, PREVIEW_ITEM_KEYS) || typeof item.dishId !== 'string' || !item.dishId ||
        typeof item.name !== 'string' || !item.name.trim() || seen.has(item.dishId) ||
        !Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > MAX_ITEM_QUANTITY ||
        unitCents === null || lineTotalCents === null || !Number.isSafeInteger(unitCents * item.quantity) ||
        unitCents * item.quantity !== lineTotalCents) {
      throw createOrderError('ORDER_ITEMS_INVALID')
    }
    seen.add(item.dishId)
    totalQuantity += item.quantity
    totalCents += lineTotalCents
    if (!Number.isSafeInteger(totalQuantity) || !Number.isSafeInteger(totalCents)) {
      throw createOrderError('ORDER_ITEMS_INVALID')
    }
    return { dishId: item.dishId, quantity: item.quantity,
      unitPrice: unitCents / 100, lineTotal: lineTotalCents / 100 }
  })

  const confirmedTotalCents = toCents(orderPendingAction.totalPrice)
  if (!Number.isInteger(orderPendingAction.totalQuantity) || orderPendingAction.totalQuantity !== totalQuantity ||
      confirmedTotalCents === null || confirmedTotalCents !== totalCents) {
    throw createOrderError('ORDER_ITEMS_INVALID')
  }
  return { items, totalQuantity, totalPrice: totalCents / 100 }
}

function normalizeRequestId(value) {
  if (typeof value !== 'string') throw createOrderError('ORDER_REQUEST_ID_INVALID')
  const requestId = value.trim()
  if (requestId.length < 8 || requestId.length > 128 || !/^[A-Za-z0-9_-]+$/.test(requestId)) {
    throw createOrderError('ORDER_REQUEST_ID_INVALID')
  }
  return requestId
}

// requestId只标识一次订单创建意图，不是登录凭证或加密令牌。
// 时间戳配合三段随机值可降低页面生命周期内的碰撞概率，并兼容微信小程序运行环境。
export function generateOrderRequestId(now = Date.now(), random = Math.random) {
  if (!Number.isSafeInteger(now) || now < 0 || typeof random !== 'function') {
    throw createOrderError('ORDER_REQUEST_ID_INVALID')
  }
  const randomParts = []
  for (let index = 0; index < 3; index += 1) {
    const value = random()
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value >= 1) {
      throw createOrderError('ORDER_REQUEST_ID_INVALID')
    }
    randomParts.push(Math.floor(value * 0x100000000).toString(36).padStart(7, '0'))
  }
  return normalizeRequestId(`ord-${now.toString(36)}-${randomParts.join('')}`)
}

function freezeSubmissionPayload(payload) {
  payload.items.forEach(Object.freeze)
  payload.expectedPreview.items.forEach(Object.freeze)
  Object.freeze(payload.items)
  Object.freeze(payload.expectedPreview.items)
  Object.freeze(payload.expectedPreview)
  return Object.freeze(payload)
}

// 第一次最终提交时同时固定requestId与完整payload。结果未知后的重试必须复用这份内容，
// 避免Cart变化导致同一个requestId对应不同fingerprint。
export function buildConfirmedOrderSubmission(cartItems, orderPendingAction, remark = '', requestId) {
  const items = buildOrderPreviewItems(cartItems)
  const expectedPreview = buildExpectedPreview(orderPendingAction)
  if (typeof remark !== 'string' || remark.length > 200) throw createOrderError('ORDER_ITEMS_INVALID')
  return freezeSubmissionPayload({
    requestId: normalizeRequestId(requestId),
    clientId: getClientId(),
    items: items.map(item => ({ ...item })),
    expectedPreview: {
      items: expectedPreview.items.map(item => ({ ...item })),
      totalQuantity: expectedPreview.totalQuantity,
      totalPrice: expectedPreview.totalPrice
    },
    remark
  })
}

function validateConfirmedOrderSubmission(value) {
  // 重试时不重新读取本地clientId，确保使用第一次提交时冻结的同一身份字段。
  if (!hasExactKeys(value, ORDER_SUBMISSION_KEYS) || typeof value.clientId !== 'string' ||
      !/^anon-[a-z0-9-]{16,80}$/.test(value.clientId) ||
      typeof value.remark !== 'string' || value.remark.length > 200) {
    throw createOrderError('ORDER_ITEMS_INVALID')
  }
  const requestId = normalizeRequestId(value.requestId)
  if (!Array.isArray(value.items) || value.items.some(item => !hasExactKeys(item, ORDER_SUBMISSION_ITEM_KEYS)) ||
      !hasExactKeys(value.expectedPreview, EXPECTED_PREVIEW_KEYS) ||
      !Array.isArray(value.expectedPreview.items) ||
      value.expectedPreview.items.some(item => !hasExactKeys(item, EXPECTED_PREVIEW_ITEM_KEYS))) {
    throw createOrderError('ORDER_ITEMS_INVALID')
  }
  const items = buildOrderPreviewItems(value.items.map(item => ({ id: item?.dishId, quantity: item?.quantity })))
  const expectedPreview = buildExpectedPreview({
    type: 'create_order',
    requiresConfirmation: true,
    items: value.expectedPreview.items.map(item => ({
      dishId: item?.dishId,
      name: '_',
      quantity: item?.quantity,
      unitPrice: item?.unitPrice,
      lineTotal: item?.lineTotal
    })),
    totalQuantity: value.expectedPreview.totalQuantity,
    totalPrice: value.expectedPreview.totalPrice
  })
  if (items.length !== expectedPreview.items.length ||
      !items.every(item => expectedPreview.items.some(expected =>
        expected.dishId === item.dishId && expected.quantity === item.quantity))) {
    throw createOrderError('ORDER_ITEMS_INVALID')
  }
  return { requestId, clientId: value.clientId, items, expectedPreview, remark: value.remark }
}

function validateCreatedOrderResponse(response, expectedPreview, clientId, remark) {
  const order = response?.order
  if (!hasExactKeys(response, ['errCode', 'order']) || response.errCode !== 0 ||
      !hasExactKeys(order, CREATED_ORDER_KEYS) || typeof order._id !== 'string' || !order._id ||
      typeof order.orderNo !== 'string' || !/^OD\d+[A-F0-9]{6}$/.test(order.orderNo) ||
      order.clientId !== clientId || order.status !== 'pending' || order.remark !== remark.trim() ||
      !Number.isInteger(order.createTime) || !Array.isArray(order.items) ||
      order.items.length !== expectedPreview.items.length) {
    throw createOrderError()
  }

  const expectedMap = new Map(expectedPreview.items.map(item => [item.dishId, item]))
  let totalCount = 0
  let totalCents = 0
  const seen = new Set()
  for (const item of order.items) {
    const expected = expectedMap.get(item?.dishId)
    const priceCents = toCents(item?.price)
    const subtotalCents = toCents(item?.subtotal)
    if (!hasExactKeys(item, CREATED_ORDER_ITEM_KEYS) || !expected || seen.has(item.dishId) ||
        typeof item.name !== 'string' || !item.name.trim() || item.quantity !== expected.quantity ||
        priceCents !== toCents(expected.unitPrice) || subtotalCents !== toCents(expected.lineTotal)) {
      throw createOrderError()
    }
    seen.add(item.dishId)
    totalCount += item.quantity
    totalCents += subtotalCents
    if (!Number.isSafeInteger(totalCount) || !Number.isSafeInteger(totalCents)) throw createOrderError()
  }
  if (order.totalCount !== totalCount || toCents(order.totalPrice) !== totalCents ||
      totalCount !== expectedPreview.totalQuantity || totalCents !== toCents(expectedPreview.totalPrice)) {
    throw createOrderError()
  }
  // UI只需要用户可读订单号，不向页面扩散数据库内部_id。
  return { orderNo: order.orderNo }
}

export async function previewOrder(cartItems) {
  const items = buildOrderPreviewItems(cartItems)
  try {
    // 正式页面只调用orders云对象；order-preview-admin仅供HBuilderX开发验收。
    const orders = uniCloud.importObject('orders', { customUI: true })
    const response = await orders.previewOrder(items)
    if (response?.errCode !== 0) throw createPreviewError(readErrorCode(response))
    return {
      orderPendingAction: validateOrderPreview(response, items),
      cartSnapshot: items.map(item => ({ ...item }))
    }
  } catch (error) {
    throw createPreviewError(readErrorCode(error))
  }
}

export async function createConfirmedOrder(submissionOrCartItems, orderPendingAction, remark = '') {
  // 保留V5.5C旧调用兼容；V5.6B正式页面传入已冻结且包含requestId的submission payload。
  const submission = Array.isArray(submissionOrCartItems)
    ? { clientId: getClientId(), items: buildOrderPreviewItems(submissionOrCartItems),
        expectedPreview: buildExpectedPreview(orderPendingAction), remark }
    : validateConfirmedOrderSubmission(submissionOrCartItems)
  if (typeof submission.remark !== 'string' || submission.remark.length > 200) {
    throw createOrderError('ORDER_ITEMS_INVALID')
  }
  try {
    const orders = uniCloud.importObject('orders', { customUI: true })
    const response = await orders.createConfirmedOrder(submission)
    if (response?.errCode !== 0) throw createOrderError(readErrorCode(response))
    return validateCreatedOrderResponse(response, submission.expectedPreview, submission.clientId, submission.remark)
  } catch (error) {
    throw createOrderError(readErrorCode(error))
  }
}

export function createOrder(cartItems, remark) {
  // 不上传购物车显示的价格与总价；云对象会从数据库取实时价格后计算。
  const items = cartItems.map((item) => ({ dishId: item.id, quantity: item.quantity }))
  return uniCloud.importObject('orders').createOrder({ clientId: getClientId(), items, remark })
}

export function getOrders() {
  return uniCloud.importObject('orders').getOrders(getClientId())
}
