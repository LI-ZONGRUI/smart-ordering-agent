# V5.6A：Server-side Order Idempotency Foundation

## 阶段状态

V5.6A已经完成服务端幂等基础，并通过真实uniCloud订单集合和数据库索引验收：

**Server-side order idempotency has been validated against the real uniCloud orders collection with a unique sparse requestId index.**

V5.6A扩展了 `orders.createConfirmedOrder()` 的服务端幂等能力。V5.6B已经把requestId接入微信正式Checkout，并完成真实微信小程序与uniCloud orders集合验收。本次前端接入没有修改Agent后端、支付、库存逻辑或服务端幂等实现。

## 为什么UI防双击不够

`submittingOrder` 可以阻止同一页面中的普通双击，但不能覆盖以下情况：

```text
Server已经持久化订单
 → 成功响应在网络途中丢失
 → Client不知道结果并重试
```

如果没有服务器唯一约束，两次请求可能写入两张订单。仅执行“先查询requestId，不存在就add”的check-then-insert同样不安全：两个并发请求可能同时查到不存在，然后都写入。

## requestId

requestId表示一次 `createConfirmedOrder` 意图，不是orderNo、身份认证、支付ID或秘密。

- 类型：string，先trim。
- 长度：8～128个字符。
- 字符：`A-Z`、`a-z`、`0-9`、`-`、`_`。
- 空值、对象、数组、控制字符、过长或非法字符返回 `ORDER_REQUEST_ID_INVALID`。
- 当前为可选字段；不传时保持V5.5C兼容路径。

orderNo仍按原规则生成并展示。requestId和requestFingerprint只保存在数据库内部，不返回创建响应或订单列表。

## request fingerprint

同一个requestId只能对应同一个创建意图。服务器对下列规范化内容计算SHA-256：

```text
clientId
items：按dishId排序，只含dishId与quantity
expectedPreview.items：按dishId排序，金额转成整数分
expectedPreview.totalQuantity
expectedPreview.totalPrice：整数分
remark：trim后的实际持久化内容
```

对象键使用固定顺序。items和expectedPreview数组的原始排列不同不会改变fingerprint；clientId、数量、确认价格或实际备注变化会改变fingerprint。

fingerprint用于检查重试内容是否一致，不是身份认证，也不会替代首次请求的实时菜品校验和计价。

## 数据库存储与唯一约束

`orders`新增两个可选字段：

- `requestId`
- `requestFingerprint`

并新增索引：

```json
{
  "IndexName": "request_id_unique",
  "MgoKeySchema": {
    "MgoIndexKeys": [{ "Name": "requestId", "Direction": "1" }],
    "MgoIsUnique": true,
    "MgoIsSparse": true
  }
}
```

当前服务空间使用阿里云uniCloud。DCloud的[数据库索引文档](https://doc.dcloud.net.cn/uniCloud/db-index.html)明确说明阿里云支持稀疏索引：缺少索引字段的历史记录可以共存，非空值仍受唯一约束。真实控制台已经确认 `request_id_unique` 创建成功，配置为requestId升序、unique和sparse；原有 `_id_`、`client_time_desc`、`order_no_unique` 均继续存在。当前历史订单没有requestId，因此不需要回填或删除，也不影响旧订单查询和legacy `createOrder()`。

该唯一索引是并发安全的必要条件。初始查询只是普通重试的快速路径，最终唯一性由数据库约束保证。

## 创建与重放流程

### 第一次请求

```text
validate requestId / payload
 → canonical fingerprint
 → existing requestId lookup（普通重试快速路径）
 → Fresh Server Validation / Pricing
 → Expected Preview Comparison
 → insert order with requestId + requestFingerprint
```

首次创建不会因为幂等功能而绕过V5.5C的菜品存在、在售状态、实时价格和确认金额检查。

### 同requestId、同fingerprint

已有订单时，服务器校验 `existing.clientId` 和 `existing.requestFingerprint`，一致才返回第一次创建的公开订单结构。不会重新计价、生成orderNo、写第二条记录或改变订单状态。

### 同requestId、不同fingerprint或clientId

返回：

```text
ORDER_IDEMPOTENCY_CONFLICT
该订单请求已被其他内容使用，请重新发起结算
```

服务器不会返回旧订单，也不会创建新订单或暴露fingerprint。

### 并发唯一冲突恢复

两个同键请求都可能在初始查询中看不到订单，但 `request_id_unique` 只允许一个insert成功。另一个insert失败后，服务器不会根据任意duplicate错误直接认定为重放，而是再次按requestId精确查询，并校验clientId和fingerprint：

- 找到且完全匹配：返回第一次成功创建的订单。
- 找到但意图不同：返回 `ORDER_IDEMPOTENCY_CONFLICT`。
- 查不到或查询失败：返回安全的 `ORDER_CREATE_FAILED`。

因此orderNo碰撞、其他唯一索引冲突和未知数据库异常不会被误判成幂等重放。原始DB错误、索引名、stack和内部路径不会返回客户端。

## 兼容范围

- `createConfirmedOrder()`不带requestId：保持V5.5C非幂等兼容行为。
- legacy `createOrder()`：调用方式、订单快照和返回结构不变，不保存幂等字段。
- 历史orders：不要求迁移，列表读取不暴露新增内部字段。
- V5.5C：价格变化仍返回 `ORDER_CONFIRMATION_STALE`，售罄仍返回 `ORDER_DISH_UNAVAILABLE`。
- 当前前端：第一次最终确认下单时生成requestId并冻结完整submission payload；结果未知后的重试复用同一requestId和同一payload。

## V5.6B前端生命周期

```text
Final Order Confirmation
 → Generate requestId once
 → Freeze requestId / clientId / items / expectedPreview / remark
 → orders.createConfirmedOrder()

Success or idempotent replay
 → show orderNo
 → clear Pinia Cart
 → clear Proposal / requestId / frozen payload

Outcome unknown
 → keep Cart / Proposal / confirmation / requestId / frozen payload
 → explicit retry with the same payload
 → server returns the original order when the first write already succeeded
```

requestId只在用户第一次点击最终“确认下单”时生成。Preview和“确认订单信息”阶段不会提前占用key。生成格式为 `ord-<base36 timestamp>-<three random segments>`，只使用服务端允许的字符并满足8～128字符限制；它用于降低订单意图ID碰撞概率，不是加密令牌、授权信息或orderNo，也不显示在UI和日志中。

第一次提交同时冻结以下安全结构：

```json
{
  "requestId": "ord-...",
  "clientId": "anon-...",
  "items": [{ "dishId": "dish-4", "quantity": 2 }],
  "expectedPreview": {
    "items": [{ "dishId": "dish-4", "quantity": 2, "unitPrice": 12, "lineTotal": 24 }],
    "totalQuantity": 2,
    "totalPrice": 24
  },
  "remark": ""
}
```

冻结expectedPreview不会让客户端价格成为订单事实。服务端仍会重新读取菜品状态和价格，并比较用户确认的预期。冻结的目的只是保证同一requestId的每次重试具有同一request fingerprint。

### 明确失败与结果未知

以下安全业务错误明确使旧Proposal失效：`ORDER_CONFIRMATION_STALE`、`ORDER_DISH_UNAVAILABLE`、`ORDER_DISH_NOT_FOUND`、`ORDER_ITEMS_INVALID`、`ORDER_IDEMPOTENCY_CONFLICT`、`ORDER_REQUEST_ID_INVALID`。页面保留Cart，清除Proposal、确认状态、requestId与冻结payload，并要求重新预览。

网络中断、timeout、transport错误及通用 `ORDER_CREATE_FAILED` 可能发生在服务端已经写入之后，因此按结果未知处理。页面保留Cart和全部订单意图状态，显示“重试确认下单”，并且只允许用原冻结payload重试。此时页面阻止新Agent Query、新Preview和本地取消，避免让用户误以为订单一定没有创建；若其他Tab修改Cart，重试仍对应之前已经确认的订单意图。

### 当前恢复边界

V5.6B只提供当前Agent页面生命周期内的安全重试。页面刷新、小程序重启或页面状态被销毁后，未决requestId和冻结payload不会恢复；当前没有localStorage持久化提交恢复。该限制不影响服务端已建立的唯一约束，但客户端此时无法自动找回旧key，后续需要独立设计persistent submission recovery。

## V5.6B真实微信主链验收

正式微信Checkout已经按以下链路完成真实验收：

```text
Pinia Cart
 → Server Order Preview
 → 确认订单信息
 → Final Explicit Order Confirmation
 → Generate requestId Once
 → Freeze Submission Payload
 → orders.createConfirmedOrder()
 → Canonical Fingerprint
 → Fresh Server Validation / Pricing
 → Expected Preview Comparison
 → Persist Order
 → request_id_unique UNIQUE sparse index
 → Server Success
 → Cart Clear
```

通过正式微信流程创建的最新验收订单在真实uniCloud `orders` 集合中满足：

- requestId存在且非空，格式为 `ord-...`。
- requestFingerprint存在且非空。
- `totalPrice=24`。
- `totalCount=2`。
- `status=pending`。

文档不记录完整requestId或requestFingerprint。上述字段证明V5.6B正式前端已经把V5.6A服务端幂等能力接入真实用户订单主链。

本次微信验收没有人为制造“服务端成功但响应丢失”。Retry证据由三部分组成：V5.6A真实uniCloud admin验证同key同payload返回同一orderNo且不新增记录；V5.6B自动化测试验证结果未知时保留key和冻结payload并原样重试；真实微信订单则验证正式Checkout确实写入了非空requestId与requestFingerprint。

结果未知时的完整恢复路径为：

```text
Keep requestId / Cart / Proposal / Frozen Payload
 → Retry Same Frozen Payload
 → Server Replay
 → Return Same Persisted Order
 → No Duplicate Order
```

## 真实uniCloud验收

以下结果已在真实阿里云uniCloud环境完成验证。

### Same requestId + same fingerprint

第一次请求创建了真实订单。第二次使用完全相同的requestId、clientId、items、expectedPreview和remark：

- 返回第一次创建的同一个orderNo。
- 没有生成第二个orderNo。
- `orders` 集合没有增加第二条记录。
- retry没有重复执行persist。

这确认相同requestId与相同requestFingerprint具备服务端replay semantics。

### Same requestId + different intent

继续复用相同requestId，但改变quantity、expectedPreview等fingerprint输入后，真实调用返回 `ORDER_IDEMPOTENCY_CONFLICT`：

- 没有返回修改后payload对应的新订单。
- 没有创建第二张订单。
- 第一次订单保持不变。
- 响应没有泄露requestFingerprint。

requestId只能表示同一次订单创建意图，不能复用于不同payload。

### 准确边界

真实验收证明的是：同一order creation intent在相同requestId和fingerprint下具有服务端幂等重放语义。它不等于exactly-once分布式事务、支付幂等、全局事务隔离或分布式锁。

## 已执行的部署顺序

本次真实环境按以下安全顺序完成部署；其他环境应保持相同顺序：

1. 在uniCloud Web控制台进入阿里云服务空间 `xlimao`，打开云数据库 `orders`，确认现有索引 `client_time_desc` 和 `order_no_unique`。
2. 上传更新后的 `orders.schema.json`，确认requestId和requestFingerprint均为可选字段。
3. 通过HBuilderX上传 `orders.index.json`，或在控制台索引管理中手动新增：名称 `request_id_unique`，字段 `requestId` 升序，唯一索引开启，稀疏索引开启。
4. 等待索引建立成功，再次确认 `_id_` 与三个业务索引都存在，且 `request_id_unique` 同时为unique和sparse。
5. 上传部署更新后的 `orders` 云对象；确认 `order-idempotency.js` 随云对象一起部署。
6. 上传部署仅供开发验收的 `order-idempotency-admin` 云函数。
7. 不需要修改或回填历史orders，也不要重新初始化categories、dishes或orders。

## 后续复验参数

通过HBuilderX“上传并运行云函数”执行 `order-idempotency-admin`。示例参数：

```json
{
  "clientId": "现有合法anon-clientId",
  "requestId": "test-id-001",
  "items": [{ "dishId": "dish-4", "quantity": 2 }],
  "expectedPreview": {
    "items": [{ "dishId": "dish-4", "quantity": 2, "unitPrice": 12, "lineTotal": 24 }],
    "totalQuantity": 2,
    "totalPrice": 24
  },
  "remark": ""
}
```

复验前应从实时Preview确认价格仍为12元，并使用新的、尚未占用的requestId。

1. 第一次执行：orders数量N→N+1，记录orderNo X。
2. 相同参数再次执行：返回同一个orderNo X，数量仍为N+1。
3. 保持requestId不变，同时把quantity及expectedPreview改成一致的另一组值：应返回 `ORDER_IDEMPOTENCY_CONFLICT`，数量不变。
4. 并发安全主要由自动化并发测试和数据库unique约束证明；本阶段不要求在真实云端做压力测试。

不要提交本地 `*.param.json`。V5.6B正式Checkout已经生成并复用requestId，并完成真实微信订单主链验收。本阶段没有支付、持久化恢复或Agent Order Tool。
