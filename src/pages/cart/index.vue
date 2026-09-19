<template>
  <view class="page cart-page">
    <view class="page-heading">
      <view class="section-title">购物车</view>
      <text v-if="itemCount > 0" class="muted">共 {{ itemCount }} 件</text>
    </view>

    <view v-if="itemCount === 0" class="card empty-state">
      <text>购物车还是空的</text>
      <text class="muted empty-tip">去菜单页选几道菜吧。</text>
      <button size="mini" class="primary-button" @click="goToMenu">去菜单</button>
    </view>

    <template v-else>
      <view v-if="refreshError" class="unavailable-tip">{{ refreshError }}</view>
      <view v-for="item in items" :key="item.id" class="card cart-item">
        <view class="item-top">
          <view>
            <text class="item-name">{{ item.name }}</text>
            <text v-if="!cartStore.isDishAvailable(item.id)" class="sold-out">已售罄</text>
          </view>
          <button size="mini" class="delete-button" @click="cartStore.removeDish(item.id)">删除</button>
        </view>
        <view class="item-bottom">
          <view>
            <text class="price">¥{{ item.price.toFixed(2) }} / 份</text>
            <view class="subtotal">小计 ¥{{ (item.price * item.quantity).toFixed(2) }}</view>
          </view>
          <view class="quantity-controls">
            <button size="mini" @click="cartStore.changeQuantity(item.id, -1)">−</button>
            <text>{{ item.quantity }}</text>
            <button
              size="mini"
              :disabled="!cartStore.isDishAvailable(item.id)"
              @click="cartStore.changeQuantity(item.id, 1)"
            >+</button>
          </view>
        </view>
      </view>

      <view v-if="hasUnavailableItems" class="unavailable-tip">
        购物车中有已售罄菜品，请先删除再结算。
      </view>

      <view class="card summary">
        <text>商品总数量：{{ itemCount }}</text>
        <text class="price">合计 ¥{{ totalPrice.toFixed(2) }}</text>
      </view>
      <button class="clear-button" @click="cartStore.clearCart()">清空购物车</button>
      <button class="primary-button checkout-button" :disabled="hasUnavailableItems" @click="goCheckout">
        去结算
      </button>
    </template>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { onShow } from '@dcloudio/uni-app'
import { getDishes } from '../../services/menu'
import { useCartStore } from '../../stores/cart'

const cartStore = useCartStore()
// 从 store 中取出响应式状态时使用 storeToRefs，避免失去响应性。
const { items, itemCount, totalPrice, hasUnavailableItems } = storeToRefs(cartStore)
const refreshError = ref('')

onShow(async () => {
  if (itemCount.value === 0) return
  try {
    refreshError.value = ''
    cartStore.syncDishes(await getDishes())
  } catch (error) {
    refreshError.value = '暂时无法更新菜品状态，提交订单时云端会再次检查。'
  }
})

function goToMenu() {
  uni.switchTab({ url: '/pages/menu/index' })
}

function goCheckout() {
  if (itemCount.value === 0 || hasUnavailableItems.value) return
  // 确认订单页不是 TabBar 页面，用 navigateTo 保留返回购物车的路径。
  uni.navigateTo({ url: '/pages/order-confirm/index' })
}
</script>

<style scoped>
.cart-page {
  padding-bottom: 48rpx;
}

.page-heading,
.item-top,
.item-bottom,
.summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-heading .section-title {
  margin-bottom: 24rpx;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 28rpx;
}

.empty-tip {
  margin: 20rpx 0;
  font-size: 24rpx;
}

.item-name {
  font-weight: 600;
}

.sold-out {
  margin-left: 14rpx;
  color: #c56a46;
  font-size: 22rpx;
}

.delete-button {
  margin: 0;
  color: #728075;
  background: #f5f6f3;
}

.item-bottom {
  margin-top: 28rpx;
}

.subtotal {
  margin-top: 8rpx;
  color: #879388;
  font-size: 22rpx;
}

.quantity-controls {
  display: flex;
  align-items: center;
}

.quantity-controls button {
  margin: 0;
}

.quantity-controls text {
  margin: 0 14rpx;
}

.clear-button {
  color: #728075;
  background: #ffffff;
}

.checkout-button {
  margin-top: 20rpx;
}

.unavailable-tip {
  margin: 12rpx 0 24rpx;
  color: #c56a46;
  font-size: 24rpx;
}
</style>
