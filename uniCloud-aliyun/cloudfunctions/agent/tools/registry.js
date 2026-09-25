// Registry是唯一机器可读合同；模型只能看到这里声明、且Executor静态映射的工具。
const definitions = [
  {
    type: 'function',
    function: {
      name: 'search_menu',
      description: '按菜名、描述或配料中的关键词查询当前真实菜单，包含售罄记录。空结果仅表示当前查询没有匹配。',
      parameters: {
        type: 'object', properties: { query: { type: 'string', minLength: 1, maxLength: 50,
          description: '去除首尾空白后1～50个Unicode字符，做字面匹配，不做语义推断' } },
        required: ['query'], additionalProperties: false
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'list_available_drinks',
      description: '读取当前饮料分类下status为on_sale的真实菜品，不生成推荐文案。',
      parameters: { type: 'object', properties: {}, required: [], additionalProperties: false }
    }
  },
  {
    type: 'function',
    function: {
      name: 'get_dish_detail',
      description: '按真实dishId读取菜品详情及当前价格和状态；不存在时返回found=false。',
      parameters: {
        type: 'object', properties: { dishId: { type: 'string', minLength: 1,
          description: '非空的真实菜品ID，去除首尾空白' } },
        required: ['dishId'], additionalProperties: false
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'prepare_add_to_cart',
      description: '根据真实dishId和数量准备一个需要用户确认的购物车动作；会重新查询菜品状态与价格，不会修改购物车。应先用菜单查询工具确认具体菜品，不得把待确认动作说成已经执行。',
      parameters: {
        type: 'object',
        properties: {
          dishId: { type: 'string', minLength: 1, description: '非空的真实菜品ID，去除首尾空白' },
          quantity: { type: 'integer', minimum: 1, maximum: 20, description: '准备加入的数量，必须为1～20的整数' }
        },
        required: ['dishId', 'quantity'],
        additionalProperties: false
      }
    }
  }
]

function freeze(value) {
  for (const child of Object.values(value)) if (child && typeof child === 'object') freeze(child)
  return Object.freeze(value)
}
freeze(definitions)

// 返回副本，调用者不能修改后续请求使用的 allowlist / 参数定义。
function getToolDefinitions() { return JSON.parse(JSON.stringify(definitions)) }
module.exports = { getToolDefinitions }
