import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

// 当前微信开发者工具与开发 sourcemap 存在兼容问题，微信小程序开发模式暂时关闭映射。
// uni-app 开发模式默认开启映射，需要在 uni() 初始化前关闭其内部开关。
const disableWechatDevSourcemap =
  process.env.UNI_PLATFORM === 'mp-weixin' && process.env.NODE_ENV === 'development'

if (disableWechatDevSourcemap) {
  process.env.UNI_APP_SOURCEMAP = 'false'
}

export default defineConfig({
  plugins: [uni()],
  // 正式发行和其他平台仍使用原有默认配置。
  ...(disableWechatDevSourcemap ? { build: { sourcemap: false } } : {})
})
