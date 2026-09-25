const SAFE_ORDER_ERRORS = Object.freeze({
  ORDER_ITEMS_INVALID: '订单菜品或数量无效',
  ORDER_DISH_NOT_FOUND: '未找到对应菜品',
  ORDER_DISH_UNAVAILABLE: '当前菜品不可用'
})

function restoreSafeOrderError(error) {
  if (!error || (typeof error !== 'object' && typeof error !== 'function')) return null
  const code = Object.hasOwn(error, 'errCode') ? error.errCode : error.code
  if (typeof code !== 'string' || !Object.hasOwn(SAFE_ORDER_ERRORS, code)) return null
  // 文案始终来自本地白名单，不信任云对象代理异常中的message/errMsg。
  return { errCode: code, errMsg: SAFE_ORDER_ERRORS[code] }
}

function previewFailed() {
  return { errCode: 'ORDER_PREVIEW_FAILED', errMsg: '订单预览未完成，请检查菜品状态和输入' }
}

// 仅供HBuilderX“上传并运行”验收订单预览；不配置URL、定时器或前端入口。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'ORDER_PREVIEW_FORBIDDEN', errMsg: '请通过 HBuilderX 执行订单预览测试' }
  }
  try {
    const orders = uniCloud.importObject('orders')
    // 只转发items；所有校验和计价都由正式orders.previewOrder完成。
    const result = await orders.previewOrder(event?.items)
    const businessError = restoreSafeOrderError(result)
    if (businessError) return businessError
    if (result && typeof result === 'object' && Object.hasOwn(result, 'errCode') && result.errCode !== 0) {
      return previewFailed()
    }
    return result
  } catch (error) {
    const businessError = restoreSafeOrderError(error)
    if (businessError) return businessError
    return previewFailed()
  }
}
