const { executeTool } = require('./tools/executor')
const { getToolDefinitions } = require('./tools/registry')
const { runAgent } = require('./runner')
const forbidden = () => ({ errCode: 'AGENT_TOOL_FORBIDDEN', errMsg: '请通过管理云函数执行工具诊断' })

function dependencies(includeTrace) {
  return {
    db: uniCloud.database(),
    httpclient: uniCloud.httpclient,
    includeTrace
  }
}

module.exports = {
  // 正式单次任务接口：只返回最终回答，不暴露messages、trace或模型原始响应。
  async run(query) {
    return runAgent(query, dependencies(false))
  },

  // 仅供HBuilderX管理云函数验收；与正式run复用同一个runner。
  async runForAdmin(query) {
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) return forbidden()
    return runAgent(query, dependencies(true))
  },

  async testTool(toolName, args) {
    // 仅平台提供的云函数/服务端来源；不接收用户声明的source或数据库依赖。
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) return forbidden()
    try {
      return await executeTool(toolName, args, { db: uniCloud.database() })
    } catch {
      return { errCode: 'AGENT_TOOL_EXECUTION_FAILED', errMsg: '工具执行失败，请检查菜单数据或稍后重试' }
    }
  },

  async getToolDefinitions() {
    if (!['function', 'server'].includes(this.getClientInfo?.().source)) return forbidden()
    return { errCode: 0, tools: getToolDefinitions() }
  }
}
