import { createSSRApp } from 'vue'
import * as Pinia from 'pinia'
import App from './App.vue'

export function createApp() {
  const app = createSSRApp(App)

  // 所有页面共用同一个 Pinia 实例，购物车状态才能在 Tab 页面之间共享。
  app.use(Pinia.createPinia())

  // uni-app 的 Vue3/Pinia 集成需要一并返回 Pinia。
  return { app, Pinia }
}
