<template>
  <view v-if="dish" class="detail-page">
    <image class="detail-image" :src="dish.image" mode="aspectFill" />

    <view class="detail-content">
      <view class="dish-title">{{ dish.name }}</view>
      <view class="dish-summary">
        <text class="price">¥{{ dish.price.toFixed(2) }}</text>
        <text class="muted">月售 {{ dish.sales }}</text>
      </view>

      <view class="info-card">
        <view class="section-title">菜品介绍</view>
        <text>{{ dish.description }}</text>
      </view>

      <view class="info-card">
        <view class="info-row">
          <text class="info-label">主要配料</text>
          <text class="info-value">{{ dish.ingredients.join('、') }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">辣度</text>
          <text class="info-value">{{ spicyText }}</text>
        </view>
      </view>

      <view class="info-card quantity-row">
        <text class="info-label">选择数量</text>
        <view class="quantity-controls">
          <button size="mini" @click="decreaseQuantity">−</button>
          <text>{{ quantity }}</text>
          <button size="mini" @click="increaseQuantity">+</button>
        </view>
      </view>
    </view>

    <view class="bottom-bar">
      <button
        class="primary-button add-cart-button"
        :disabled="dish.status === 'sold_out'"
        @click="addToCart"
      >
        {{ addButtonText }}
      </button>
    </view>
  </view>

  <view v-else class="page missing-state">
    <text>{{ loading ? '正在加载菜品...' : loadError || '菜品不存在' }}</text>
    <button v-if="!loading && loadError" class="primary-button" @click="loadDish">重试</button>
    <button class="primary-button" @click="goToMenu">返回菜单</button>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { spicyLevelLabels } from '../../constants/dish'
import { getDishes } from '../../services/menu'
import { useCartStore } from '../../stores/cart'

const cartStore = useCartStore()
const dish = ref(null)
const quantity = ref(1)
const loading = ref(true)
const loadError = ref('')
let dishId = ''

onLoad((options) => {
  dishId = String(options?.id || '')
  loadDish()
})

async function loadDish() {
  loading.value = true
  loadError.value = ''
  dish.value = null
  try {
    const dishes = await getDishes()
    // URL 只传 _id，详情内容仍从云端获取。
    dish.value = dishes.find((item) => item.id === dishId) || null
  } catch (error) {
    loadError.value = error?.message || '云端菜品加载失败'
  } finally {
    loading.value = false
  }
}

const spicyText = computed(() =>
  dish.value ? spicyLevelLabels[dish.value.spicyLevel] || '辣度未标注' : ''
)

const addButtonText = computed(() => {
  if (!dish.value || dish.value.status === 'sold_out') return '已售罄'
  return `加入购物车 · ¥${(dish.value.price * quantity.value).toFixed(2)}`
})

function decreaseQuantity() {
  if (quantity.value > 1) quantity.value -= 1
}

function increaseQuantity() {
  if (quantity.value < 99) quantity.value += 1
}

function addToCart() {
  if (!dish.value || dish.value.status === 'sold_out') return
  const added = cartStore.addDish(dish.value, quantity.value)
  uni.showToast({ title: added ? `已加入 ${quantity.value} 份` : '菜品已售罄', icon: 'none' })
}

function goToMenu() {
  uni.switchTab({ url: '/pages/menu/index' })
}
</script>

<style scoped>
.detail-page {
  box-sizing: border-box;
  min-height: 100vh;
  padding-bottom: 166rpx;
  background: #f7f8f5;
}

.detail-image {
  width: 100%;
  height: 560rpx;
  background: #f0eadf;
}

.detail-content {
  position: relative;
  margin-top: -30rpx;
  padding: 34rpx 28rpx;
  border-radius: 30rpx 30rpx 0 0;
  background: #f7f8f5;
}

.dish-title {
  font-size: 42rpx;
  font-weight: 700;
}

.dish-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 18rpx 0 30rpx;
}

.dish-summary .price {
  font-size: 38rpx;
}

.info-card {
  margin-bottom: 22rpx;
  padding: 28rpx;
  border-radius: 18rpx;
  background: #ffffff;
}

.info-card .section-title {
  margin-bottom: 14rpx;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 14rpx 0;
}

.info-label {
  flex-shrink: 0;
  color: #728075;
}

.info-value {
  margin-left: 24rpx;
  text-align: right;
}

.quantity-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.quantity-controls {
  display: flex;
  align-items: center;
}

.quantity-controls button {
  width: 62rpx;
  height: 62rpx;
  margin: 0;
  padding: 0;
  line-height: 60rpx;
}

.quantity-controls text {
  min-width: 52rpx;
  text-align: center;
}

.bottom-bar {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  box-sizing: border-box;
  padding: 16rpx 28rpx calc(16rpx + env(safe-area-inset-bottom));
  background: #ffffff;
  box-shadow: 0 -8rpx 28rpx rgba(22, 41, 27, 0.07);
}

.add-cart-button {
  width: 100%;
}

.missing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 120rpx;
}

.missing-state button {
  margin-top: 30rpx;
}
</style>
