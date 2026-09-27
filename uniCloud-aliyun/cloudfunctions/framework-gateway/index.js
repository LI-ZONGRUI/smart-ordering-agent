const menuDomain = require('./menu-domain')
const { createFrameworkGateway } = require('./gateway')

async function ragAnswer(query) {
  // 复用已部署的正式 RAG 能力；Gateway 不复制 Embedding、Retrieval 或 Grounding。
  return uniCloud.importObject('rag').answer(query)
}

const handle = createFrameworkGateway({ domain: menuDomain, ragAnswer })

exports.main = async (event, context) => {
  // 只允许URL化HTTP入口；callFunction或客户端不能绕过HMAC边界。
  if (context?.SOURCE !== 'http') {
    return { errCode: 'FRAMEWORK_GATEWAY_REQUEST_INVALID', message: '请求格式不正确' }
  }
  return handle(event)
}
