<template>
  <view class="page">
    <view class="title">AI 智能点餐</view>
    <view class="intro muted">告诉我你的预算、口味和不想吃的食材。</view>
    <view class="card">
      <textarea v-model="message" class="request-input" :maxlength="200" :disabled="loading"
        placeholder="例如：想吃辣一点的，预算50元，不要牛肉" />
      <view class="muted counter">{{ message.length }}/200</view>
      <button class="primary-button" :disabled="loading" :loading="loading" @click="submit">
        {{ loading ? '正在挑选菜品...' : '帮我推荐' }}
      </button>
    </view>

    <view v-if="loading" class="card muted">正在根据当前在售菜单生成推荐，请稍候。</view>
    <view v-else-if="error" class="card">
      <view class="error-text">{{ error }}</view>
      <button class="retry-button" @click="submit">重新尝试</button>
    </view>
    <template v-else-if="result">
      <view class="card">
        <view class="section-title">{{ result.recommendations.length ? '为你推荐' : '暂时没有合适的推荐' }}</view>
        <view class="reason">{{ result.reason }}</view>
        <view v-if="result.recommendations.length" class="total">
          每道菜一份，合计 <text class="price">¥{{ result.totalPrice.toFixed(2) }}</text>
        </view>
        <button v-else class="retry-button" @click="submit">重新尝试</button>
      </view>
      <view v-for="dish in result.recommendations" :key="dish.dishId" class="card">
        <view class="dish-row">
          <image :src="dish.image" class="dish-image" mode="aspectFill" />
          <view class="dish-info">
            <view class="dish-name">{{ dish.name }}</view>
            <view class="muted">{{ dish.description }}</view>
            <view class="meta">{{ spicyLevelLabels[dish.spicyLevel] || '辣度未标注' }}</view>
            <view class="price">¥{{ dish.price.toFixed(2) }}</view>
          </view>
        </view>
        <view class="ingredients muted">主要配料：{{ dish.ingredients.join('、') }}</view>
        <button class="primary-button" :disabled="addingId !== ''" :loading="addingId === dish.dishId"
          @click="addToCart(dish)">加入购物车</button>
      </view>
      <button :disabled="addingId !== ''" @click="goToCart">查看购物车</button>
    </template>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { recommendDishes } from '../../services/ai'
import { getDishes } from '../../services/menu'
import { useCartStore } from '../../stores/cart'
import { spicyLevelLabels } from '../../constants/dish'

const cartStore = useCartStore()
const message = ref('')
const loading = ref(false)
const addingId = ref('')
const error = ref('')
const result = ref(null)

async function submit() {
  if (loading.value || addingId.value) return
  const text = message.value.trim()
  if (!text || [...text].length > 200) {
    error.value = '请填写 1～200 字的点餐需求'
    result.value = null
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await recommendDishes(text)
  } catch (err) {
    error.value = err.message // service 已转换为安全、友好的提示。
  } finally {
    loading.value = false
  }
}

async function addToCart(dish) {
  if (addingId.value) return
  addingId.value = dish.dishId
  try {
    // 用户可能停留很久，加购前刷新该菜品的真实价格和状态。
    const currentDish = (await getDishes()).find(item => item.id === dish.dishId)
    if (!currentDish || !cartStore.addDish(currentDish)) {
      uni.showToast({ title: '菜品已下架或售罄，请重新推荐', icon: 'none' })
      return
    }
    // 复用现有 Pinia 加购，AI 后端不操作购物车，也不创建订单。
    uni.showToast({ title: '已加入购物车', icon: 'success' })
  } catch {
    uni.showToast({ title: '暂时无法确认菜品状态，请重试', icon: 'none' })
  } finally {
    addingId.value = ''
  }
}

function goToCart() {
  uni.switchTab({ url: '/pages/cart/index' })
}
</script>

<style scoped>
.intro { margin: 16rpx 0 28rpx; }
.request-input { box-sizing: border-box; width: 100%; height: 200rpx; line-height: 1.6; }
.counter { text-align: right; margin-bottom: 20rpx; }
.reason { line-height: 1.7; white-space: pre-wrap; }
.total { margin-top: 20rpx; }
.dish-row { display: flex; gap: 20rpx; }
.dish-image { width: 160rpx; height: 160rpx; flex-shrink: 0; border-radius: 16rpx; }
.dish-info { flex: 1; min-width: 0; line-height: 1.6; }
.dish-name { font-size: 32rpx; font-weight: 600; }
.meta { margin-top: 12rpx; }
.ingredients { margin: 20rpx 0; line-height: 1.6; }
.error-text { color: #a63e2b; }
.retry-button { margin-top: 20rpx; }
</style>
