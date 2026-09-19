// 云端调用集中在 services，页面只关心拿到的数据。
function readList(result, methodName) {
  // 云对象正常会直接返回数组；兼容数据库结果 { data: [] }，并在结构异常时给出明确错误。
  const list = Array.isArray(result) ? result : result?.data
  if (!Array.isArray(list)) {
    throw new Error(`menu.${methodName} 返回格式错误`)
  }
  return list
}

export async function getCategories() {
  const menuCloud = uniCloud.importObject('menu', { customUI: true })
  const result = await menuCloud.getCategories()
  const categories = readList(result, 'getCategories')
  return categories.map((category) => ({ ...category, id: category._id }))
}

export async function getDishes() {
  const menuCloud = uniCloud.importObject('menu', { customUI: true })
  const result = await menuCloud.getDishes()
  const dishes = readList(result, 'getDishes')
  return dishes.map((dish) => ({ ...dish, id: dish._id }))
}
