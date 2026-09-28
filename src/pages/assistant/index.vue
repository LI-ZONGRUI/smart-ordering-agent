<template>
  <view class="assistant-page">
    <view class="assistant-header">
      <view>
        <view class="assistant-title">AI 点餐助手</view>
        <view class="assistant-subtitle">菜单事实来自实时服务，购物车操作需要你明确确认。</view>
      </view>
      <button class="new-chat-button" size="mini" :disabled="sending || loadingHistory || Boolean(actionProcessingId)"
        @click="startNewConversation">新对话</button>
    </view>

    <scroll-view class="message-list" scroll-y :scroll-into-view="scrollTarget"
      :enhanced="true" :show-scrollbar="false">
      <view v-if="loadingHistory" class="center-state">正在加载会话…</view>

      <view v-else-if="!messages.length && !conversationInvalid" class="welcome-state">
        <view class="welcome-title">你好，我是 AI 点餐助手。</view>
        <view class="welcome-copy">可以连续询问当前菜单、菜品知识，或准备待确认的购物车操作。</view>
        <view class="example-list">
          <button v-for="example in examples" :key="example" size="mini" class="example-chip"
            :disabled="sending || !threadId || Boolean(actionProcessingId)"
            @click="sendExample(example)">{{ example }}</button>
        </view>
      </view>

      <view v-for="message in messages" :key="message.id" class="message-row"
        :class="message.role === 'user' ? 'user-row' : 'assistant-row'">
        <view class="message-bubble" :class="[
          message.role === 'user' ? 'user-bubble' : 'assistant-bubble',
          message.status === 'error' ? 'error-bubble' : ''
        ]">
          <text class="message-content">{{ message.content }}</text>
        </view>

        <view v-if="message.pendingAction" class="action-card">
          <view class="action-title">待确认购物车操作</view>
          <view class="action-name">{{ message.pendingAction.name }} × {{ message.pendingAction.quantity }}</view>
          <view class="action-line"><text>单价</text><text>¥{{ message.pendingAction.unitPrice.toFixed(2) }}</text></view>
          <view class="action-line total-line"><text>合计</text><text>¥{{ message.pendingAction.totalPrice.toFixed(2) }}</text></view>

          <template v-if="message.actionStatus === 'pending'">
            <button class="confirm-button" size="mini"
              :loading="actionProcessingId === message.id"
              :disabled="sending || Boolean(actionProcessingId)"
              @click="confirmAction(message.id)">确认加入购物车</button>
            <button class="cancel-action-button" size="mini"
              :disabled="sending || Boolean(actionProcessingId)"
              @click="cancelAction(message.id)">取消</button>
          </template>
          <view v-else-if="message.actionStatus === 'added'" class="action-success">
            {{ message.actionResult || '已加入购物车。' }}
          </view>
          <view v-else-if="message.actionStatus === 'cancelled'" class="action-muted">已取消</view>
          <view v-else-if="message.actionStatus === 'expired'" class="action-muted">该操作已失效，请重新发起。</view>
          <view v-else-if="message.actionStatus === 'invalid'" class="action-error">{{ message.actionError }}</view>
          <view v-if="message.actionError && message.actionStatus === 'pending'" class="action-error">{{ message.actionError }}</view>
        </view>
      </view>

      <view v-if="sending" class="message-row assistant-row">
        <view class="message-bubble assistant-bubble typing-indicator">正在思考…</view>
      </view>

      <view v-if="error" class="error-state">
        <view>{{ error }}</view>
        <button v-if="conversationInvalid" class="recovery-button" size="mini"
          @click="startNewConversation">新建对话</button>
      </view>
      <view id="message-bottom" class="message-bottom" />
    </scroll-view>

    <view class="composer safe-area-bottom">
      <textarea v-model="input" class="composer-input" :maxlength="200" auto-height
        :disabled="sending || loadingHistory || Boolean(actionProcessingId) || conversationInvalid"
        :adjust-position="true" :cursor-spacing="20" confirm-type="send"
        placeholder="输入消息…" @confirm="send" />
      <button class="send-button" size="mini" :disabled="!canSend" @click="send">发送</button>
    </view>
  </view>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAssistantStore } from '../../stores/assistant'

const assistantStore = useAssistantStore()
const {
  threadId,
  messages,
  sending,
  loadingHistory,
  actionProcessingId,
  error,
  conversationInvalid
} = storeToRefs(assistantStore)

const input = ref('')
const scrollTarget = ref('')
const examples = ['有什么饮品？', '柠檬茶是什么味道？', '推荐点清爽的', '有柠檬茶吗？']
const canSend = computed(() => Boolean(input.value.trim()) && Array.from(input.value.trim()).length <= 200 &&
  Boolean(threadId.value) && !sending.value && !loadingHistory.value && !actionProcessingId.value &&
  !conversationInvalid.value)

function scrollToBottom() {
  scrollTarget.value = ''
  nextTick(() => { scrollTarget.value = 'message-bottom' })
}

async function sendText(text) {
  if (!threadId.value || sending.value || loadingHistory.value || actionProcessingId.value ||
      conversationInvalid.value) return
  const query = typeof text === 'string' ? text.trim() : ''
  if (!query || Array.from(query).length > 200) return
  input.value = ''
  await assistantStore.sendMessage(query)
}

async function send() {
  if (!canSend.value) return
  await sendText(input.value)
}

async function sendExample(example) {
  await sendText(example)
}

async function startNewConversation() {
  input.value = ''
  await assistantStore.startNewConversation()
}

async function confirmAction(messageId) {
  await assistantStore.confirmPendingAction(messageId)
}

function cancelAction(messageId) {
  assistantStore.cancelPendingAction(messageId)
}

watch([() => messages.value.length, sending], scrollToBottom)
onMounted(async () => {
  await assistantStore.initializeConversation()
  scrollToBottom()
})
</script>

<style scoped>
.assistant-page { box-sizing: border-box; display: flex; flex-direction: column; height: 100vh; background: #f4f6f3; }
.assistant-header { display: flex; align-items: center; justify-content: space-between; gap: 20rpx; padding: 24rpx 28rpx; background: #fff; border-bottom: 1rpx solid #e5eae6; }
.assistant-title { font-size: 34rpx; font-weight: 700; color: #243126; }
.assistant-subtitle { margin-top: 6rpx; font-size: 22rpx; color: #728075; line-height: 1.5; }
.new-chat-button { flex-shrink: 0; margin: 0; color: #2d8055; background: #eef5ef; }
.message-list { flex: 1; min-height: 0; padding: 28rpx; box-sizing: border-box; }
.center-state, .error-state { padding: 80rpx 24rpx; color: #728075; text-align: center; }
.welcome-state { margin: 40rpx 0; padding: 34rpx; border-radius: 24rpx; background: #fff; }
.welcome-title { font-size: 34rpx; font-weight: 700; }
.welcome-copy { margin-top: 14rpx; color: #728075; line-height: 1.7; }
.example-list { display: flex; flex-wrap: wrap; gap: 14rpx; margin-top: 28rpx; }
.example-chip { margin: 0; color: #2d8055; background: #eef5ef; font-size: 23rpx; }
.message-row { display: flex; flex-direction: column; margin-bottom: 24rpx; }
.user-row { align-items: flex-end; }
.assistant-row { align-items: flex-start; }
.message-bubble { max-width: 78%; padding: 20rpx 24rpx; border-radius: 22rpx; line-height: 1.7; overflow-wrap: anywhere; }
.user-bubble { color: #fff; background: #2d8055; border-bottom-right-radius: 6rpx; }
.assistant-bubble { color: #243126; background: #fff; border-bottom-left-radius: 6rpx; }
.error-bubble { color: #a63e2b; background: #fff2ef; }
.message-content { white-space: pre-wrap; }
.typing-indicator { color: #728075; }
.action-card { width: 78%; box-sizing: border-box; margin-top: 14rpx; padding: 24rpx; border: 2rpx solid #d9eadf; border-radius: 20rpx; background: #fff; }
.action-title { color: #2d8055; font-size: 24rpx; font-weight: 600; }
.action-name { margin: 16rpx 0; font-size: 32rpx; font-weight: 700; }
.action-line { display: flex; justify-content: space-between; margin: 12rpx 0; }
.total-line { padding-top: 12rpx; border-top: 1rpx solid #e8eee9; font-weight: 600; }
.confirm-button { margin: 22rpx 0 0; color: #fff; background: #2d8055; }
.cancel-action-button { margin: 12rpx 0 0; color: #56645a; background: #f1f3f1; }
.action-success { margin-top: 18rpx; color: #2d8055; }
.action-muted { margin-top: 18rpx; color: #728075; }
.action-error { margin-top: 18rpx; color: #a63e2b; line-height: 1.6; }
.recovery-button { margin-top: 20rpx; color: #fff; background: #2d8055; }
.message-bottom { height: 28rpx; }
.composer { display: flex; align-items: flex-end; gap: 16rpx; padding: 20rpx 24rpx calc(20rpx + env(safe-area-inset-bottom)); background: #fff; border-top: 1rpx solid #e5eae6; }
.composer-input { box-sizing: border-box; flex: 1; min-height: 76rpx; max-height: 200rpx; padding: 18rpx 22rpx; border-radius: 20rpx; background: #f3f5f2; line-height: 1.5; }
.send-button { flex-shrink: 0; margin: 0; color: #fff; background: #2d8055; }
.send-button[disabled] { opacity: 0.5; }
</style>
