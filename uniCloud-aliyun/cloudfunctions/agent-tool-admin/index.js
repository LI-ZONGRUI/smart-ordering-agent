// 仅HBuilderX“上传并运行”；不配置URL化、定时器或前端入口。
const safeToolErrors = Object.freeze({
  AGENT_ACTION_DISH_NOT_FOUND: '未找到对应菜品',
  AGENT_ACTION_DISH_UNAVAILABLE: '当前菜品不可用'
})

function getSafeToolError(error) {
  if (!error || typeof error !== 'object') return null
  try {
    const code = Object.hasOwn(error, 'errCode') ? error.errCode : error.code
    return Object.hasOwn(safeToolErrors, code)
      ? { errCode: code, errMsg: safeToolErrors[code] }
      : null
  } catch {
    return null
  }
}

exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'AGENT_TOOL_FORBIDDEN', errMsg: '请在 HBuilderX 上传并运行管理工具云函数' }
  }
  try {
    const agent = uniCloud.importObject('agent')
    return await agent.testTool(event?.toolName, event?.args)
  } catch (error) {
    // 云对象代理会把非零errCode转成异常；仅恢复白名单中的安全业务错误。
    const safeError = getSafeToolError(error)
    if (safeError) return safeError
    return { errCode: 'AGENT_TOOL_EXECUTION_FAILED', errMsg: '工具调用未完成，请检查部署与菜单数据' }
  }
}
