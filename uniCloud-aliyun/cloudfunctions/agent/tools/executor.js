const { getToolDefinitions } = require('./registry')
const { searchMenu, listAvailableDrinks, getDishDetail } = require('./menu-tools')
const { prepareAddToCart } = require('./cart-actions')
const handlers = Object.freeze({ search_menu: searchMenu, list_available_drinks: listAvailableDrinks,
  get_dish_detail: getDishDetail, prepare_add_to_cart: prepareAddToCart })
const schemas = new Map(getToolDefinitions().map(tool => [tool.function.name, tool.function.parameters]))
const errors = {
  AGENT_TOOL_NOT_FOUND: '工具未注册',
  AGENT_TOOL_ARGUMENT_INVALID: '工具参数格式不正确',
  AGENT_TOOL_EXECUTION_FAILED: '工具执行失败，请检查菜单数据或稍后重试',
  AGENT_ACTION_DISH_NOT_FOUND: '未找到对应菜品',
  AGENT_ACTION_DISH_UNAVAILABLE: '当前菜品不可用'
}
const SAFE_TOOL_ERROR_CODES = new Set([
  'AGENT_ACTION_DISH_NOT_FOUND',
  'AGENT_ACTION_DISH_UNAVAILABLE'
])
const failure = errCode => ({ errCode, errMsg: errors[errCode] })

function getSafeErrorCode(error) {
  if (!error || typeof error !== 'object') return null
  try {
    const code = Object.hasOwn(error, 'errCode') ? error.errCode : error.code
    return SAFE_TOOL_ERROR_CODES.has(code) ? code : null
  } catch {
    return null
  }
}

function normalizeHandlerResult(result) {
  if (!result || typeof result !== 'object' || Array.isArray(result)) return failure('AGENT_TOOL_EXECUTION_FAILED')
  if (!Object.hasOwn(result, 'errCode') || result.errCode === 0) return { errCode: 0, ...result }

  // 只允许明确列出的安全业务错误穿透，避免未知错误码和原始异常信息泄露。
  if (SAFE_TOOL_ERROR_CODES.has(result.errCode)) return failure(result.errCode)
  return failure('AGENT_TOOL_EXECUTION_FAILED')
}

function validateArgs(schema, args) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error()
  const proto = Object.getPrototypeOf(args)
  if (proto !== Object.prototype && proto !== null) throw new Error()
  if (Reflect.ownKeys(args).some(key => typeof key !== 'string' || !Object.hasOwn(schema.properties, key))) throw new Error()
  const clean = {}
  for (const key of schema.required) {
    // 仅接受JSON数据属性，不接受getter或继承属性；禁止传入实现函数、collection等额外参数。
    const descriptor = Object.getOwnPropertyDescriptor(args, key)
    if (!descriptor || !Object.hasOwn(descriptor, 'value')) throw new Error()
    const rule = schema.properties[key]
    if (rule.type === 'string') {
      if (typeof descriptor.value !== 'string') throw new Error()
      const value = descriptor.value.trim()
      if (Array.from(value).length < rule.minLength || (rule.maxLength && Array.from(value).length > rule.maxLength)) throw new Error()
      clean[key] = value
    } else if (rule.type === 'integer') {
      const value = descriptor.value
      if (!Number.isInteger(value) || value < rule.minimum || value > rule.maximum) throw new Error()
      clean[key] = value
    } else {
      throw new Error()
    }
  }
  return clean
}

// db是服务端内部依赖；客户端args不参与依赖、函数或集合选择。
async function executeTool(toolName, args, { db }) {
  if (typeof toolName !== 'string' || !schemas.has(toolName) || !Object.hasOwn(handlers, toolName)) return failure('AGENT_TOOL_NOT_FOUND')
  let clean
  try { clean = validateArgs(schemas.get(toolName), args) }
  catch { return failure('AGENT_TOOL_ARGUMENT_INVALID') }
  try {
    return normalizeHandlerResult(await handlers[toolName](clean, { db }))
  } catch (error) {
    // 不记录/返回原始DB异常、请求参数或内部连接信息。
    return failure(getSafeErrorCode(error) || 'AGENT_TOOL_EXECUTION_FAILED')
  }
}

module.exports = { executeTool }
