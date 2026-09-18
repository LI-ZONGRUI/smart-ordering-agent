# 微信点餐小程序：本地点餐闭环

这是一个面向初学者的 **Vue 3 + uni-app + Composition API + Pinia** 项目。五个 TabBar 页面仍是**首页、菜单、购物车、订单、我的**，另有菜品详情页和确认订单页。现在可以完成“菜单 → 购物车 → 确认订单 → 提交订单 → 订单列表”。订单只保存在本次运行的内存中；没有支付、登录或云端业务。

## 目录与文件

```text
wechat-ordering-uniapp/
├── .gitignore
├── README.md
├── index.html
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── vite.config.js
└── src/
    ├── App.vue
    ├── main.js
    ├── manifest.json
    ├── pages.json
    ├── mock/
    │   ├── categories.js
    │   └── dishes.js
    ├── static/dishes/
    │   └── 8 张本地菜品图片
    ├── stores/
    │   ├── cart.js
    │   └── orders.js
    └── pages/
        ├── home/index.vue
        ├── menu/index.vue
        ├── cart/index.vue
        ├── orders/index.vue
        ├── profile/index.vue
        ├── dish-detail/index.vue
        └── order-confirm/index.vue
```

| 文件 | 作用 |
| --- | --- |
| `.gitignore` | 忽略安装依赖和编译产物。 |
| `README.md` | 项目说明、文件用途和运行步骤。 |
| `index.html` | Vite 的 Web 入口；微信小程序由 uni-app 编译生成。 |
| `package.json` | 声明依赖及微信小程序的开发、构建命令。 |
| `pnpm-lock.yaml` | 锁定本次验证过的依赖版本。 |
| `pnpm-workspace.yaml` | 允许安装时执行必要依赖的构建脚本；项目仍是单项目。 |
| `vite.config.js` | 启用 uni-app 的 Vite 编译插件。 |
| `src/App.vue` | 应用级公共样式。 |
| `src/main.js` | 创建 Vue 应用并注册 Pinia。 |
| `src/manifest.json` | uni-app 应用配置和微信小程序 AppID 配置。 |
| `src/pages.json` | 注册五个 TabBar 页面、两个非 TabBar 页面和导航栏。 |
| `src/mock/categories.js` | 推荐、热菜、凉菜、主食、饮料五个分类及排序。 |
| `src/mock/dishes.js` | 八条模拟菜品和辣度文字。 |
| `src/static/dishes/*.png` | 本地菜品插图，避免依赖网络图片域名。 |
| `src/stores/cart.js` | Pinia 购物车状态、数量增减、删除、清空与售罄检查。 |
| `src/stores/orders.js` | Pinia 本地订单列表、订单创建与状态文案。 |
| `src/pages/home/index.vue` | 首页和“浏览菜单”入口。 |
| `src/pages/menu/index.vue` | 左侧分类、右侧菜品列表及“+”按钮。 |
| `src/pages/dish-detail/index.vue` | 菜品详情、数量选择与加入购物车。 |
| `src/pages/cart/index.vue` | 展示购物车、增减与删除商品、清空和进入结算。 |
| `src/pages/order-confirm/index.vue` | 核对商品、输入备注并提交订单。 |
| `src/pages/orders/index.vue` | 展示本次运行中创建的订单。 |
| `src/pages/profile/index.vue` | 我的页面占位。 |

`dist/` 是运行命令后生成的微信小程序代码，`node_modules/` 是安装的依赖；它们都不是手写源码。

## 菜品数据与页面逻辑

每条菜品数据包含 `id`、`name`、`categoryId`、`description`、`price`、`image`、`sales`、`spicyLevel`、`ingredients` 和 `status`。其中 `price` 的单位是元；`spicyLevel` 的 0～5 分别是**不辣、微辣、中辣、辣、很辣、特辣**；`ingredients` 是配料名称数组；`status` 使用 `on_sale`（在售）或 `sold_out`（售罄）。额外的 `recommended` 布尔值用于“推荐”分组。

菜单页将当前分类 id 保存在 `selectedCategoryId` 中，并用 Vue 的 `computed` 计算右侧菜品：“推荐”读取 `recommended` 标记，其余分类按 `categoryId` 匹配。点击菜品卡片时用 `uni.navigateTo` 跳转到详情页，只把菜品 `id` 放进 URL；详情页在 `onLoad` 中读取 id，再从模拟数据中查找菜品。卡片上的“+”按钮使用 `@click.stop`，因此加入购物车时不会同时打开详情页。

详情页调用 `cartStore.addDish(dish, quantity)`。菜单页仍调用 `cartStore.addDish(dish)`，默认数量是 1。购物车 store 会检查菜品是否在售：售罄商品不能加入或继续加量，已经在购物车里的售罄商品可以减少或删除，但必须清理后才能结算。

## 从购物车到订单

购物车页的“去结算”使用 `uni.navigateTo` 打开确认订单页。确认页从 Pinia 购物车读取明细、数量和总价，并通过 `form` 收集备注。点击“提交订单”后，订单 store **复制**购物车条目，计算每项小计、总数量和总价，生成 `id`、`items`、`totalPrice`、`totalCount`、`remark`、`status: 'pending'`、`createTime`。订单列表支持显示 `pending`（待处理）、`preparing`（制作中）、`completed`（已完成）、`cancelled`（已取消）四种状态文案；本阶段没有修改状态的功能。

创建成功后才清空购物车，并用 `uni.switchTab` 跳转到订单页。由于订单保存了独立的商品快照，清空购物车不会删除订单。Pinia 数据未写入本地存储，**退出或重新启动小程序后订单会消失**。

## 启动到微信开发者工具

先准备 **Node.js 20 或更新版本**、**pnpm** 和 **微信开发者工具**。本项目已用 Node.js 24 和 pnpm 11.19 编译验证。若尚未安装 pnpm，可在安装 Node.js 后执行 `npm install -g pnpm@11.19.0`。

在项目根目录运行：

```bash
pnpm install
pnpm run dev:mp-weixin
```

看到 `DONE Build complete. Watching for changes...` 后，打开微信开发者工具，选择“导入项目”，项目目录选 **`dist/dev/mp-weixin`**。开发命令会持续监听文件变化，修改源码后会重新编译；退出时按 `Ctrl+C`。

当前未填写自己的微信小程序 AppID，编译产物使用 `touristappid` 供本地体验。需要用自己的小程序预览或发布时，在 `src/manifest.json` 的 `mp-weixin.appid` 中填入真实 AppID，再重新编译。

需要生成正式构建时运行：

```bash
pnpm run build:mp-weixin
```

构建目录是 **`dist/build/mp-weixin`**。本交付已保留一次成功编译的 `dist/dev/mp-weixin` 和 `dist/build/mp-weixin`，因此也可以先导入其中的目录查看项目，再安装依赖继续开发。

## 后续接入 uniCloud

目前菜品来自 `src/mock/dishes.js`，购物车和订单只保存在运行内存中。之后可通过 HBuilderX 导入这个 CLI 项目，在项目根目录创建 uniCloud 开发环境并关联云服务空间，再把菜单和订单的数据来源替换为云端。uniCloud 服务空间、云函数和数据库尚未创建；这一步需要你的云服务账号及实际业务规则。

下一阶段可先确定真实菜品表和订单表字段、图片存储方式、库存和上下架规则，再接入 uniCloud。

## 验证情况

已执行售罄拦截、购物车数量、订单快照和辣度映射检查，并运行 `pnpm run build:mp-weixin`、`pnpm run dev:mp-weixin`，两种编译都成功生成七个页面和五项 TabBar。当前环境没有安装微信开发者工具，新增结算交互尚未在其模拟器中验证。
