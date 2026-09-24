const PAGE_SIZE = 100
const DISH_FIELDS = { _id: true, name: true, categoryId: true, description: true,
  price: true, status: true, spicyLevel: true, ingredients: true }
const nonempty = value => typeof value === 'string' && value.trim().length > 0

// 分页读取，避免默认返回条数限制把“没读到”误判成“没匹配”。固定collection，不接受外部集合名。
async function readDishes(db, filter = null) {
  const rows = []
  for (let offset = 0; ; offset += PAGE_SIZE) {
    let query = db.collection('dishes')
    if (filter) query = query.where(filter)
    const result = await query.field(DISH_FIELDS).orderBy('_id', 'asc').skip(offset).limit(PAGE_SIZE).get()
    if (!Array.isArray(result?.data)) throw new Error('invalid dish data')
    rows.push(...result.data)
    if (result.data.length < PAGE_SIZE) break
  }
  const seen = new Set()
  for (const row of rows) {
    if (!row || !nonempty(row._id) || seen.has(row._id) || !nonempty(row.name) || !nonempty(row.categoryId) ||
        typeof row.description !== 'string' || typeof row.price !== 'number' || !Number.isFinite(row.price) || row.price < 0 ||
        !['on_sale', 'sold_out'].includes(row.status) || !Number.isInteger(row.spicyLevel) || row.spicyLevel < 0 || row.spicyLevel > 5 ||
        !Array.isArray(row.ingredients) || !row.ingredients.every(nonempty)) throw new Error('invalid dish data')
    seen.add(row._id)
  }
  return rows
}

function summary(row) {
  // 显式白名单：价格/状态只能来自本次DB读取，不展开数据库原始记录。
  return { dishId: row._id, name: row.name, categoryId: row.categoryId,
    price: row.price, status: row.status, spicyLevel: row.spicyLevel }
}

async function searchMenu({ query }, { db }) {
  const rows = await readDishes(db)
  const keyword = query.toLowerCase()
  const items = rows.filter(row => [row.name, row.description, ...row.ingredients]
    .some(text => text.toLowerCase().includes(keyword))).map(summary)
  return { tool: 'search_menu', query, count: items.length, items }
}

async function listAvailableDrinks(args, { db }) {
  // 初始化数据真实名称为“饮料”；运行时解析ID，不猜测或硬编码drink。
  const result = await db.collection('categories').where({ name: '饮料' })
    .field({ _id: true, name: true }).limit(2).get()
  if (!Array.isArray(result?.data) || result.data.length !== 1 ||
      result.data[0]?.name !== '饮料' || !nonempty(result.data[0]._id)) {
    // 缺失/重名是配置异常，不能伪装成“当前没有饮料”。
    throw new Error('ambiguous drinks category')
  }
  const categoryId = result.data[0]._id
  const rows = await readDishes(db, { categoryId, status: 'on_sale' })
  if (rows.some(row => row.categoryId !== categoryId || row.status !== 'on_sale')) throw new Error('invalid filtered data')
  const items = rows.map(summary)
  return { tool: 'list_available_drinks', count: items.length, items }
}

async function getDishDetail({ dishId }, { db }) {
  const rows = await readDishes(db, { _id: dishId })
  if (rows.length > 1 || rows.some(row => row._id !== dishId)) throw new Error('invalid detail data')
  const row = rows[0]
  return { tool: 'get_dish_detail', dishId, found: Boolean(row),
    item: row ? { ...summary(row), description: row.description, ingredients: [...row.ingredients] } : null }
}

module.exports = { searchMenu, listAvailableDrinks, getDishDetail }
