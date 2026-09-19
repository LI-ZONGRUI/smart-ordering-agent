const crypto = require('crypto')
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
    if (!Array.isArray(items) || items.length === 0 || items.length > 30) {
      throw new Error('请选择 1～30 种菜品')
    }
    if (typeof remark !== 'string' || remark.length > 200) {
      throw new Error('备注不能超过 200 字')
    }

    const quantities = new Map()
    for (const item of items) {
      if (!item || typeof item.dishId !== 'string' || !item.dishId ||
          !Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > 99 ||
          quantities.has(item.dishId)) {
        throw new Error('菜品或数量无效，请返回购物车检查')
      }
      quantities.set(item.dishId, item.quantity)
    }

    const dishIds = [...quantities.keys()]
    const result = await db.collection('dishes')
      .where({ _id: db.command.in(dishIds) })
      .get()
    const dishMap = new Map(result.data.map((dish) => [dish._id, dish]))

    let totalCount = 0
    let totalCents = 0
    const orderItems = dishIds.map((dishId) => {
      const dish = dishMap.get(dishId)
      if (!dish) throw new Error('有菜品已下架，请返回购物车检查')
      if (dish.status !== 'on_sale') throw new Error(`${dish.name} 已售罄，请返回购物车删除`)

      const price = dish.price
      if (typeof dish.name !== 'string' || !dish.name ||
          typeof price !== 'number' || !Number.isFinite(price) || price < 0 ||
          Math.abs(Math.round(price * 100) - price * 100) > 0.000001) {
        throw new Error('菜品名称或价格数据无效')
      }
      const quantity = quantities.get(dishId)
      const priceCents = Math.round(price * 100)
      const subtotalCents = priceCents * quantity
      if (!Number.isSafeInteger(subtotalCents) || !Number.isSafeInteger(totalCents + subtotalCents)) {
        throw new Error('订单金额超出范围')
      }
      totalCount += quantity
      totalCents += subtotalCents

      // 前端只传菜品 ID 和数量。价格必须从云数据库重新读取，防止前端改价后少付。
      // 这里复制名称与单价，之后菜品改名或改价也不会改动历史订单。
      return {
        dishId,
        name: dish.name,
        price: priceCents / 100,
        quantity,
        subtotal: subtotalCents / 100
      }
    })

    const order = {
      orderNo: `OD${Date.now()}${crypto.randomBytes(3).toString('hex').toUpperCase()}`,
      items: orderItems,
      totalPrice: totalCents / 100,
      totalCount,
      remark: remark.trim(),
      status: 'pending',
      clientId,
      createTime: Date.now()
    }
    const added = await db.collection('orders').add(order)
    return { _id: added.id, ...order }
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
