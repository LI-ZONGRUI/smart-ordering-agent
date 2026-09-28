import { FRAMEWORK_AGENT_BASE_URL } from '../config/framework-agent'
import { validatePendingAction } from './agent'

const MAX_QUERY_LENGTH = 200
const REQUEST_TIMEOUT = 45000
const THREAD_ID_PATTERN = /^[A-Za-z0-9_-]{8,128}$/
const TOKEN_PATTERN = /^[A-Za-z0-9_-]{32,256}$/

const SAFE_ERROR_MESSAGES = {
  FRAMEWORK_QUERY_INVALID: '请输入 1～200 字的问题。',
  FRAMEWORK_THREAD_INVALID: '当前会话信息无效，请新建对话。',
  FRAMEWORK_CONVERSATION_INVALID: '当前会话信息无效，请新建对话。',
  FRAMEWORK_CONVERSATION_ACCESS_DENIED: '当前会话已失效，请新建对话。',
  FRAMEWORK_HISTORY_FAILED: '会话历史暂时无法恢复，请稍后重试。',
  FRAMEWORK_CONTEXT_FAILED: '暂时无法理解这条追问，请换一种说法。',
  FRAMEWORK_EXECUTION_TIMEOUT: '助手响应超时，请稍后重试。'
}

function publicError(message, errCode, accessDenied = false) {
  const error = new Error(message)
  error.errCode = errCode
  error.accessDenied = accessDenied
  return error
}

function normalizeBaseUrl() {
  const baseUrl = typeof FRAMEWORK_AGENT_BASE_URL === 'string'
    ? FRAMEWORK_AGENT_BASE_URL.trim().replace(/\/+$/, '')
    : ''
  if (!/^https?:\/\/[^\s/?#@]+(?::\d+)?(?:\/[^\s?#]*)?$/.test(baseUrl)) {
    throw publicError('AI 点餐助手尚未配置，请联系开发人员。', 'FRAMEWORK_CLIENT_CONFIG_INVALID')
  }
  return baseUrl
}

function validateSession(threadId, conversationToken) {
  if (!THREAD_ID_PATTERN.test(threadId || '') || !TOKEN_PATTERN.test(conversationToken || '')) {
    throw publicError('当前会话信息无效，请新建对话。', 'FRAMEWORK_CONVERSATION_INVALID', true)
  }
}

function mapRemoteError(data) {
  const code = typeof data?.errCode === 'string' ? data.errCode : 'FRAMEWORK_REQUEST_FAILED'
  const accessDenied = code === 'FRAMEWORK_CONVERSATION_ACCESS_DENIED' ||
    code === 'FRAMEWORK_CONVERSATION_INVALID' || code === 'FRAMEWORK_THREAD_INVALID'
  return publicError(
    SAFE_ERROR_MESSAGES[code] || 'AI 点餐助手暂时不可用，请稍后重试。',
    code,
    accessDenied
  )
}

function requestFramework(path, { method = 'GET', data, conversationToken } = {}) {
  const header = { 'Content-Type': 'application/json' }
  if (conversationToken) header['X-Conversation-Token'] = conversationToken

  return new Promise((resolve, reject) => {
    try {
      uni.request({
        url: `${normalizeBaseUrl()}${path}`,
        method,
        data,
        header,
        timeout: REQUEST_TIMEOUT,
        success(response) {
          const body = response?.data
          if (!Number.isInteger(response?.statusCode) || response.statusCode < 200 ||
              response.statusCode >= 300 || body?.errCode !== 0) {
            reject(mapRemoteError(body))
            return
          }
          resolve(body)
        },
        fail() {
          // 不把 request config、URL、Header 或 token 拼入错误信息。
          reject(publicError('网络连接失败，请稍后重试。', 'FRAMEWORK_NETWORK_FAILED'))
        }
      })
    } catch {
      // 即使运行时同步抛错，也只向页面暴露固定的安全错误。
      reject(publicError('网络连接失败，请稍后重试。', 'FRAMEWORK_NETWORK_FAILED'))
    }
  })
}

function hasExactKeys(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const actual = Object.keys(value)
  return actual.length === keys.length && actual.every(key => keys.includes(key))
}

export async function createConversation() {
  const response = await requestFramework('/v1/conversations', { method: 'POST' })
  if (!hasExactKeys(response, ['errCode', 'threadId', 'conversationToken']) ||
      !THREAD_ID_PATTERN.test(response.threadId) || !TOKEN_PATTERN.test(response.conversationToken)) {
    throw publicError('无法创建新会话，请稍后重试。', 'FRAMEWORK_RESPONSE_INVALID')
  }
  return { threadId: response.threadId, conversationToken: response.conversationToken }
}

export async function getConversationMessages(threadId, conversationToken) {
  validateSession(threadId, conversationToken)
  const response = await requestFramework(
    `/v1/conversations/${encodeURIComponent(threadId)}/messages`,
    { conversationToken }
  )
  if (!response || response.threadId !== threadId || !Array.isArray(response.messages) ||
      response.messages.length > 100) {
    throw publicError('会话历史返回格式异常，请稍后重试。', 'FRAMEWORK_RESPONSE_INVALID')
  }
  const messages = response.messages.map(message => {
    if (!hasExactKeys(message, ['role', 'content']) ||
        !['user', 'assistant'].includes(message.role) ||
        typeof message.content !== 'string' || !message.content.trim()) {
      throw publicError('会话历史返回格式异常，请稍后重试。', 'FRAMEWORK_RESPONSE_INVALID')
    }
    return { role: message.role, content: message.content }
  })
  return { threadId, messages }
}

export async function runFrameworkAgent(query, threadId, conversationToken) {
  if (typeof query !== 'string') {
    throw publicError(SAFE_ERROR_MESSAGES.FRAMEWORK_QUERY_INVALID, 'FRAMEWORK_QUERY_INVALID')
  }
  const text = query.trim()
  if (!text || Array.from(text).length > MAX_QUERY_LENGTH) {
    throw publicError(SAFE_ERROR_MESSAGES.FRAMEWORK_QUERY_INVALID, 'FRAMEWORK_QUERY_INVALID')
  }
  validateSession(threadId, conversationToken)
  const response = await requestFramework('/v1/agent/run', {
    method: 'POST',
    conversationToken,
    data: { query: text, threadId }
  })
  const allowedKeys = ['errCode', 'query', 'answer', 'completed', 'threadId', 'pendingAction']
  if (!response || Object.keys(response).some(key => !allowedKeys.includes(key)) ||
      response.query !== text || response.threadId !== threadId || response.completed !== true ||
      typeof response.answer !== 'string' || !response.answer.trim()) {
    throw publicError('助手返回格式异常，请重试。', 'FRAMEWORK_RESPONSE_INVALID')
  }
  const result = { query: text, answer: response.answer.trim(), completed: true, threadId }
  if (Object.hasOwn(response, 'pendingAction')) {
    try {
      result.pendingAction = validatePendingAction(response.pendingAction)
    } catch {
      throw publicError('待确认操作无效，请重新发起。', 'FRAMEWORK_RESPONSE_INVALID')
    }
  }
  return result
}
