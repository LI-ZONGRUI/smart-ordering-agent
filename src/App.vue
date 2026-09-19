<script setup>
import { onLaunch } from '@dcloudio/uni-app'
import { getClientId } from './services/clientId'

onLaunch(() => {
  // 首次启动生成匿名 clientId，并存到本地；重新打开小程序会继续使用同一个值。
  getClientId()
})
</script>

<style>
page {
  background: #f7f8f5;
  color: #243126;
  font-size: 28rpx;
}

.page {
  padding: 32rpx;
}

.card {
  margin-bottom: 24rpx;
  padding: 28rpx;
  border-radius: 20rpx;
  background: #ffffff;
}

.title {
  font-size: 40rpx;
  font-weight: 700;
}

.section-title {
  margin-bottom: 20rpx;
  font-size: 32rpx;
  font-weight: 600;
}

.muted {
  color: #728075;
}

.price {
  color: #cf6139;
  font-weight: 600;
}

.primary-button {
  background: #2d8055;
  color: #ffffff;
}
</style>
