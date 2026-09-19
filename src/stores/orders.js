import { ref } from 'vue'
import { defineStore } from 'pinia'

export const orderStatusLabels = {
  pending: '待处理',
  preparing: '制作中',
  completed: '已完成',
  cancelled: '已取消'
}

// 这里仅缓存云端查询结果，云数据库才是订单的持久化来源。
export const useOrdersStore = defineStore('orders', () => {
  const orders = ref([])

  function setOrders(cloudOrders) {
    orders.value = cloudOrders
  }

  return { orders, setOrders }
})
