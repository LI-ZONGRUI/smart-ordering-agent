const { executeTool } = require('./tools/executor')
const { getToolDefinitions } = require('./tools/registry')
const forbidden = () => ({ errCode: 'AGENT_TOOL_FORBIDDEN', errMsg: '请通过管理云函数执行工具诊断' })

module.exports = {
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
