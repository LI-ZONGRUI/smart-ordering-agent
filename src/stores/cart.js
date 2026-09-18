import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { dishes } from '../mock/dishes.js'

function isDishAvailable(id) {
  const dish = dishes.find((entry) => entry.id === id)
  return Boolean(dish && dish.status === 'on_sale')
}

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
    items.value.some((item) => !isDishAvailable(item.id))
  )

  function addDish(dish, quantity = 1) {
    // 在 store 再检查一次状态，避免绕过页面按钮加入已售罄菜品。
    if (!isDishAvailable(dish.id)) return false

    // 菜单页仍传一个参数，行为与原来相同；详情页可一次加入选定数量。
    const count = Number.isInteger(quantity) && quantity > 0 ? quantity : 1
    const item = items.value.find((entry) => entry.id === dish.id)
    if (item) {
      item.quantity += count
      return true
    }

    // 只保存购物车需要的字段，避免直接修改模拟菜品数据。
    items.value.push({ id: dish.id, name: dish.name, price: dish.price, quantity: count })
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

  return {
    items,
    itemCount,
    totalPrice,
    hasUnavailableItems,
    isDishAvailable,
    addDish,
    changeQuantity,
    removeDish,
    clearCart
  }
})
