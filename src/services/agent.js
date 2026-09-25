const MAX_QUERY_LENGTH = 200
const ACTION_KEYS = ['type', 'dishId', 'name', 'quantity', 'unitPrice', 'totalPrice', 'requiresConfirmation']

const ERROR_MESSAGES = {
  AGENT_QUERY_INVALID: '请输入 1～200 字的问题。',
  AGENT_CONFIG_MISSING: '点餐助手暂时不可用，请稍后重试。',
  AGENT_MODEL_REQUEST_FAILED: '点餐助手暂时无法响应，请稍后重试。',
  AGENT_MODEL_RESPONSE_INVALID: '点餐助手返回异常，请重新尝试。',
  AGENT_MAX_STEPS_EXCEEDED: '本次请求未能完成，请换一种说法重试。',
  AGENT_MAX_TOOL_CALLS_EXCEEDED: '本次请求未能完成，请换一种说法重试。',
  AGENT_ACTION_DISH_NOT_FOUND: '没有找到对应菜品，请重新选择。',
  AGENT_ACTION_DISH_UNAVAILABLE: '当前菜品不可用，请重新选择。'
}

function publicError(message, errCode, invalidateAction = false) {
  const error = new Error(message)
  error.errCode = errCode
  error.invalidateAction = invalidateAction
  return error
}

function readErrorCode(error) {
  if (!error || typeof error !== 'object') return ''
  try {
    return typeof error.errCode === 'string' ? error.errCode
      : typeof error.code === 'string' ? error.code : ''
  } catch {
    return ''
  }
}

function toCents(value) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return null
  const cents = Math.round(value * 100)
  if (!Number.isSafeInteger(cents) || Math.abs(value * 100 - cents) > 0.000001) return null
  return cents
}

export function validatePendingAction(action) {
  const invalid = () => { throw publicError('待确认操作无效，请重新发起。', 'AGENT_PENDING_ACTION_INVALID', true) }
  if (!action || typeof action !== 'object' || Array.isArray(action)) invalid()
  const keys = Object.keys(action)
  if (keys.length !== ACTION_KEYS.length || keys.some(key => !ACTION_KEYS.includes(key)) ||
      ACTION_KEYS.some(key => !Object.hasOwn(action, key))) invalid()

  const dishId = typeof action.dishId === 'string' ? action.dishId.trim() : ''
  const name = typeof action.name === 'string' ? action.name.trim() : ''
  const unitCents = toCents(action.unitPrice)
  const totalCents = toCents(action.totalPrice)
  if (action.type !== 'add_to_cart' || !dishId || !name || !Number.isInteger(action.quantity) ||
      action.quantity < 1 || action.quantity > 20 || unitCents === null || totalCents === null ||
      action.requiresConfirmation !== true || !Number.isSafeInteger(unitCents * action.quantity) ||
      unitCents * action.quantity !== totalCents) invalid()

  // 只构造唯一允许的动作结构，不按type动态调用任意函数。
  return { type: 'add_to_cart', dishId, name, quantity: action.quantity,
    unitPrice: unitCents / 100, totalPrice: totalCents / 100, requiresConfirmation: true }
}

export async function runOrderingAgent(query) {
  if (typeof query !== 'string') throw publicError(ERROR_MESSAGES.AGENT_QUERY_INVALID, 'AGENT_QUERY_INVALID')
  const text = query.trim()
  if (!text || Array.from(text).length > MAX_QUERY_LENGTH) {
    throw publicError(ERROR_MESSAGES.AGENT_QUERY_INVALID, 'AGENT_QUERY_INVALID')
  }

  let timer
  try {
    const agent = uniCloud.importObject('agent', { customUI: true })
    const response = await Promise.race([
      agent.run(text),
      new Promise((resolve, reject) => {
        timer = setTimeout(() => reject(publicError('请求超时', 'AGENT_REQUEST_TIMEOUT')), 60000)
      })
    ])
    if (response?.errCode !== 0) throw publicError('Agent request failed', response?.errCode || 'AGENT_RESPONSE_INVALID')
    if (!response || response.completed !== true || typeof response.answer !== 'string' || !response.answer.trim()) {
      throw publicError('Invalid Agent response', 'AGENT_RESPONSE_INVALID')
    }

    // 页面只接收正式结果字段；Trace、messages、Prompt和模型原始响应不会透传。
    const result = { query: text, answer: response.answer.trim(), completed: true }
    if (Object.hasOwn(response, 'pendingAction')) result.pendingAction = validatePendingAction(response.pendingAction)
    return result
  } catch (error) {
    if (error?.errCode === 'AGENT_PENDING_ACTION_INVALID') throw error
    const code = readErrorCode(error)
    throw publicError(ERROR_MESSAGES[code] || '点餐助手暂时不可用，请稍后重试。', code || 'AGENT_REQUEST_FAILED')
  } finally {
    clearTimeout(timer)
  }
}

export async function executePendingCartAction(action, { loadDishes, addDish }) {
  const cleanAction = validatePendingAction(action)
  if (typeof loadDishes !== 'function' || typeof addDish !== 'function') {
    throw publicError('待确认操作无效，请重新发起。', 'AGENT_PENDING_ACTION_INVALID', true)
  }

  let dishes
  try {
    dishes = await loadDishes()
  } catch {
    throw publicError('暂时无法确认菜品状态，请重试。', 'AGENT_CART_MENU_UNAVAILABLE')
  }
  if (!Array.isArray(dishes)) {
    throw publicError('暂时无法确认菜品状态，请重试。', 'AGENT_CART_MENU_UNAVAILABLE')
  }

  const dish = dishes.find(item => item?.id === cleanAction.dishId)
  if (!dish || dish.status !== 'on_sale') {
    throw publicError('菜品状态已变化，目前无法加入购物车，请重新选择。',
      'AGENT_CART_DISH_UNAVAILABLE', true)
  }

  const currentPriceCents = toCents(dish.price)
  const proposedPriceCents = toCents(cleanAction.unitPrice)
  if (currentPriceCents === null || currentPriceCents !== proposedPriceCents) {
    throw publicError('菜品价格已变化，请重新确认最新价格。', 'AGENT_CART_PRICE_CHANGED', true)
  }

  // 用户确认后只显式执行现有Pinia addDish；数量来自已校验提案，不按动作名动态派发。
  let added
  try {
    added = addDish(dish, cleanAction.quantity)
  } catch {
    throw publicError('暂时无法加入购物车，请重试。', 'AGENT_CART_MUTATION_FAILED')
  }
  if (added !== true) {
    throw publicError('菜品状态已变化，目前无法加入购物车，请重新选择。',
      'AGENT_CART_DISH_UNAVAILABLE', true)
  }
  return { name: dish.name, quantity: cleanAction.quantity }
}
