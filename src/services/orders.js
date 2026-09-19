import { getClientId } from './clientId'

export function createOrder(cartItems, remark) {
  // 不上传购物车显示的价格与总价；云对象会从数据库取实时价格后计算。
  const items = cartItems.map((item) => ({ dishId: item.id, quantity: item.quantity }))
  return uniCloud.importObject('orders').createOrder({ clientId: getClientId(), items, remark })
}

export function getOrders() {
  return uniCloud.importObject('orders').getOrders(getClientId())
}
