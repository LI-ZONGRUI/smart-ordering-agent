const menuDomain = require('./menu-domain')
const { createFrameworkGateway } = require('./gateway')

async function ragAnswer(query) {
  // 复用已部署的正式 RAG 能力；Gateway 不复制 Embedding、Retrieval 或 Grounding。
  return uniCloud.importObject('rag').answer(query)
}

async function agentProposeAction(query) {
  // 只调用正式Native Agent入口；Gateway不会暴露管理trace或任何确认后执行能力。
  return uniCloud.importObject('agent').run(query)
}

const handle = createFrameworkGateway({ domain: menuDomain, ragAnswer, agentProposeAction })

exports.main = async (event, context) => {
  // 只允许URL化HTTP入口；callFunction或客户端不能绕过HMAC边界。
  if (context?.SOURCE !== 'http') {
    return { errCode: 'FRAMEWORK_GATEWAY_REQUEST_INVALID', message: '请求格式不正确' }
  }
  return handle(event)
}
