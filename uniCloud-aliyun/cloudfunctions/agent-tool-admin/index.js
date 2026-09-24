// 仅HBuilderX“上传并运行”；不配置URL化、定时器或前端入口。
exports.main = async function (event, context) {
  if (context?.SOURCE !== 'server') {
    return { errCode: 'AGENT_TOOL_FORBIDDEN', errMsg: '请在 HBuilderX 上传并运行管理工具云函数' }
  }
  try {
    const agent = uniCloud.importObject('agent')
    return await agent.testTool(event?.toolName, event?.args)
  } catch {
    return { errCode: 'AGENT_TOOL_EXECUTION_FAILED', errMsg: '工具调用未完成，请检查部署与菜单数据' }
  }
}
