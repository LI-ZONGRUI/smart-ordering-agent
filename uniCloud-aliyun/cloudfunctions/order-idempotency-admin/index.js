const SAFE_ORDER_ERRORS = Object.freeze({
  ORDER_ITEMS_INVALID: '订单菜品或数量无效',
  ORDER_DISH_NOT_FOUND: '未找到对应菜品',
  ORDER_DISH_UNAVAILABLE: '当前菜品不可用',
  ORDER_CONFIRMATION_STALE: '订单信息已发生变化，请重新确认',
  ORDER_REQUEST_ID_INVALID: '订单请求标识无效，请重新发起结算',
  ORDER_IDEMPOTENCY_CONFLICT: '该订单请求已被其他内容使用，请重新发起结算'
})

function restoreSafeOrderError(error) {
  if (!error || (typeof error !== 'object' && typeof error !== 'function')) return null
  const code = Object.hasOwn(error, 'errCode') ? error.errCode : error.code
  if (typeof code !== 'string' || !Object.hasOwn(SAFE_ORDER_ERRORS, code)) return null
  return { errCode: code, errMsg: SAFE_ORDER_ERRORS[code] }
}

function createFailed() {
  return { errCode: 'ORDER_CREATE_FAILED', errMsg: '订单创建未完成，请检查部署与输入' }
}

// 仅供HBuilderX开发验收幂等重试；不复制校验、计价、指纹或持久化逻辑。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'ORDER_IDEMPOTENCY_FORBIDDEN', errMsg: '请通过 HBuilderX 执行订单幂等测试' }
  }
  try {
    const orders = uniCloud.importObject('orders')
    const result = await orders.createConfirmedOrder(event)
    const businessError = restoreSafeOrderError(result)
    if (businessError) return businessError
    if (!result || typeof result !== 'object' || result.errCode !== 0) return createFailed()
    return result
  } catch (error) {
    const businessError = restoreSafeOrderError(error)
    return businessError || createFailed()
  }
}
