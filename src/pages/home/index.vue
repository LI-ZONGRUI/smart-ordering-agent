<template>
  <view class="page">
    <view class="card welcome-card">
      <text class="title">欢迎点餐</text>
      <text class="welcome-copy">从云端菜单挑选菜品，完成点餐。</text>
      <button class="primary-button menu-button" @click="goToMenu">浏览菜单</button>
    </view>

    <view class="card">
      <view class="section-title">AI 智能点餐</view>
      <text class="muted">说说预算和口味，从当前在售菜品中获得推荐。</text>
      <button class="primary-button menu-button" @click="goToAi">AI 智能点餐</button>
    </view>

    <view class="card">
      <view class="section-title">菜单问答</view>
      <text class="muted">问问菜品口味、配料和介绍</text>
      <button class="primary-button menu-button" @click="goToMenuQuestion">菜单问答</button>
    </view>

    <view class="card">
      <view class="section-title">现在可以体验</view>
      <text class="muted">浏览云端菜品、加入购物车、提交订单，再到订单页查看记录。</text>
    </view>
  </view>
</template>

<script setup>
function goToMenuQuestion() {
  uni.navigateTo({ url: '/pages/rag-qa/index' })
}

function goToAi() {
  uni.navigateTo({ url: '/pages/ai-recommend/index' })
}

function goToMenu() {
  // TabBar 页面要用 switchTab 跳转。
  uni.switchTab({ url: '/pages/menu/index' })
}
</script>

<style scoped>
.welcome-card {
  padding-top: 56rpx;
  padding-bottom: 56rpx;
}

.welcome-copy {
  display: block;
  margin-top: 20rpx;
  color: #728075;
}

.menu-button {
  margin-top: 40rpx;
}
</style>
