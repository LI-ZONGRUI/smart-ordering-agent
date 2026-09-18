<template>
  <view class="page">
    <view class="card welcome-card">
      <text class="title">欢迎点餐</text>
      <text class="welcome-copy">这是微信点餐小程序的基础项目。</text>
      <button class="primary-button menu-button" @click="goToMenu">浏览菜单</button>
    </view>

    <view class="card">
      <view class="section-title">现在可以体验</view>
      <text class="muted">查看模拟菜品、加入购物车，并通过底部导航切换页面。</text>
    </view>
  </view>
</template>

<script setup>
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
