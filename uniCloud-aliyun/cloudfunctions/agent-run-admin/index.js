// 仅用于HBuilderX“上传并运行”；不配置URL化、定时器或微信前端入口。
function pickItem(item) {
  if (!item || typeof item !== 'object' || Array.isArray(item)) return null
  const value = {}
  for (const key of ['dishId', 'name', 'status']) {
    if (typeof item[key] === 'string') value[key] = item[key]
  }
  if (typeof item.price === 'number' && Number.isFinite(item.price)) value.price = item.price
  return value
}

function summarizeToolResult(toolName, result) {
  const summary = {}
  if (toolName === 'search_menu' || toolName === 'list_available_drinks') {
    if (Number.isInteger(result?.count) && result.count >= 0) summary.count = result.count
    if (Array.isArray(result?.items)) summary.items = result.items.map(pickItem).filter(Boolean)
  } else if (toolName === 'get_dish_detail') {
    if (typeof result?.found === 'boolean') summary.found = result.found
    if (result?.item) summary.item = pickItem(result.item)
  }
  return summary
}

function compactTrace(trace) {
  if (!Array.isArray(trace)) return []
  const compact = []
  for (const item of trace) {
    if (!item || !Number.isInteger(item.step) || typeof item.toolName !== 'string') continue
    if (item.type === 'tool_call') {
      compact.push({ step: item.step, type: item.type, toolName: item.toolName, arguments: item.arguments })
    } else if (item.type === 'tool_result') {
      compact.push({ step: item.step, type: item.type, toolName: item.toolName,
        summary: summarizeToolResult(item.toolName, item.result) })
    }
  }
  return compact
}

function traceOnlyResult(result) {
  if (!result || typeof result !== 'object') {
    return { errCode: 'AGENT_MODEL_RESPONSE_INVALID', errMsg: 'Agent 管理验收结果格式异常' }
  }
  if (result.errCode !== 0) return result
  return {
    errCode: 0,
    query: result.query,
    completed: result.completed,
    trace: compactTrace(result.trace)
  }
}

exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'AGENT_TOOL_FORBIDDEN', errMsg: '请在 HBuilderX 上传并运行 Agent 管理云函数' }
  }
  try {
    const agent = uniCloud.importObject('agent')
    // traceOnly 只压缩同一次完整 runForAdmin 结果，不创建另一条 Agent 执行路径。
    const result = await agent.runForAdmin(event?.query)
    return event?.traceOnly === true ? traceOnlyResult(result) : result
  } catch {
    // 不透传云对象异常、模型请求头或内部地址。
    return { errCode: 'AGENT_MODEL_REQUEST_FAILED', errMsg: 'Agent 调用未完成，请检查部署和云端配置' }
  }
}
