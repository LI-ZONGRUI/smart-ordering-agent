// 前端只传点餐需求，密钥和模型配置始终留在云端。
export async function recommendDishes(message) {
  try {
    const ai = uniCloud.importObject('ai', { customUI: true })
    const result = await ai.recommend(message)
    if (result?.errCode && result.errCode !== 0) {
      const error = new Error('recommendation failed')
      error.errCode = result.errCode
      throw error
    }
    // 防止部署版本不一致或异常响应导致页面渲染时报错。
    if (!result || result.errCode !== 0 || !Array.isArray(result.recommendations) ||
        result.recommendations.length > 3 || typeof result.reason !== 'string' ||
        typeof result.totalPrice !== 'number' || !Number.isFinite(result.totalPrice) || result.totalPrice < 0 ||
        result.recommendations.some(dish => !dish || typeof dish.dishId !== 'string' ||
          typeof dish.name !== 'string' || typeof dish.price !== 'number' || !Number.isFinite(dish.price) || dish.price < 0 ||
          !Array.isArray(dish.ingredients) || dish.ingredients.some(item => typeof item !== 'string'))) {
      throw new Error('invalid response')
    }
    return result
  } catch (error) {
    // 不把 SDK 或上游的原始错误展示给用户。
    const code = error?.errCode
    if (code === 'AI_INPUT_INVALID') throw new Error('请填写 1～200 字的点餐需求')
    if (code === 'AI_MENU_FAILED') throw new Error('菜单暂时加载失败，请稍后重试')
    throw new Error('智能推荐暂时不可用，请稍后重新尝试')
  }
}
