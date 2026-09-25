<template>
  <view class="page">
    <view class="title">智能点餐 Agent</view>
    <view class="intro muted">可以查询实时菜单，也可以帮你准备加入购物车操作。每次处理一个请求。</view>

    <view class="card">
      <textarea v-model="query" class="query-input" :maxlength="-1" :disabled="loading || confirming || orderPreviewLoading || submittingOrder"
        placeholder="例如：把柠檬茶加两杯到购物车" />
      <view class="counter muted">{{ queryLength }}/200</view>
      <view class="examples">
        <button v-for="example in examples" :key="example" class="example-chip" size="mini"
          :disabled="loading || confirming || orderPreviewLoading || submittingOrder" @click="fillExample(example)">{{ example }}</button>
      </view>
      <button class="primary-button" :disabled="loading || confirming || orderPreviewLoading || submittingOrder" :loading="loading" @click="submitQuery">
        {{ loading ? '处理中...' : '发送请求' }}
      </button>
    </view>

    <view v-if="loading" class="card muted">正在查询实时菜单，请稍候。</view>
    <view v-if="errorMessage" class="card error-text">{{ errorMessage }}</view>

    <view v-if="result" class="card">
      <view class="section-title">点餐助手</view>
      <text class="answer-text">{{ result.answer }}</text>
    </view>

    <view v-if="cartPendingAction" class="card action-card">
      <view class="section-title">待确认操作</view>
      <view class="action-name">{{ cartPendingAction.name }}</view>
      <view class="action-line"><text>数量</text><text>× {{ cartPendingAction.quantity }}</text></view>
      <view class="action-line"><text>单价</text><text>¥{{ cartPendingAction.unitPrice.toFixed(2) }}</text></view>
      <view class="action-line total-line"><text>合计</text><text class="price">¥{{ cartPendingAction.totalPrice.toFixed(2) }}</text></view>
      <button class="primary-button" :disabled="loading || confirming || submittingOrder" :loading="confirming" @click="confirmAction">
        {{ confirming ? '正在确认菜品...' : '确认加入购物车' }}
      </button>
      <button class="cancel-button" :disabled="loading || confirming || submittingOrder" @click="cancelAction">取消</button>
    </view>

    <view v-if="actionStatus" class="card"
      :class="{ 'success-text': actionStatusType === 'success', 'error-text': actionStatusType === 'error' }">
      {{ actionStatus }}
      <button v-if="actionStatusType === 'success'" class="cart-button" @click="goToCart">查看购物车</button>
    </view>

    <view class="card checkout-card">
      <view class="section-title">当前购物车</view>
      <view class="muted">{{ cartItemCount > 0 ? `共 ${cartItemCount} 件商品` : '购物车为空' }}</view>
      <button class="primary-button checkout-button"
        :disabled="cartItemCount === 0 || loading || confirming || orderPreviewLoading || submittingOrder"
        :loading="orderPreviewLoading" @click="generateOrderPreview">
        {{ orderPreviewLoading ? '正在生成...' : '生成订单预览' }}
      </button>
    </view>

    <view v-if="orderPendingAction" class="card order-card">
      <view class="section-title">订单预览</view>
      <view v-for="item in orderPendingAction.items" :key="item.dishId" class="order-item">
        <view class="action-line"><text class="order-name">{{ item.name }} × {{ item.quantity }}</text></view>
        <view class="action-line muted"><text>单价 ¥{{ item.unitPrice.toFixed(2) }}</text><text>小计 ¥{{ item.lineTotal.toFixed(2) }}</text></view>
      </view>
      <view class="action-line"><text>商品总数量</text><text>{{ orderPendingAction.totalQuantity }} 件</text></view>
      <view class="action-line total-line"><text>合计</text><text class="price">¥{{ orderPendingAction.totalPrice.toFixed(2) }}</text></view>
      <view class="proposal-tip muted">{{ orderProposalConfirmed ? '订单信息已确认。请再次明确确认后创建订单。' : '先确认当前预览信息，再进行最终下单。' }}</view>
      <button v-if="!orderProposalConfirmed" class="primary-button"
        :disabled="loading || confirming || orderPreviewLoading || submittingOrder"
        @click="confirmOrderProposal">确认订单信息</button>
      <button v-else class="primary-button" :disabled="submittingOrder" :loading="submittingOrder"
        @click="submitConfirmedOrder">{{ submittingOrder ? '正在创建订单...' : '确认下单' }}</button>
      <button class="cancel-button" :disabled="loading || confirming || orderPreviewLoading || submittingOrder"
        @click="cancelOrderProposal">取消</button>
    </view>

    <view v-if="orderStatus" class="card"
      :class="{ 'success-text': orderStatusType === 'success', 'error-text': orderStatusType === 'error' }">
      {{ orderStatus }}
      <view v-if="createdOrderNo" class="order-number">订单号：{{ createdOrderNo }}</view>
      <button v-if="createdOrderNo" class="cart-button" @click="goToOrders">查看订单</button>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { runOrderingAgent, executePendingCartAction } from '../../services/agent'
import { getDishes } from '../../services/menu'
import { createConfirmedOrder, isSameCartSnapshot, previewOrder } from '../../services/orders'
import { useCartStore } from '../../stores/cart'

const cartStore = useCartStore()
const query = ref('')
const loading = ref(false)
const result = ref(null)
const errorMessage = ref('')
const cartPendingAction = ref(null)
const confirming = ref(false)
const actionStatus = ref('')
const actionStatusType = ref('')
const orderPreviewLoading = ref(false)
const orderPendingAction = ref(null)
const orderCartSnapshot = ref([])
const orderProposalConfirmed = ref(false)
const orderStatus = ref('')
const orderStatusType = ref('')
const submittingOrder = ref(false)
const createdOrderNo = ref('')
const cartItems = computed(() => Array.isArray(cartStore.items) ? cartStore.items : [])
const cartItemCount = computed(() => cartItems.value.reduce((sum, item) => sum + item.quantity, 0))
const queryLength = computed(() => Array.from(query.value).length)
const examples = ['把柠檬茶加两杯到购物车', '有可乐吗？没有的话推荐别的喝的。', '你好']

function clearPreviousResult() {
  result.value = null
  errorMessage.value = ''
  cartPendingAction.value = null
  actionStatus.value = ''
  actionStatusType.value = ''
  clearOrderProposal()
  orderStatus.value = ''
  orderStatusType.value = ''
  createdOrderNo.value = ''
}

function clearOrderProposal() {
  orderPendingAction.value = null
  orderCartSnapshot.value = []
  orderProposalConfirmed.value = false
}

function fillExample(example) {
  if (!loading.value && !confirming.value && !orderPreviewLoading.value && !submittingOrder.value) query.value = example
}

async function submitQuery() {
  if (loading.value || confirming.value || orderPreviewLoading.value || submittingOrder.value) return
  // 新请求先让旧提案失效，避免把旧动作绑定到新的用户输入。
  clearPreviousResult()
  loading.value = true
  try {
    const response = await runOrderingAgent(query.value)
    result.value = response
    cartPendingAction.value = response.pendingAction || null
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}

async function confirmAction() {
  if (loading.value || confirming.value || submittingOrder.value || !cartPendingAction.value) return
  confirming.value = true // 必须在第一个await之前设置，阻止双击执行两次。
  actionStatus.value = ''
  actionStatusType.value = ''
  const action = cartPendingAction.value
  try {
    const executed = await executePendingCartAction(action, {
      loadDishes: getDishes,
      addDish: (dish, quantity) => cartStore.addDish(dish, quantity)
    })
    cartPendingAction.value = null
    actionStatus.value = `已加入购物车：${executed.name} × ${executed.quantity}`
    actionStatusType.value = 'success'
  } catch (error) {
    if (error.invalidateAction) cartPendingAction.value = null
    actionStatus.value = error.message
    actionStatusType.value = 'error'
  } finally {
    confirming.value = false
  }
}

function cancelAction() {
  if (loading.value || confirming.value || submittingOrder.value || !cartPendingAction.value) return
  cartPendingAction.value = null
  actionStatus.value = '已取消。'
  actionStatusType.value = 'cancelled'
}

async function generateOrderPreview() {
  if (loading.value || confirming.value || orderPreviewLoading.value || submittingOrder.value || cartItemCount.value === 0) return
  clearOrderProposal()
  orderStatus.value = ''
  orderStatusType.value = ''
  createdOrderNo.value = ''
  orderPreviewLoading.value = true
  try {
    const preview = await previewOrder(cartItems.value)
    orderPendingAction.value = preview.orderPendingAction
    orderCartSnapshot.value = preview.cartSnapshot
  } catch (error) {
    clearOrderProposal()
    orderStatus.value = error.message
    orderStatusType.value = 'error'
  } finally {
    orderPreviewLoading.value = false
  }
}

function confirmOrderProposal() {
  if (loading.value || confirming.value || orderPreviewLoading.value || submittingOrder.value ||
      !orderPendingAction.value || orderProposalConfirmed.value) return
  // 确认前重读Pinia购物车；菜品或数量变化都会让旧的服务端预览失效。
  if (!isSameCartSnapshot(cartItems.value, orderCartSnapshot.value)) {
    clearOrderProposal()
    orderStatus.value = '购物车已发生变化，请重新生成订单预览。'
    orderStatusType.value = 'error'
    return
  }
  orderProposalConfirmed.value = true
  orderStatus.value = '订单信息已确认，尚未创建订单。'
  orderStatusType.value = 'success'
}

function cancelOrderProposal() {
  if (loading.value || confirming.value || orderPreviewLoading.value || submittingOrder.value || !orderPendingAction.value) return
  clearOrderProposal()
  orderStatus.value = '已取消订单预览。'
  orderStatusType.value = 'cancelled'
}

async function submitConfirmedOrder() {
  if (loading.value || confirming.value || orderPreviewLoading.value || submittingOrder.value ||
      !orderPendingAction.value || !orderProposalConfirmed.value) return
  // 最终写入前再次比较当前购物车，旧Preview不能用于已变化的Cart。
  if (!isSameCartSnapshot(cartItems.value, orderCartSnapshot.value)) {
    clearOrderProposal()
    orderStatus.value = '购物车已发生变化，请重新生成订单预览。'
    orderStatusType.value = 'error'
    return
  }

  submittingOrder.value = true // 在第一个await前设置，防止双击产生两次客户端请求。
  orderStatus.value = ''
  orderStatusType.value = ''
  try {
    const created = await createConfirmedOrder(cartItems.value, orderPendingAction.value, '')
    // 只有服务端确认已经持久化成功后，才通过现有Store API清空购物车。
    cartStore.clearCart()
    clearOrderProposal()
    createdOrderNo.value = created.orderNo
    orderStatus.value = '下单成功'
    orderStatusType.value = 'success'
  } catch (error) {
    if (error.invalidateProposal) clearOrderProposal()
    orderStatus.value = error.message
    orderStatusType.value = 'error'
  } finally {
    submittingOrder.value = false
  }
}

function goToCart() {
  uni.switchTab({ url: '/pages/cart/index' })
}

function goToOrders() {
  uni.switchTab({ url: '/pages/orders/index' })
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
.checkout-button { margin-top: 22rpx; }
.order-card { border: 2rpx solid #d9eadf; }
.order-item { padding: 16rpx 0; border-bottom: 1rpx solid #e8eee9; }
.order-name { font-weight: 600; }
.proposal-tip { margin: 20rpx 0; line-height: 1.6; }
.order-number { margin-top: 16rpx; font-weight: 600; }
.error-text { color: #a63e2b; }
.success-text { color: #2d8055; }
</style>
