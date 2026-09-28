import { ref } from 'vue'
import { defineStore } from 'pinia'
import { executePendingCartAction } from '../services/agent'
import { createConversation, getConversationMessages, runFrameworkAgent } from '../services/framework-agent'
import { getDishes } from '../services/menu'
import { useCartStore } from './cart'

export const ASSISTANT_SESSION_STORAGE_KEY = 'framework_agent_conversation_v1'

let messageSequence = 0

function nextMessageId() {
  messageSequence += 1
  return `assistant-message-${Date.now()}-${messageSequence}`
}

function readStoredSession() {
  try {
    const value = uni.getStorageSync(ASSISTANT_SESSION_STORAGE_KEY)
    return value && typeof value.threadId === 'string' &&
      typeof value.conversationToken === 'string' ? value : null
  } catch {
    return null
  }
}

function saveStoredSession(session) {
  // capability 只保存在本机 storage，不打印、不进入 URL 或页面消息。
  uni.setStorageSync(ASSISTANT_SESSION_STORAGE_KEY, {
    threadId: session.threadId,
    conversationToken: session.conversationToken
  })
}

function clearStoredSession() {
  uni.removeStorageSync(ASSISTANT_SESSION_STORAGE_KEY)
}

function historyMessage(message) {
  return { id: nextMessageId(), role: message.role, content: message.content, status: 'sent' }
}

export const useAssistantStore = defineStore('assistant', () => {
  const cartStore = useCartStore()
  const threadId = ref('')
  const conversationToken = ref('')
  const messages = ref([])
  const sending = ref(false)
  const loadingHistory = ref(false)
  const pendingAction = ref(null)
  const actionProcessingId = ref('')
  const error = ref('')
  const conversationInvalid = ref(false)

  function clearUiState() {
    messages.value = []
    pendingAction.value = null
    actionProcessingId.value = ''
    error.value = ''
    conversationInvalid.value = false
  }

  async function createSession() {
    const session = await createConversation()
    threadId.value = session.threadId
    conversationToken.value = session.conversationToken
    saveStoredSession(session)
  }

  async function initializeConversation() {
    if (loadingHistory.value || sending.value) return
    loadingHistory.value = true
    error.value = ''
    pendingAction.value = null
    try {
      const saved = readStoredSession()
      if (!saved) {
        clearUiState()
        await createSession()
        return
      }
      threadId.value = saved.threadId
      conversationToken.value = saved.conversationToken
      const history = await getConversationMessages(threadId.value, conversationToken.value)
      messages.value = history.messages.map(historyMessage)
      conversationInvalid.value = false
    } catch (requestError) {
      if (requestError?.accessDenied) {
        messages.value = []
        conversationInvalid.value = true
        error.value = '当前会话已失效，请新建对话。'
      } else {
        error.value = requestError?.message || '会话暂时无法加载，请稍后重试。'
      }
    } finally {
      loadingHistory.value = false
    }
  }

  async function startNewConversation() {
    if (loadingHistory.value || sending.value || actionProcessingId.value) return
    loadingHistory.value = true
    clearStoredSession()
    threadId.value = ''
    conversationToken.value = ''
    clearUiState()
    try {
      await createSession()
    } catch (requestError) {
      error.value = requestError?.message || '无法创建新会话，请稍后重试。'
    } finally {
      loadingHistory.value = false
    }
  }

  function expireOldActions() {
    messages.value.forEach(message => {
      if (message.actionStatus === 'pending') message.actionStatus = 'expired'
    })
    pendingAction.value = null
  }

  async function sendMessage(query) {
    if (sending.value || loadingHistory.value || actionProcessingId.value || conversationInvalid.value ||
        !threadId.value || !conversationToken.value) return false
    const text = typeof query === 'string' ? query.trim() : ''
    if (!text || Array.from(text).length > 200) {
      error.value = '请输入 1～200 字的问题。'
      return false
    }

    expireOldActions()
    error.value = ''
    messages.value.push({ id: nextMessageId(), role: 'user', content: text, status: 'sent' })
    sending.value = true
    try {
      const response = await runFrameworkAgent(text, threadId.value, conversationToken.value)
      const assistantMessage = {
        id: nextMessageId(),
        role: 'assistant',
        content: response.answer,
        status: 'sent'
      }
      if (response.pendingAction) {
        assistantMessage.pendingAction = response.pendingAction
        assistantMessage.actionStatus = 'pending'
        pendingAction.value = response.pendingAction
      }
      messages.value.push(assistantMessage)
      return true
    } catch (requestError) {
      const message = requestError?.accessDenied
        ? '当前会话已失效，请新建对话。'
        : '请求失败，请重试。'
      messages.value.push({
        id: nextMessageId(),
        role: 'assistant',
        content: message,
        status: 'error'
      })
      if (requestError?.accessDenied) {
        conversationInvalid.value = true
        error.value = message
      }
      return false
    } finally {
      sending.value = false
    }
  }

  async function confirmPendingAction(messageId) {
    if (sending.value || actionProcessingId.value) return false
    const message = messages.value.find(item => item.id === messageId)
    if (!message?.pendingAction || message.actionStatus !== 'pending') return false

    actionProcessingId.value = messageId
    message.actionError = ''
    try {
      const executed = await executePendingCartAction(message.pendingAction, {
        loadDishes: getDishes,
        addDish: (dish, quantity) => cartStore.addDish(dish, quantity)
      })
      message.actionStatus = 'added'
      message.actionResult = `已加入购物车：${executed.name} × ${executed.quantity}`
      pendingAction.value = null
      return true
    } catch (actionError) {
      message.actionError = actionError?.message || '暂时无法加入购物车，请重试。'
      if (actionError?.invalidateAction) {
        message.actionStatus = 'invalid'
        pendingAction.value = null
      }
      return false
    } finally {
      actionProcessingId.value = ''
    }
  }

  function cancelPendingAction(messageId) {
    if (sending.value || actionProcessingId.value) return false
    const message = messages.value.find(item => item.id === messageId)
    if (!message?.pendingAction || message.actionStatus !== 'pending') return false
    message.actionStatus = 'cancelled'
    pendingAction.value = null
    return true
  }

  return {
    threadId,
    conversationToken,
    messages,
    sending,
    loadingHistory,
    pendingAction,
    actionProcessingId,
    error,
    conversationInvalid,
    initializeConversation,
    startNewConversation,
    sendMessage,
    confirmPendingAction,
    cancelPendingAction
  }
})
