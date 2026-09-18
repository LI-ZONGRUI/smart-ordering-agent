// price 的单位是元；spicyLevel 为 0~5；status 为 on_sale 或 sold_out。
// image 使用本地静态图片，微信小程序离线预览时也能正常显示。
export const dishes = [
  {
    id: 1,
    name: '招牌鸡腿饭',
    categoryId: 'staple',
    description: '酱香鸡腿搭配米饭和时蔬，饱腹又满足。',
    price: 28,
    image: '/static/dishes/chicken-rice.png',
    sales: 326,
    spicyLevel: 0,
    ingredients: ['鸡腿', '米饭', '西兰花'],
    status: 'on_sale',
    recommended: true
  },
  {
    id: 2,
    name: '番茄牛肉面',
    categoryId: 'staple',
    description: '番茄汤底酸甜开胃，配上软嫩牛肉。',
    price: 32,
    image: '/static/dishes/beef-noodles.png',
    sales: 214,
    spicyLevel: 0,
    ingredients: ['牛肉', '番茄', '面条', '青菜'],
    status: 'on_sale',
    recommended: false
  },
  {
    id: 3,
    name: '鲜蔬沙拉',
    categoryId: 'cold',
    description: '新鲜蔬菜拌油醋汁，清爽轻盈。',
    price: 22,
    image: '/static/dishes/salad.png',
    sales: 168,
    spicyLevel: 0,
    ingredients: ['生菜', '番茄', '黄瓜', '油醋汁'],
    status: 'on_sale',
    recommended: true
  },
  {
    id: 4,
    name: '柠檬茶',
    categoryId: 'drink',
    description: '清爽柠檬香气，适合搭配正餐。',
    price: 12,
    image: '/static/dishes/lemon-tea.png',
    sales: 452,
    spicyLevel: 0,
    ingredients: ['红茶', '柠檬'],
    status: 'on_sale',
    recommended: false
  },
  {
    id: 5,
    name: '香辣鸡丁',
    categoryId: 'hot',
    description: '鸡丁与辣椒快炒，香辣下饭。',
    price: 36,
    image: '/static/dishes/spicy-chicken.png',
    sales: 287,
    spicyLevel: 3,
    ingredients: ['鸡腿肉', '干辣椒', '青椒', '花椒'],
    status: 'on_sale',
    recommended: true
  },
  {
    id: 6,
    name: '双椒牛肉',
    categoryId: 'hot',
    description: '嫩牛肉配青红椒，锅气十足。',
    price: 42,
    image: '/static/dishes/pepper-beef.png',
    sales: 196,
    spicyLevel: 1,
    ingredients: ['牛肉', '青椒', '红椒', '洋葱'],
    status: 'on_sale',
    recommended: true
  },
  {
    id: 7,
    name: '拍黄瓜',
    categoryId: 'cold',
    description: '爽脆黄瓜拌蒜香酱汁。',
    price: 16,
    image: '/static/dishes/cold-cucumber.png',
    sales: 238,
    spicyLevel: 1,
    ingredients: ['黄瓜', '蒜', '香醋', '辣椒'],
    status: 'on_sale',
    recommended: false
  },
  {
    id: 8,
    name: '酸梅汤',
    categoryId: 'drink',
    description: '酸甜解腻，冰镇风味更佳。',
    price: 14,
    image: '/static/dishes/plum-juice.png',
    sales: 93,
    spicyLevel: 0,
    ingredients: ['乌梅', '山楂', '冰糖'],
    status: 'sold_out',
    recommended: false
  }
]

export const spicyLevelLabels = ['不辣', '微辣', '中辣', '辣', '很辣', '特辣']
