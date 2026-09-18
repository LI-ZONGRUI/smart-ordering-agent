import { ref } from 'vue'
import { defineStore } from 'pinia'

export const orderStatusLabels = {
  pending: '待处理',
  preparing: '制作中',
  completed: '已完成',
  cancelled: '已取消'
}

// 订单暂时只保存在 Pinia 内存中，退出小程序后会丢失。
export const useOrdersStore = defineStore('orders', () => {
  const orders = ref([])

  function createOrder(cartItems, remark = '') {
    if (cartItems.length === 0) return null

    // 复制购物车数据，确保提交后清空购物车不会影响已经创建的订单。
    const orderItems = cartItems.map((item) => ({
      id: item.id,
      name: item.name,
      price: item.price,
      quantity: item.quantity,
      subtotal: Number((item.price * item.quantity).toFixed(2))
    }))

    const totalCount = orderItems.reduce((sum, item) => sum + item.quantity, 0)
    const totalPrice = Number(
      orderItems.reduce((sum, item) => sum + item.subtotal, 0).toFixed(2)
    )

    const order = {
      id: `OD${Date.now()}${String(orders.value.length + 1).padStart(3, '0')}`,
      items: orderItems,
      totalPrice,
      totalCount,
      remark: remark.trim(),
      status: 'pending',
      createTime: new Date().toISOString()
    }

    // 新订单放在最前面，订单页打开时即可先看到它。
    orders.value.unshift(order)
    return order
  }

  return { orders, createOrder }
})
