const crypto = require('crypto')
const {
  assertPricingMatchesExpected,
  isOrderBusinessError,
  toSafeOrderBusinessResult,
  validateExpectedPreview,
  validateAndPriceOrderItems
} = require('./order-pricing')
const db = uniCloud.database()
const CONFIRMED_PAYLOAD_KEYS = ['clientId', 'expectedPreview', 'items', 'remark']

function checkClientId(clientId) {
  // clientId 只是开发期的数据隔离标记，任何人都可能伪造它，不能当作登录认证。
  if (typeof clientId !== 'string' || !/^anon-[a-z0-9-]{16,80}$/.test(clientId)) {
    throw new Error('客户端标识无效，请重新打开小程序')
  }
}

function checkRemark(remark) {
  if (typeof remark !== 'string' || remark.length > 200) throw new Error('备注不能超过 200 字')
}

function hasExactKeys(value, expectedKeys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const keys = Object.keys(value).sort()
  return keys.length === expectedKeys.length && expectedKeys.every((key, index) => keys[index] === key)
}

async function persistPricedOrder({ clientId, priced, remark }) {
  // 两个创建入口复用同一订单快照与持久化逻辑，避免出现第二套订单结构。
  const orderItems = priced.items.map(item => ({ dishId: item.dishId, name: item.name,
    price: item.unitPrice, quantity: item.quantity, subtotal: item.lineTotal }))
  const order = {
    orderNo: `OD${Date.now()}${crypto.randomBytes(3).toString('hex').toUpperCase()}`,
    items: orderItems,
    totalPrice: priced.totalPrice,
    totalCount: priced.totalQuantity,
    remark: remark.trim(),
    status: 'pending',
    clientId,
    createTime: Date.now()
  }
  const added = await db.collection('orders').add(order)
  return { _id: added.id, ...order }
}

module.exports = {
  async createOrder(payload) {
    if (!payload || typeof payload !== 'object') throw new Error('订单内容无效')
    const { clientId, items, remark = '' } = payload
    checkClientId(clientId)
    checkRemark(remark)

    // Preview和Create共享同一个实时菜品校验与计价核心；Create每次仍会重新查询。
    let priced
    try {
      priced = await validateAndPriceOrderItems(items, { db })
    } catch (error) {
      // Create保持原有普通Error文案，避免改变已经上线的订单页面错误处理。
      if (isOrderBusinessError(error)) throw new Error(error.message)
      throw error
    }
    return persistPricedOrder({ clientId, priced, remark })
  },

  async previewOrder(items) {
    // Preview只接受dishId和quantity，且只读dishes；不会写orders或生成订单号。
    let priced
    try {
      priced = await validateAndPriceOrderItems(items, { db, strictItems: true })
    } catch (error) {
      // 只恢复共享核心明确标记的业务错误；其他异常统一成固定Preview错误。
      const businessResult = toSafeOrderBusinessResult(error)
      if (businessResult) return businessResult
      return { errCode: 'ORDER_PREVIEW_FAILED', errMsg: '订单预览未完成，请稍后重试' }
    }
    return {
      errCode: 0,
      preview: {
        items: priced.items,
        totalQuantity: priced.totalQuantity,
        totalPrice: priced.totalPrice,
        requiresConfirmation: true
      }
    }
  },

  async createConfirmedOrder(payload) {
    // 该接口只接受固定字段；expectedPreview是待比较的确认值，不是价格依据。
    try {
      if (!hasExactKeys(payload, CONFIRMED_PAYLOAD_KEYS)) {
        return { errCode: 'ORDER_ITEMS_INVALID', errMsg: '订单菜品或数量无效' }
      }
      const { clientId, items, expectedPreview, remark } = payload
      checkClientId(clientId)
      checkRemark(remark)
      validateExpectedPreview(expectedPreview)

      // 在最终写入请求中再次查询真实菜单和计算金额，不能复用旧Preview价格。
      const priced = await validateAndPriceOrderItems(items, { db, strictItems: true })
      assertPricingMatchesExpected(priced, expectedPreview)
      const order = await persistPricedOrder({ clientId, priced, remark })
      return { errCode: 0, order }
    } catch (error) {
      const businessResult = toSafeOrderBusinessResult(error)
      if (businessResult) return businessResult
      // 数据库、程序或其他未知异常都使用固定文案，避免泄露内部细节。
      return { errCode: 'ORDER_CREATE_FAILED', errMsg: '订单创建未完成，请稍后重试' }
    }
  },

  async getOrders(clientId) {
    checkClientId(clientId)
    const result = await db.collection('orders')
      .where({ clientId })
      .orderBy('createTime', 'desc')
      .get()
    return result.data
  }
}
