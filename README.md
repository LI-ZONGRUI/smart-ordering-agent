# 微信点餐小程序：uniCloud 菜单与订单

本项目使用 Vue 3、uni-app CLI、Composition API 和 Pinia。首页、菜单、购物车、订单、我的五个 TabBar 页面保持原有结构。菜单和订单现已改为调用 uniCloud 云对象；购物车仍保存在本次运行的 Pinia 内存中。

**当前状态：uniCloud 阶段已完成真实环境人工验证。** 服务空间已关联，`menu` / `orders` 云对象已部署，`categories` / `dishes` / `orders` 云数据库已初始化。

已完成并验证：

- Vue 3 + uni-app + Composition API + Pinia 页面与购物车。
- 云端菜单：分类返回 5 条、菜品返回 8 条，推荐分类显示 4 道菜。
- 云端订单：真实下单成功，数据库中可以看到订单记录。
- 后端重新校验菜品状态和数据库价格，计算金额，并保存下单时的订单快照。
- 匿名 `clientId` 隔离与云端订单持久化；关闭并重新打开小程序后，历史订单仍可查看。

新环境部署可参考 [新手部署步骤](docs/UNICLOUD_SETUP.md)。

## 目录

```text
├── src/
│   ├── App.vue                     启动时生成匿名 clientId
│   ├── constants/dish.js           辣度文案
│   ├── mock/                       原有数据，保留作初始化来源与开发参考
│   ├── services/                   页面调用云对象的入口
│   │   ├── clientId.js
│   │   ├── menu.js
│   │   └── orders.js
│   ├── stores/                     Pinia 购物车与云端订单列表缓存
│   └── pages/                      原有七个页面
├── uniCloud-aliyun/
│   ├── cloudfunctions/
│   │   ├── menu/                    getCategories、getDishes
│   │   └── orders/                  createOrder、getOrders
│   └── database/                    三个 collection 的 schema、索引和示例数据
└── docs/UNICLOUD_SETUP.md          HBuilderX 人工部署与验证步骤
```

## 数据流

- 菜单页调用 `src/services/menu.js`，再调用 `menu` 云对象。云对象从 `categories` 和 `dishes` collection 读取数据。菜单页有加载中、失败重试和空数据状态。菜品详情同样从云端加载。
- 购物车使用 Pinia；菜品从云端加载后会同步价格和上下架状态。购物车页面显示的价格仅供确认。
- 确认订单页调用 `src/services/orders.js`，只传 `dishId`、`quantity`、`remark` 和临时 `clientId`。`orders` 云对象重新查询 `dishes`，检查是否在售，并用数据库价格计算每项小计、总数量和总价。写入成功后才清空购物车。
- 订单页每次显示时调用 `getOrders(clientId)`，从云端读取该 clientId 的订单，按时间倒序展示。订单 `items` 保存下单时的菜名、价格、数量与小计快照。

**clientId 只是开发阶段的临时隔离方式，不属于真正的身份认证；以后接入 uni-id 后会改成 userId。** 它保存在小程序本地存储，清除小程序数据、换设备或重装后可能改变。知道或伪造其他 clientId 的人可能查询对应订单，因此不要把本阶段用于真实顾客资料或正式经营。

## 数据库字段

| collection | 主要字段 |
| --- | --- |
| `categories` | `_id`、`name`、`sort` |
| `dishes` | `_id`、`name`、`categoryId`、`description`、`price`、`image`、`sales`、`spicyLevel`、`ingredients`、`status`、`recommended`、`createTime`、`updateTime` |
| `orders` | `_id`、`orderNo`、`items`、`totalPrice`、`totalCount`、`remark`、`status`、`clientId`、`createTime` |

`price` 和 `totalPrice` 单位为元；计算时云对象先转换为分，再汇总。`spicyLevel` 为 0～5，依次是不辣、微辣、中辣、辣、很辣、特辣。`status` 在菜品中是 `on_sale` 或 `sold_out`；订单状态是 `pending`、`preparing`、`completed`、`cancelled`，本阶段只创建 `pending` 订单。

`dishes.image` 暂时沿用 `/static/dishes/*.png`。这些路径指向**小程序包内图片**，不是云存储文件。以后若要让运营人员在云端新增菜品图片，应再迁移到云存储。

三个 schema 的客户端数据库直连读写权限均为 `false`。菜单与订单只通过云对象访问数据库。因为现在没有正式登录，`clientId` 的查询限制仍不能视为安全授权。

## 构建

准备 Node.js 20+、pnpm、微信开发者工具。项目根目录执行：

```bash
pnpm install
pnpm run build:mp-weixin
```

日常云端联调请在 HBuilderX 中打开当前项目，通过“运行 → 运行到小程序模拟器 → 微信开发者工具”启动，并选择“连接云端云函数”。开发产物位于 `dist/dev/mp-weixin`；不要同时运行 `pnpm run dev:mp-weixin`，避免两个编译进程写入同一目录。

`pnpm run build:mp-weixin` 用于前端正式构建检查，产物位于 `dist/build/mp-weixin`；命令本身不会部署云对象或初始化数据库。关联服务空间及云端联调步骤见 [新手部署步骤](docs/UNICLOUD_SETUP.md)。

开发说明：当前微信开发者工具与 development sourcemap 存在兼容问题（`No element indexed by 9`）。`vite.config.js` 暂时只在 `mp-weixin + development` 下关闭 sourcemap，正式发行与其他平台配置不受影响。开发调试期间无法通过 sourcemap 定位原始源码行号；兼容问题修复后可移除该条件配置。

原有 `src/mock/categories.js` 和 `src/mock/dishes.js` 仍保留。页面已不再从它们读取分类或菜品；`uniCloud-aliyun/database/*.init_data.json` 是从它们整理出的初始化数据。确认真实云空间运行后，可在未来阶段删除 mock 数据，但本阶段保留供对照。

## 参考文档

- [DCloud：CLI 项目接入 uniCloud](https://uniapp.dcloud.net.cn/uniCloud/quickstart.html)
- [DCloud：云对象](https://doc.dcloud.net.cn/uniCloud/cloud-obj.html)
- [DCloud：数据库初始化](https://doc.dcloud.net.cn/uniCloud/hellodb.html)
- [DCloud：DB Schema](https://doc.dcloud.net.cn/uniCloud/schema.html)
