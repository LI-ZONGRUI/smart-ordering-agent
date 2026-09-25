# V5.5A：服务端订单预览基础

## 阶段目标

V5.5A把现有订单创建中的实时菜品校验和计价规则抽成共享核心，并新增只读的 `orders.previewOrder(items)`：

```text
Cart
 → Server Order Preview
 → Fresh Dish Validation
 → Server Pricing
 → requiresConfirmation=true
 → STOP
```

**Server-validated order preview has been validated against the real uniCloud menu data.** 本阶段没有Agent Order Tool、订单待确认动作、订单前端自动执行、自动结算或支付能力。

## Preview输入与规则

客户端只能提交：

```json
[
  {
    "dishId": "dish-4",
    "quantity": 2
  }
]
```

- items必须包含1～30种菜品。
- dishId必须是非空字符串；重复dishId拒绝，不合并。
- quantity必须是1～99的整数，与现有 `createOrder()` 一致。
- Preview严格拒绝name、price、status、lineTotal等额外字段。
- 服务端根据dishId重新查询dishes，拒绝不存在或非 `on_sale` 的菜品。
- 菜名与单价只取当前数据库值，客户端缓存不作为依据。

金额先转为整数分，再执行 `unitCents × quantity` 和逐行求和，最后转回元。这避免直接使用JavaScript浮点数进行订单乘加。

## Preview输出

```json
{
  "errCode": 0,
  "preview": {
    "items": [
      {
        "dishId": "dish-4",
        "name": "柠檬茶",
        "quantity": 2,
        "unitPrice": 12,
        "lineTotal": 24
      }
    ],
    "totalQuantity": 2,
    "totalPrice": 24,
    "requiresConfirmation": true
  }
}
```

返回值不含orderId、orderNo、订单状态或支付状态。`requiresConfirmation=true` 表示这是等待确认的结算提案，不代表订单已经创建。

## Preview与Create共用规则

`previewOrder()` 与 `createOrder()` 都调用 `orders/order-pricing.js` 中的 `validateAndPriceOrderItems()`。共享核心负责：

1. 校验items、dishId、quantity和重复ID。
2. 重新读取实时dishes。
3. 校验菜品存在且在售。
4. 从数据库读取菜名和价格。
5. 按整数分计算行金额、总数量和总价。

Preview只返回结果，不写数据库。Create收到正式创建请求时会再次调用共享核心，重新查询状态和价格，然后才生成订单号、保存快照并写入orders。不能把较早的Preview当成未来价格或状态的承诺。

例如Preview时柠檬茶为12元，创建前变成13元，Create会按13元重新校验和计价。后续阶段才能决定金额变化后的再次确认交互。

## 无副作用边界

`previewOrder()` 只读取dishes：

- 不调用 `orders.add/update/remove`。
- 不生成订单记录或订单号。
- 不修改菜品、库存、购物车或订单状态。
- 不创建reservation、payment intent或authorization token。

订单比客户端购物车具有更严格的边界，因为创建订单会产生服务端持久化业务记录。订单预览用于在持久化之前展示由服务器验证的实时明细；真正创建时仍需再次校验，避免预览与创建之间的状态或价格变化被忽略。

Order Preview的准确性质是 **server-validated checkout proposal**。它不是persisted order、order transaction、reservation、payment intent、authorization token或immutable price guarantee。`requiresConfirmation=true` 只表示后续仍需明确确认，不表示订单已经创建。

## 错误合同

共享计价核心以私有业务错误类型区分可安全暴露的业务失败和未知内部异常：

| errCode | 固定安全文案 | 含义 |
| --- | --- | --- |
| `ORDER_ITEMS_INVALID` | 订单菜品或数量无效 | items、dishId、quantity、额外字段或重复dishId不符合规则 |
| `ORDER_DISH_NOT_FOUND` | 未找到对应菜品 | 实时dishes中不存在对应菜品 |
| `ORDER_DISH_UNAVAILABLE` | 当前菜品不可用 | 菜品当前不是 `on_sale`，包括售罄 |
| `ORDER_PREVIEW_FAILED` | 订单预览未完成，请稍后重试 | 未知数据库或内部异常 |

只有前三个固定白名单业务错误允许由管理验收入口恢复。未知 `error.code`、`error.message`、stack和数据库异常不会直接返回。Create继续使用原有普通Error文案，避免改变已经工作的订单页面错误处理；Preview与Create仍共享相同校验和计价规则。

## 当前订单阶段架构

```text
Pinia Cart
 → Order Preview Request
 → orders.previewOrder()
 → Shared Validation / Pricing
 → Fresh dishes DB
 → Server-priced Order Preview
 → requiresConfirmation=true
 → STOP
```

下一阶段设想为“明确订单确认 → 再次服务端校验/计价 → createOrder()”。该确认链、Agent Order Tool、Order Pending Action和Agent驱动创建订单目前均未实现。

## 真实uniCloud验收

V5.5A已通过HBuilderX的 `order-preview-admin` 在真实uniCloud阿里云空间完成验收。

### Case 1：正常Order Preview

真实输入：

```json
{
  "items": [
    {
      "dishId": "dish-4",
      "quantity": 2
    }
  ]
}
```

真实返回：

```json
{
  "errCode": 0,
  "preview": {
    "items": [
      {
        "dishId": "dish-4",
        "name": "柠檬茶",
        "quantity": 2,
        "unitPrice": 12,
        "lineTotal": 24
      }
    ],
    "totalQuantity": 2,
    "totalPrice": 24,
    "requiresConfirmation": true
  }
}
```

客户端只提供dishId和quantity；服务端从真实dishes读取“柠檬茶”和12元单价、确认可售并计算 `2 × 12 = 24`。结果不含orderId、订单状态或支付状态。

### Case 2：售罄商品

真实输入：

```json
{
  "items": [
    {
      "dishId": "dish-8",
      "quantity": 1
    }
  ]
}
```

真实数据库中dish-8为酸梅汤，状态是 `sold_out`。错误语义修复后的真实结果：

```json
{
  "errCode": "ORDER_DISH_UNAVAILABLE",
  "errMsg": "当前菜品不可用"
}
```

该调用没有成功Preview，售罄菜品未进入订单预览。

### Case 3：未观察到订单写入

完成上述Preview调用后检查真实uniCloud orders集合，没有看到本次V5.5A验收创建的新订单记录。集合中可见的订单时间为：

- `1789805603805`：2026-09-19 16:13:23 +08:00
- `1789827054619`：2026-09-19 22:10:54 +08:00

本次验收日期为2026-09-25，没有出现对应的新记录。这是本次真实验收的观察结果，支持 `previewOrder()` 未写入orders；它不被表述为数据库层的数学证明。

管理入口只转发items给正式 `orders.previewOrder()`，不复制业务校验或计价逻辑。

云函数本地运行参数使用 `*.param.json`，继续由Git忽略。
