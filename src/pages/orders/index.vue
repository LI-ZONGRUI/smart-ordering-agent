<template>
  <view class="page">
    <view class="section-title">我的订单</view>

    <view v-if="orders.length === 0" class="card empty-state">
      <text>暂无订单</text>
      <text class="muted">去菜单挑选喜欢的菜品吧。</text>
      <button size="mini" class="primary-button" @click="goToMenu">去菜单</button>
    </view>

    <view v-for="order in orders" :key="order.id" class="card order-card">
      <view class="order-heading">
        <text class="order-id">订单号 {{ order.id }}</text>
        <text class="status">{{ statusText(order.status) }}</text>
      </view>
      <view class="muted order-time">下单时间 {{ formatTime(order.createTime) }}</view>
      <view class="item-summary">{{ itemSummary(order.items) }}</view>
      <view v-if="order.remark" class="muted remark">备注：{{ order.remark }}</view>
      <view class="order-total">
        <text>共 {{ order.totalCount }} 件</text>
        <text class="price">合计 ¥{{ order.totalPrice.toFixed(2) }}</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { orderStatusLabels, useOrdersStore } from '../../stores/orders'

const ordersStore = useOrdersStore()
const { orders } = storeToRefs(ordersStore)

function statusText(status) {
  // 目前新订单都是 pending；其他状态先准备好显示文案。
  return orderStatusLabels[status] || '未知状态'
}

function itemSummary(items) {
  return items.map((item) => `${item.name} × ${item.quantity}`).join('、')
}

function formatTime(isoTime) {
  const date = new Date(isoTime)
  const twoDigits = (number) => String(number).padStart(2, '0')
  const year = date.getFullYear()
  const month = twoDigits(date.getMonth() + 1)
  const day = twoDigits(date.getDate())
  const hour = twoDigits(date.getHours())
  const minute = twoDigits(date.getMinutes())
  return `${year}-${month}-${day} ${hour}:${minute}`
}

function goToMenu() {
  uni.switchTab({ url: '/pages/menu/index' })
}
</script>

<style scoped>
.order-heading,
.order-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.order-id {
  font-size: 24rpx;
  font-weight: 600;
}

.status {
  color: #2d8055;
  font-size: 24rpx;
}

.order-time {
  margin-top: 14rpx;
  font-size: 22rpx;
}

.item-summary {
  margin: 24rpx 0;
  line-height: 1.6;
}

.remark {
  margin-bottom: 20rpx;
  font-size: 23rpx;
}

.order-total {
  padding-top: 20rpx;
  border-top: 1rpx solid #edf0eb;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64rpx 28rpx;
}

.empty-state .muted {
  margin-top: 20rpx;
}

.empty-state button {
  margin-top: 24rpx;
}
</style>
