<template>
  <view class="page confirm-page">
    <view class="section-title">确认订单</view>

    <view v-if="submitting" class="card success-state">
      订单提交成功，正在前往订单列表...
    </view>

    <view v-else-if="itemCount === 0" class="card empty-state">
      <text>购物车还是空的</text>
      <button class="primary-button" size="mini" @click="goToCart">返回购物车</button>
    </view>

    <form v-else @submit="submitOrder">
      <view class="card">
        <view class="card-title">商品明细</view>
        <view v-for="item in items" :key="item.id" class="order-item">
          <view class="item-name">{{ item.name }} × {{ item.quantity }}</view>
          <view class="item-prices">
            <text class="muted">单价 ¥{{ item.price.toFixed(2) }}</text>
            <text>小计 ¥{{ (item.price * item.quantity).toFixed(2) }}</text>
          </view>
        </view>
      </view>

      <view class="card">
        <view class="card-title">订单备注</view>
        <textarea
          v-model="remark"
          name="remark"
          class="remark-input"
          maxlength="200"
          placeholder="例如：少辣、不要香菜"
        />
      </view>

      <view class="card totals">
        <view><text>商品总数量</text><text>{{ itemCount }} 件</text></view>
        <view><text>订单总价</text><text class="price">¥{{ totalPrice.toFixed(2) }}</text></view>
      </view>

      <view v-if="hasUnavailableItems" class="unavailable-tip">
        购物车中有已售罄菜品，请返回购物车删除后再提交。
      </view>

      <button
        class="primary-button submit-button"
        form-type="submit"
        :disabled="hasUnavailableItems || submitting"
      >
        {{ submitting ? '正在提交...' : '提交订单' }}
      </button>
    </form>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useCartStore } from '../../stores/cart'
import { useOrdersStore } from '../../stores/orders'

const cartStore = useCartStore()
const ordersStore = useOrdersStore()
const { items, itemCount, totalPrice, hasUnavailableItems } = storeToRefs(cartStore)
const remark = ref('')
const submitting = ref(false)

function submitOrder(event) {
  if (submitting.value || itemCount.value === 0 || hasUnavailableItems.value) return
  submitting.value = true

  // form 提交时读取备注，可拿到用户点击按钮前输入的最新内容。
  const formRemark = event.detail.value.remark
  const submittedRemark = String(formRemark === undefined ? remark.value : formRemark).trim()
  const order = ordersStore.createOrder(items.value, submittedRemark)
  if (!order) {
    submitting.value = false
    return
  }

  // 订单 store 已保存独立明细，清空购物车不会影响刚生成的订单。
  cartStore.clearCart()
  uni.showToast({ title: '下单成功', icon: 'success', duration: 1200 })
  setTimeout(() => {
    uni.switchTab({ url: '/pages/orders/index' })
  }, 1200)
}

function goToCart() {
  uni.switchTab({ url: '/pages/cart/index' })
}
</script>

<style scoped>
.confirm-page {
  padding-bottom: 48rpx;
}

.card-title {
  margin-bottom: 20rpx;
  font-size: 30rpx;
  font-weight: 600;
}

.order-item {
  padding: 20rpx 0;
  border-top: 1rpx solid #edf0eb;
}

.item-name {
  font-weight: 600;
}

.item-prices,
.totals view {
  display: flex;
  justify-content: space-between;
}

.item-prices {
  margin-top: 12rpx;
  font-size: 24rpx;
}

.remark-input {
  box-sizing: border-box;
  width: 100%;
  height: 150rpx;
  padding: 18rpx;
  border-radius: 12rpx;
  background: #f7f8f5;
  font-size: 26rpx;
}

.totals view + view {
  margin-top: 20rpx;
}

.submit-button {
  margin-top: 26rpx;
}

.unavailable-tip {
  color: #c56a46;
  font-size: 24rpx;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60rpx 28rpx;
}

.empty-state button {
  margin-top: 24rpx;
}

.success-state {
  padding: 64rpx 28rpx;
  color: #2d8055;
  text-align: center;
}
</style>
