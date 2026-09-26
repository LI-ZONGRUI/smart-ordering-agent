const assert = require('node:assert/strict')
const source = require('../../uniCloud-aliyun/database/dishes.init_data.json')
const categorySource = require('../../uniCloud-aliyun/database/categories.init_data.json')

function createMenuDb(options = {}) {
  const calls = []
  const dishes = structuredClone(options.dishes || source)
  const categories = structuredClone(options.categories || categorySource)
  const db = { collection(name) {
    assert.ok(['dishes', 'categories'].includes(name))
    let condition = {}, offset = 0, size = 100
    return {
      where(value) { condition = value; return this },
      field() { return this },
      orderBy(key, direction) { assert.equal(key, '_id'); assert.equal(direction, 'asc'); return this },
      skip(value) { offset = value; return this },
      limit(value) { size = value; return this },
      async get() {
        calls.push({ name, condition, offset, size })
        if (options.fails) throw new Error('private database detail')
        const rows = name === 'dishes' ? dishes : categories
        return { data: rows.filter(row => Object.entries(condition).every(([key, value]) => row[key] === value))
          .sort((a, b) => a._id < b._id ? -1 : a._id > b._id ? 1 : 0).slice(offset, offset + size) }
      },
      add() { assert.fail('write forbidden') },
      update() { assert.fail('write forbidden') },
      remove() { assert.fail('write forbidden') }
    }
  } }
  return { db, calls, dishes, categories }
}

module.exports = { createMenuDb }
