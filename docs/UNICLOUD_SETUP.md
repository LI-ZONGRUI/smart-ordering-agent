# HBuilderX 手动部署 uniCloud：新手逐步操作

这份步骤针对本仓库的 **Vue 3 + uni-app CLI** 项目。源码在 `src/`，云端代码在项目根目录的 `uniCloud-aliyun/`，两者是同一个项目。以下操作需要你的 DCloud 账号和微信小程序账号；仓库没有写入账号密码或密钥。

## 1. 安装并登录 HBuilderX

需要安装 HBuilderX。请从 [DCloud 官方下载页](https://www.dcloud.io/hbuilderx.html)安装当前正式版，建议至少 3.97，因为本项目使用 `*.init_data.json` 数据库初始化文件。打开 HBuilderX 后登录你的 DCloud 账号。

**成功标志：** 能在 HBuilderX 顶部菜单看到“文件”“运行”等菜单，账号处显示已登录。

## 2. 导入整个 CLI 项目

在 HBuilderX 选择“文件 → 导入 → 从本地目录导入”，选择本仓库根目录 `wechat-ordering-uniapp`，即**同时包含 `package.json`、`src/` 和 `uniCloud-aliyun/` 的目录**。不要只导入 `src/` 或 `dist/`。

先在项目根目录执行 `pnpm install`。如果 HBuilderX 提示缺少 Node，请在 HBuilderX 的“偏好设置/设置 → 运行配置 → Node 路径”中选择本机 Node.js 20+，再重启 HBuilderX。

**成功标志：** HBuilderX 左侧同一个项目下能看到 `src/`、`uniCloud-aliyun/`、`package.json`。

## 3. 取得 uni-app 应用标识与填写微信 AppID

打开 `src/manifest.json`。当前顶层 `appid` 和 `mp-weixin.appid` 均为空。如果 HBuilderX 提示缺少 uni-app 应用标识，在可视化“基础配置 → uni-app 应用标识”处点击“重新获取”。若要使用自己的微信小程序真机预览，在“微信小程序配置”填写自己的小程序 AppID。AppID 是公开标识，不是 AppSecret；**不要把 AppSecret、Token 或其他密钥写入项目**。

**成功标志：** 顶层 uni-app 应用标识不为空；微信开发者工具导入后显示预期的小程序 AppID。

## 4. 创建阿里云开发服务空间

在 HBuilderX 中右击项目里的 `uniCloud-aliyun/`，选择“关联云服务空间或项目…”；若还没有空间，按界面入口新建，或打开 [uniCloud Web 控制台](https://unicloud.dcloud.net.cn)创建。选择**阿里云**，新建专门用于开发和测试的服务空间。按照控制台提示完成实名认证等账号步骤，并等待空间状态变为可用。费用、免费额度和区域选项以创建时控制台显示为准。

这里选阿里云，是因为本仓库云端目录已命名为 `uniCloud-aliyun/`。不要把这个目录关联到腾讯云或支付宝云空间。

**成功标志：** 控制台服务空间列表中出现一个可用的阿里云空间，能打开它的数据库和云函数页面。

## 5. 关联服务空间

回到 HBuilderX，右击 `uniCloud-aliyun/`，选择“关联云服务空间或项目… → 关联云服务空间”，选择刚建的阿里云开发空间。若新建后列表暂未显示，等空间创建完成再刷新。

**成功标志：** `uniCloud-aliyun/` 在 HBuilderX 中显示关联空间；右击其下的数据库和云对象时能看到上传、初始化等菜单。如果 HBuilderX 没把预置目录识别为云环境，先在项目根目录右击“创建 uniCloud 云开发环境”并选择阿里云，再确认云端源码位于识别出的 `uniCloud-aliyun/` 下。

## 6. 初始化三个 collection

本项目已准备好：

- `uniCloud-aliyun/database/categories.schema.json`、`categories.index.json`、`categories.init_data.json`
- `uniCloud-aliyun/database/dishes.schema.json`、`dishes.index.json`、`dishes.init_data.json`
- `uniCloud-aliyun/database/orders.schema.json`、`orders.index.json`

在 HBuilderX 中右击 `uniCloud-aliyun/database/`，选择“初始化云数据库”（某些版本可从 `uniCloud-aliyun/` 的“初始化向导”进入）。在向导中选中这三个 collection 的 schema、索引，以及 categories/dishes 的初始化数据，确认目标是刚创建的**开发空间**，再执行。只在空数据库上导入一次示例数据；文件里有固定 `_id`，重复导入可能出现冲突。

如果向导分步执行，先上传三个 DB Schema 和索引，再初始化 `categories.init_data.json` 与 `dishes.init_data.json`。`orders` 不需要初始订单数据，首次下单时由云对象写入。不要从小程序前端直接写数据库。

**成功标志：** 在 uniCloud Web 控制台的云数据库里能看到 `categories`、`dishes`、`orders` 三个集合；`categories` 有 5 条，`dishes` 有 8 条，`orders` 初始为空。`dishes` 的 `_id` 应是 `dish-1` 等字符串，`categoryId` 应与分类 `_id` 匹配。

## 7. 上传两个云对象

在 HBuilderX 右击 `uniCloud-aliyun/cloudfunctions/menu/`，选择“上传部署”；对 `orders/` 也做一次。也可以通过 `cloudfunctions/` 的批量上传菜单。`pnpm run build:mp-weixin` **不会**部署这两个云对象。

**成功标志：** HBuilderX 输出上传成功；uniCloud Web 控制台的云函数列表里能看到 `menu` 和 `orders`。它们对应的入口分别是各自目录内的 `index.obj.js`。

## 8. 运行到微信开发者工具

在 HBuilderX 使用“运行 → 运行到小程序模拟器 → 微信开发者工具”，选择项目关联的微信 AppID。HBuilderX 的 uniCloud 调试控制台默认可能连接**本地云函数**；要验证真正的云端持久化，在前端控制台右上角切换为“连接云端云函数”。然后在微信开发者工具打开菜单页。

也可以使用 `pnpm run dev:mp-weixin` 编译前端，再在微信开发者工具导入 `dist/dev/mp-weixin`；前提仍是已用 HBuilderX 关联并部署云空间。第一次排查时建议先用 HBuilderX 的运行菜单，较容易看到云端连接状态。

**成功标志：** 菜单从“正在加载菜品…”变为 5 个分类和 8 道菜；右侧可以切换分类，售罄的酸梅汤显示“已售罄”。云端连接失败会显示错误和“重试”按钮，不能把前端编译成功误认为云端已部署成功。

## 9. 检查微信网络域名

本阶段只调用云对象，不上传图片文件。若微信开发者工具提示域名不在合法域名列表，开发模式可在工具的项目设置中临时关闭合法域名校验；真实预览或发行前，应在微信公众平台的小程序后台把阿里云 uniCloud 的 **request 合法域名**加入白名单。按 [DCloud 官方发行文档](https://doc.dcloud.net.cn/uniCloud/publish.html) 当前表格，阿里云为 `https://api.next.bspapp.com`；最终仍以控制台和开发者工具实际提示为准。不要为本地调试把任何域名或密钥写死到源码里。

**成功标志：** 微信开发者工具 Console 没有域名拦截错误，菜单和订单请求能正常返回。

## 10. 验证下单与重启后保留

1. 进入菜单，选一道在售菜，加入购物车；进入购物车、确认订单，填写备注并提交。
2. 只有云端创建成功，才会看到“下单成功”、购物车清空、自动跳到订单页。订单页应显示新订单号、时间、商品快照、数量、总价和“待处理”。
3. 打开 uniCloud Web 控制台的 `orders` 集合，确认新增一条记录，`clientId`、`items`、`totalPrice` 等字段齐全。
4. **关闭微信开发者工具中的小程序，再重新打开同一个小程序**，进入订单 Tab；该订单仍应出现。保持同一个微信开发者工具存储环境，不要执行“清除缓存/清除数据”。
5. 可把 `dishes` 某道菜改为 `sold_out` 再尝试提交；云对象应拒绝创建订单，购物车应保留。测试后可在控制台改回 `on_sale`。

**成功标志：** 重启后订单仍在；在控制台可查到对应记录；云端拒绝失败订单时购物车没有被清空。

## 目前的边界

`clientId` 只用于开发阶段按本地标记筛选订单，**不是真正的身份认证**。未来接入 uni-id 后，应把订单归属改为服务端识别的 `userId`，并重新设计权限。本阶段没有微信登录、支付或云存储图片。`src/mock/` 只保留作参考和初始化来源，运行时菜单不再读取它们。
