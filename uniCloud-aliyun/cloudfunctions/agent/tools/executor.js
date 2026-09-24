const { getToolDefinitions } = require('./registry')
const { searchMenu, listAvailableDrinks, getDishDetail } = require('./menu-tools')
const handlers = Object.freeze({ search_menu: searchMenu, list_available_drinks: listAvailableDrinks, get_dish_detail: getDishDetail })
const schemas = new Map(getToolDefinitions().map(tool => [tool.function.name, tool.function.parameters]))
const errors = {
  AGENT_TOOL_NOT_FOUND: '工具未注册',
  AGENT_TOOL_ARGUMENT_INVALID: '工具参数格式不正确',
  AGENT_TOOL_EXECUTION_FAILED: '工具执行失败，请检查菜单数据或稍后重试'
}
const failure = errCode => ({ errCode, errMsg: errors[errCode] })

function validateArgs(schema, args) {
  if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error()
  const proto = Object.getPrototypeOf(args)
  if (proto !== Object.prototype && proto !== null) throw new Error()
  if (Reflect.ownKeys(args).some(key => typeof key !== 'string' || !Object.hasOwn(schema.properties, key))) throw new Error()
  const clean = {}
  for (const key of schema.required) {
    // 仅接受JSON数据属性，不接受getter或继承属性；禁止传入实现函数、collection等额外参数。
    const descriptor = Object.getOwnPropertyDescriptor(args, key)
    if (!descriptor || !Object.hasOwn(descriptor, 'value') || typeof descriptor.value !== 'string') throw new Error()
    const value = descriptor.value.trim()
    const rule = schema.properties[key]
    if (Array.from(value).length < rule.minLength || (rule.maxLength && Array.from(value).length > rule.maxLength)) throw new Error()
    clean[key] = value
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
    return { errCode: 0, ...await handlers[toolName](clean, { db }) }
  } catch {
    // 不记录/返回原始DB异常、请求参数或内部连接信息。
    return failure('AGENT_TOOL_EXECUTION_FAILED')
  }
}

module.exports = { executeTool }
