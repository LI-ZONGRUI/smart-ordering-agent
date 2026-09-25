const crypto = require('crypto')
const {
  isOrderBusinessError,
  toSafeOrderBusinessResult,
  validateAndPriceOrderItems
} = require('./order-pricing')
const db = uniCloud.database()

function checkClientId(clientId) {
  // clientId 只是开发期的数据隔离标记，任何人都可能伪造它，不能当作登录认证。
  if (typeof clientId !== 'string' || !/^anon-[a-z0-9-]{16,80}$/.test(clientId)) {
    throw new Error('客户端标识无效，请重新打开小程序')
  }
}

module.exports = {
  async createOrder(payload) {
    if (!payload || typeof payload !== 'object') throw new Error('订单内容无效')
    const { clientId, items, remark = '' } = payload
    checkClientId(clientId)
    if (typeof remark !== 'string' || remark.length > 200) {
      throw new Error('备注不能超过 200 字')
    }

    // Preview和Create共享同一个实时菜品校验与计价核心；Create每次仍会重新查询。
    let priced
    try {
      priced = await validateAndPriceOrderItems(items, { db })
    } catch (error) {
      // Create保持原有普通Error文案，避免改变已经上线的订单页面错误处理。
      if (isOrderBusinessError(error)) throw new Error(error.message)
      throw error
    }
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

  async getOrders(clientId) {
    checkClientId(clientId)
    const result = await db.collection('orders')
      .where({ clientId })
      .orderBy('createTime', 'desc')
      .get()
    return result.data
  }
}
