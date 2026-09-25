import { getClientId } from './clientId'

const MAX_ORDER_ITEM_TYPES = 30
const MAX_ITEM_QUANTITY = 99
const PREVIEW_KEYS = ['items', 'requiresConfirmation', 'totalPrice', 'totalQuantity']
const PREVIEW_ITEM_KEYS = ['dishId', 'lineTotal', 'name', 'quantity', 'unitPrice']
const PREVIEW_ERROR_MESSAGES = Object.freeze({
  ORDER_ITEMS_INVALID: '购物车内容无效，请返回购物车检查。',
  ORDER_DISH_NOT_FOUND: '购物车中有菜品已下架，请重新选择。',
  ORDER_DISH_UNAVAILABLE: '购物车中有菜品当前不可用，请返回购物车处理。',
  ORDER_PREVIEW_FAILED: '暂时无法生成订单预览，请稍后重试。'
})

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

export function createOrder(cartItems, remark) {
  // 不上传购物车显示的价格与总价；云对象会从数据库取实时价格后计算。
  const items = cartItems.map((item) => ({ dishId: item.id, quantity: item.quantity }))
  return uniCloud.importObject('orders').createOrder({ clientId: getClientId(), items, remark })
}

export function getOrders() {
  return uniCloud.importObject('orders').getOrders(getClientId())
}
