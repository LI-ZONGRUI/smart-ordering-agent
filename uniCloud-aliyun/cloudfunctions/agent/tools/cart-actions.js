const { getDishDetail } = require('./menu-tools')

const actionFailure = (errCode, errMsg) => ({
  errCode,
  errMsg,
  tool: 'prepare_add_to_cart'
})

async function prepareAddToCart({ dishId, quantity }, { db }) {
  // 模型只提供身份和数量；名称、状态、单价必须由服务端重新查询真实 dishes。
  const detail = await getDishDetail({ dishId }, { db })
  if (!detail.found) {
    return actionFailure('AGENT_ACTION_DISH_NOT_FOUND', '菜品不存在，无法准备购物车操作')
  }
  if (detail.item.status !== 'on_sale') {
    return actionFailure('AGENT_ACTION_DISH_UNAVAILABLE', '菜品当前不可购买，无法准备购物车操作')
  }

  const unitCents = Math.round(detail.item.price * 100)
  const totalCents = unitCents * quantity
  if (!Number.isSafeInteger(unitCents) || Math.abs(unitCents - detail.item.price * 100) > 0.000001 ||
      !Number.isSafeInteger(totalCents)) throw new Error('invalid price')

  return {
    tool: 'prepare_add_to_cart',
    pendingAction: {
      type: 'add_to_cart',
      dishId: detail.item.dishId,
      name: detail.item.name,
      quantity,
      unitPrice: unitCents / 100,
      totalPrice: totalCents / 100,
      requiresConfirmation: true
    }
  }
}

module.exports = { prepareAddToCart }
