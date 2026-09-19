import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

// 使用 Composition API 风格的 setup store，暂时只保存到内存。
export const useCartStore = defineStore('cart', () => {
  const items = ref([])

  const itemCount = computed(() =>
    items.value.reduce((sum, item) => sum + item.quantity, 0)
  )

  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => sum + item.price * item.quantity, 0)
  )

  const hasUnavailableItems = computed(() =>
    items.value.some((item) => item.status !== 'on_sale')
  )

  function isDishAvailable(id) {
    const item = items.value.find((entry) => entry.id === id)
    return Boolean(item && item.status === 'on_sale')
  }

  function addDish(dish, quantity = 1) {
    // 在 store 再检查一次状态，避免绕过页面按钮加入已售罄菜品。
    if (dish.status !== 'on_sale') return false

    // 菜单页仍传一个参数，行为与原来相同；详情页可一次加入选定数量。
    const count = Number.isInteger(quantity) && quantity > 0 ? quantity : 1
    const item = items.value.find((entry) => entry.id === dish.id)
    if (item) {
      item.name = dish.name
      item.price = dish.price
      item.status = dish.status
      item.quantity += count
      return true
    }

    // 购物车保留用于展示的菜品快照；下单价格仍以云数据库为准。
    items.value.push({ id: dish.id, name: dish.name, price: dish.price, status: dish.status, quantity: count })
    return true
  }

  function changeQuantity(id, amount) {
    const item = items.value.find((entry) => entry.id === id)
    if (!item) return false
    // 已售罄商品允许减少或删除，但不能再增加数量。
    if (amount > 0 && !isDishAvailable(id)) return false

    item.quantity += amount
    if (item.quantity <= 0) {
      items.value = items.value.filter((entry) => entry.id !== id)
    }
    return true
  }

  function removeDish(id) {
    items.value = items.value.filter((entry) => entry.id !== id)
  }

  function clearCart() {
    items.value = []
  }

  function syncDishes(dishes) {
    // 菜单刷新后同步上下架状态。服务端提交订单时仍会再次检查。
    const dishMap = new Map(dishes.map((dish) => [dish.id, dish]))
    items.value.forEach((item) => {
      const dish = dishMap.get(item.id)
      item.status = dish?.status || 'sold_out'
      if (dish) {
        item.name = dish.name
        item.price = dish.price
      }
    })
  }

  return {
    items,
    itemCount,
    totalPrice,
    hasUnavailableItems,
    isDishAvailable,
    addDish,
    changeQuantity,
    removeDish,
    clearCart,
    syncDishes
  }
})
