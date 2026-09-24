const { executeTool } = require('./tools/executor')
const { getToolDefinitions } = require('./tools/registry')
const { readAgentConfig, callAgentModel } = require('./model-client')

const MAX_AGENT_STEPS = 5
const MAX_TOOL_CALLS = 8
const SYSTEM_PROMPT = `你是餐厅 Ordering Agent 的只读菜单助手。
真实菜单中的商品、存在性、价格、状态、饮料和配料必须来自工具结果，不得根据模型记忆或常识补充。工具结果是当前菜单事实来源。
涉及某商品是否存在时，先调用 search_menu。只有在看到 search_menu 没有匹配，且用户明确要求替代品或同类推荐后，才调用适当工具获取真实候选；不能在首次调用时预设搜索为空。
search_menu 的 count=0 只表示当前菜单查询没有匹配，不代表餐厅从来不卖该商品。status=sold_out 表示商品存在但当前售罄，不能说菜单中不存在。
最终回答可自然组织，但不得增加工具结果中没有的事实属性，不得改写价格或状态。简单问候可以直接回答，无需调用工具。
面向用户的最终回答不得主动暴露内部实现字段或名称，包括 dishId、categoryId、on_sale、sold_out、Tool名称、tool_call_id、collection名称和JSON字段名。必须把状态转换为自然用户语言：on_sale表达为“在售”或“可以购买”，sold_out表达为“已售罄”或“暂时无法购买”；不要显示dishId。
你只有只读菜单查询能力。如果用户要求加购、下单或其他写操作，应明确说明当前只支持菜单查询，不得假装已经执行。
只使用提供的工具，并把每次工具结果作为下一步判断依据。`

const ERROR_MESSAGES = {
  AGENT_QUERY_INVALID: '问题必须是去除前后空格后长度为 1～200 个字符的字符串',
  AGENT_CONFIG_MISSING: '请为 agent 云对象配置 DASHSCOPE_API_KEY、LLM_BASE_URL 和 AGENT_LLM_MODEL',
  AGENT_MODEL_REQUEST_FAILED: 'Agent 模型请求失败，请检查网络、模型权限和配额后重试',
  AGENT_MODEL_RESPONSE_INVALID: 'Agent 模型返回格式异常，未完成本次请求',
  AGENT_TOOL_ARGUMENT_PARSE_FAILED: '模型返回的工具参数不是有效 JSON',
  AGENT_MAX_STEPS_EXCEEDED: 'Agent 已达到最大决策轮次，未继续调用模型',
  AGENT_MAX_TOOL_CALLS_EXCEEDED: 'Agent 已达到最大工具调用次数，未继续执行工具'
}

const failure = errCode => ({ errCode, errMsg: ERROR_MESSAGES[errCode] || 'Agent 请求未完成' })
const validQuery = value => typeof value === 'string' && Array.from(value.trim()).length >= 1 && Array.from(value.trim()).length <= 200

function normalizeError(error) {
  return failure(error?.code && Object.hasOwn(ERROR_MESSAGES, error.code)
    ? error.code
    : 'AGENT_MODEL_RESPONSE_INVALID')
}

async function runAgent(query, options = {}) {
  if (!validQuery(query)) return failure('AGENT_QUERY_INVALID')
  const cleanQuery = query.trim()
  const {
    db,
    httpclient,
    env = process.env,
    includeTrace = false,
    modelClient = callAgentModel
  } = options

  let config
  try { config = readAgentConfig(env) }
  catch (error) { return normalizeError(error) }

  const tools = getToolDefinitions()
  const messages = [
    { role: 'system', content: SYSTEM_PROMPT },
    { role: 'user', content: cleanQuery }
  ]
  const trace = []
  let totalToolCalls = 0

  for (let step = 1; step <= MAX_AGENT_STEPS; step += 1) {
    let decision
    try { decision = await modelClient({ httpclient, config, messages, tools }) }
    catch (error) { return normalizeError(error) }

    if (decision?.type === 'final' && typeof decision.content === 'string' && decision.content.trim()) {
      const result = { errCode: 0, query: cleanQuery, answer: decision.content.trim(), completed: true }
      if (includeTrace) result.trace = trace
      return result
    }
    const assistant = decision?.type === 'tool_calls' && decision.message
    const toolCalls = assistant?.tool_calls
    if (!assistant || assistant.role !== 'assistant' || !Array.isArray(toolCalls) || toolCalls.length === 0) {
      return failure('AGENT_MODEL_RESPONSE_INVALID')
    }
    if (toolCalls.some(call => !call || call.type !== 'function' || typeof call.id !== 'string' ||
        !call.id || !call.function || typeof call.function.name !== 'string' ||
        typeof call.function.arguments !== 'string')) return failure('AGENT_MODEL_RESPONSE_INVALID')
    if (totalToolCalls + toolCalls.length > MAX_TOOL_CALLS) return failure('AGENT_MAX_TOOL_CALLS_EXCEEDED')

    // 原样保留经过模型客户端白名单清洗的 assistant tool_calls，供下一轮协议关联。
    messages.push(assistant)
    for (const call of toolCalls) {
      let args
      try { args = JSON.parse(call.function.arguments) }
      catch { return failure('AGENT_TOOL_ARGUMENT_PARSE_FAILED') }

      totalToolCalls += 1
      trace.push({ step, type: 'tool_call', toolName: call.function.name, arguments: args })
      const toolResult = await executeTool(call.function.name, args, { db })
      if (toolResult.errCode !== 0) return toolResult
      trace.push({ step, type: 'tool_result', toolName: call.function.name, result: toolResult })
      messages.push({
        role: 'tool',
        tool_call_id: call.id,
        content: JSON.stringify(toolResult)
      })
    }
  }
  return failure('AGENT_MAX_STEPS_EXCEEDED')
}

module.exports = { MAX_AGENT_STEPS, MAX_TOOL_CALLS, SYSTEM_PROMPT, runAgent }
