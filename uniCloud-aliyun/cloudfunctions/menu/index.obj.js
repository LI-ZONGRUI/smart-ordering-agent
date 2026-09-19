// 菜单云对象：页面只调用这里的方法，不直接读写数据库。
const db = uniCloud.database()

module.exports = {
  async getCategories() {
    const result = await db.collection('categories').orderBy('sort', 'asc').get()
    return result.data
  },

  async getDishes(categoryId = '') {
    let query = db.collection('dishes')
    if (categoryId && categoryId !== 'recommended') {
      query = query.where({ categoryId })
    }
    const result = await query.get()
    const dishes = result.data
    return categoryId === 'recommended'
      ? dishes.filter((dish) => dish.recommended && dish.status === 'on_sale')
      : dishes
  }
}
