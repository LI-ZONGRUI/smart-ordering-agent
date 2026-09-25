<template>
  <view class="page">
    <view class="title">智能点餐 Agent</view>
    <view class="intro muted">可以查询实时菜单，也可以帮你准备加入购物车操作。每次处理一个请求。</view>

    <view class="card">
      <textarea v-model="query" class="query-input" :maxlength="-1" :disabled="loading || confirming"
        placeholder="例如：把柠檬茶加两杯到购物车" />
      <view class="counter muted">{{ queryLength }}/200</view>
      <view class="examples">
        <button v-for="example in examples" :key="example" class="example-chip" size="mini"
          :disabled="loading || confirming" @click="fillExample(example)">{{ example }}</button>
      </view>
      <button class="primary-button" :disabled="loading || confirming" :loading="loading" @click="submitQuery">
        {{ loading ? '处理中...' : '发送请求' }}
      </button>
    </view>

    <view v-if="loading" class="card muted">正在查询实时菜单，请稍候。</view>
    <view v-if="errorMessage" class="card error-text">{{ errorMessage }}</view>

    <view v-if="result" class="card">
      <view class="section-title">点餐助手</view>
      <text class="answer-text">{{ result.answer }}</text>
    </view>

    <view v-if="pendingAction" class="card action-card">
      <view class="section-title">待确认操作</view>
      <view class="action-name">{{ pendingAction.name }}</view>
      <view class="action-line"><text>数量</text><text>× {{ pendingAction.quantity }}</text></view>
      <view class="action-line"><text>单价</text><text>¥{{ pendingAction.unitPrice.toFixed(2) }}</text></view>
      <view class="action-line total-line"><text>合计</text><text class="price">¥{{ pendingAction.totalPrice.toFixed(2) }}</text></view>
      <button class="primary-button" :disabled="loading || confirming" :loading="confirming" @click="confirmAction">
        {{ confirming ? '正在确认菜品...' : '确认加入购物车' }}
      </button>
      <button class="cancel-button" :disabled="loading || confirming" @click="cancelAction">取消</button>
    </view>

    <view v-if="actionStatus" class="card"
      :class="{ 'success-text': actionStatusType === 'success', 'error-text': actionStatusType === 'error' }">
      {{ actionStatus }}
      <button v-if="actionStatusType === 'success'" class="cart-button" @click="goToCart">查看购物车</button>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { runOrderingAgent, executePendingCartAction } from '../../services/agent'
import { getDishes } from '../../services/menu'
import { useCartStore } from '../../stores/cart'

const cartStore = useCartStore()
const query = ref('')
const loading = ref(false)
const result = ref(null)
const errorMessage = ref('')
const pendingAction = ref(null)
const confirming = ref(false)
const actionStatus = ref('')
const actionStatusType = ref('')
const queryLength = computed(() => Array.from(query.value).length)
const examples = ['把柠檬茶加两杯到购物车', '有可乐吗？没有的话推荐别的喝的。', '你好']

function clearPreviousResult() {
  result.value = null
  errorMessage.value = ''
  pendingAction.value = null
  actionStatus.value = ''
  actionStatusType.value = ''
}

function fillExample(example) {
  if (!loading.value && !confirming.value) query.value = example
}

async function submitQuery() {
  if (loading.value || confirming.value) return
  // 新请求先让旧提案失效，避免把旧动作绑定到新的用户输入。
  clearPreviousResult()
  loading.value = true
  try {
    const response = await runOrderingAgent(query.value)
    result.value = response
    pendingAction.value = response.pendingAction || null
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function confirmAction() {
  if (loading.value || confirming.value || !pendingAction.value) return
  confirming.value = true // 必须在第一个await之前设置，阻止双击执行两次。
  actionStatus.value = ''
  actionStatusType.value = ''
  const action = pendingAction.value
  try {
    const executed = await executePendingCartAction(action, {
      loadDishes: getDishes,
      addDish: (dish, quantity) => cartStore.addDish(dish, quantity)
    })
    pendingAction.value = null
    actionStatus.value = `已加入购物车：${executed.name} × ${executed.quantity}`
    actionStatusType.value = 'success'
  } catch (error) {
    if (error.invalidateAction) pendingAction.value = null
    actionStatus.value = error.message
    actionStatusType.value = 'error'
  } finally {
    confirming.value = false
  }
}

function cancelAction() {
  if (loading.value || confirming.value || !pendingAction.value) return
  pendingAction.value = null
  actionStatus.value = '已取消。'
  actionStatusType.value = 'cancelled'
}

function goToCart() {
  uni.switchTab({ url: '/pages/cart/index' })
}
</script>

<style scoped>
.intro { margin: 16rpx 0 28rpx; line-height: 1.6; }
.query-input { box-sizing: border-box; width: 100%; height: 190rpx; line-height: 1.6; }
.counter { margin: 12rpx 0; text-align: right; }
.examples { display: flex; flex-wrap: wrap; gap: 12rpx; margin-bottom: 24rpx; }
.example-chip { margin: 0; color: #2d8055; background: #eef5ef; font-size: 24rpx; }
.answer-text { display: block; white-space: pre-wrap; line-height: 1.8; overflow-wrap: anywhere; }
.action-card { border: 2rpx solid #d9eadf; }
.action-name { margin-bottom: 20rpx; font-size: 34rpx; font-weight: 600; }
.action-line { display: flex; justify-content: space-between; margin: 14rpx 0; }
.total-line { padding-top: 14rpx; border-top: 1rpx solid #e8eee9; }
.cancel-button, .cart-button { margin-top: 16rpx; }
.error-text { color: #a63e2b; }
.success-text { color: #2d8055; }
</style>
