const MAX_ORDER_ITEM_TYPES = 30
const MAX_ITEM_QUANTITY = 99
const ITEM_KEYS = ['dishId', 'quantity']
const ORDER_BUSINESS_ERROR_MESSAGES = Object.freeze({
  ORDER_ITEMS_INVALID: '订单菜品或数量无效',
  ORDER_DISH_NOT_FOUND: '未找到对应菜品',
  ORDER_DISH_UNAVAILABLE: '当前菜品不可用'
})

class OrderBusinessError extends Error {
  constructor(errCode, message) {
    super(message)
    this.name = 'OrderBusinessError'
    this.errCode = errCode
    this.errMsg = ORDER_BUSINESS_ERROR_MESSAGES[errCode]
  }
}

function throwBusinessError(errCode, legacyMessage) {
  throw new OrderBusinessError(errCode, legacyMessage)
}

function isOrderBusinessError(error) {
  return error instanceof OrderBusinessError &&
    typeof error.errCode === 'string' && Object.hasOwn(ORDER_BUSINESS_ERROR_MESSAGES, error.errCode)
}

function toSafeOrderBusinessResult(error) {
  if (!isOrderBusinessError(error)) return null
  return { errCode: error.errCode, errMsg: ORDER_BUSINESS_ERROR_MESSAGES[error.errCode] }
}

function validateItems(items, { strictItems }) {
  if (!Array.isArray(items) || items.length === 0 || items.length > MAX_ORDER_ITEM_TYPES) {
    throwBusinessError('ORDER_ITEMS_INVALID', '请选择 1～30 种菜品')
  }

  const quantities = new Map()
  for (const item of items) {
    if (!item || typeof item !== 'object' || Array.isArray(item) ||
        typeof item.dishId !== 'string' || !item.dishId ||
        !Number.isInteger(item.quantity) || item.quantity < 1 || item.quantity > MAX_ITEM_QUANTITY ||
        quantities.has(item.dishId) || (strictItems && (
          Object.keys(item).length !== ITEM_KEYS.length ||
          Object.keys(item).some(key => !ITEM_KEYS.includes(key)) ||
          ITEM_KEYS.some(key => !Object.hasOwn(item, key))
        ))) {
      throwBusinessError('ORDER_ITEMS_INVALID', '菜品或数量无效，请返回购物车检查')
    }
    quantities.set(item.dishId, item.quantity)
  }
  return quantities
}

async function validateAndPriceOrderItems(items, { db, strictItems = false }) {
  const quantities = validateItems(items, { strictItems })
  const dishIds = [...quantities.keys()]

  let result
  try {
    result = await db.collection('dishes')
      .where({ _id: db.command.in(dishIds) })
      .get()
  } catch {
    // 不返回数据库连接、集合或内部异常信息。
    throw new Error('菜单数据暂时无法读取，请稍后重试')
  }
  if (!result || !Array.isArray(result.data)) throw new Error('菜单数据暂时无法读取，请稍后重试')
  const dishMap = new Map(result.data.map(dish => [dish._id, dish]))

  let totalQuantity = 0
  let totalCents = 0
  const pricedItems = dishIds.map((dishId) => {
    const dish = dishMap.get(dishId)
    if (!dish) throwBusinessError('ORDER_DISH_NOT_FOUND', '有菜品已下架，请返回购物车检查')
    if (dish.status !== 'on_sale') {
      throwBusinessError('ORDER_DISH_UNAVAILABLE', `${dish.name} 已售罄，请返回购物车删除`)
    }

    const price = dish.price
    if (typeof dish.name !== 'string' || !dish.name || typeof price !== 'number' ||
        !Number.isFinite(price) || price < 0 ||
        Math.abs(Math.round(price * 100) - price * 100) > 0.000001) {
      throw new Error('菜品名称或价格数据无效')
    }

    const quantity = quantities.get(dishId)
    const unitCents = Math.round(price * 100)
    const lineTotalCents = unitCents * quantity
    if (!Number.isSafeInteger(lineTotalCents) || !Number.isSafeInteger(totalCents + lineTotalCents) ||
        !Number.isSafeInteger(totalQuantity + quantity)) {
      throw new Error('订单金额超出范围')
    }
    totalQuantity += quantity
    totalCents += lineTotalCents

    // 名称和价格只来自实时数据库，客户端不能通过同名字段覆盖。
    return {
      dishId,
      name: dish.name,
      quantity,
      unitPrice: unitCents / 100,
      lineTotal: lineTotalCents / 100
    }
  })

  return { items: pricedItems, totalQuantity, totalPrice: totalCents / 100 }
}

module.exports = {
  MAX_ORDER_ITEM_TYPES,
  MAX_ITEM_QUANTITY,
  ORDER_BUSINESS_ERROR_MESSAGES,
  isOrderBusinessError,
  toSafeOrderBusinessResult,
  validateAndPriceOrderItems
}
