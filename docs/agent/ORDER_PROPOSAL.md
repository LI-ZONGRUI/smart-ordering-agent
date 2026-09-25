# V5.5B：Checkout Proposal Integration

## 阶段边界

V5.5B把当前Pinia购物车接到已经真实验证的服务端订单预览：

```text
Pinia Cart
 → 只提取 dishId / quantity
 → orders.previewOrder(items)
 → Server Validated Checkout Proposal
 → Order Pending Action
 → Explicit Information Confirmation
 → STOP
```

**Checkout proposal flow has been integrated and validated in the WeChat mini-program.** 本阶段不会调用 `orders.createOrder()`，不会写orders集合、清空购物车、生成订单号、跳转订单页或发起支付。

## 为什么Preview不经过Qwen

订单预览属于确定性的交易准备边界：

- 购物车是客户端Pinia中的当前真实状态，Agent云端不维护另一份购物车。
- 客户端只提交dishId和quantity，不能让模型或本地展示价格成为订单事实。
- 菜品存在性、在售状态、名称、单价和金额必须由orders服务端读取数据库并计算。
- 结算不需要为了“像Agent”而让模型参与每个安全关键步骤。

Agent继续负责自然语言菜单和购物车意图；Checkout Flow直接使用正式orders云对象。项目没有新增 `preview_order` Agent Tool，也没有把Pinia状态发送给Qwen。

## 前端输入与响应校验

`src/services/orders.js` 从购物车仅构造：

```json
[
  {
    "dishId": "dish-4",
    "quantity": 2
  }
]
```

前端先验证1～30种菜品、非空dishId、不重复，以及1～99整数数量。正式调用为：

```js
uniCloud.importObject('orders', { customUI: true }).previewOrder(items)
```

它不会调用开发验收用的 `order-preview-admin`。服务端仍是最终安全边界。

成功响应还会在前端做结构防御：只接受规定的Preview和item字段；数量必须与请求一致；unitPrice、lineTotal、totalPrice必须是非负且最多两位小数，并转成整数分校验行金额和总金额；totalQuantity必须等于数量之和；`requiresConfirmation` 必须严格为true。畸形或带未知动作字段的响应不会生成待确认状态。

## Order Pending Action

通过校验后，页面只在内存中生成：

```json
{
  "type": "create_order",
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
```

它是checkout proposal，不是订单，不包含orderId、orderNo、订单状态或支付状态，也不写localStorage。

Agent页面中的 `cartPendingAction` 和 `orderPendingAction` 是两个独立状态。新的Agent Query会清除旧订单预览；取消只清除订单提案，不修改购物车，也不调用Qwen或订单创建接口。

## 信息确认与购物车快照

生成Preview时保存仅含dishId和quantity的购物车快照。用户点击“确认订单信息”时，页面重新读取当前Pinia购物车，按dishId和quantity精确比较：

- 数量变化、菜品新增或删除都会使旧Preview失效。
- 失效时清除提案并提示“购物车已发生变化，请重新生成订单预览。”
- 快照一致时只设置页面内的 `orderProposalConfirmed=true`，显示“订单信息已确认，尚未创建订单。”

该确认不调用createOrder、不清空购物车，也不表示价格被锁定。即使快照未变，未来V5.5C正式创建订单时仍必须重新读取dishes、检查状态和价格、重新计算金额；若价格变化，需要重新让用户确认。

快照检查是客户端Checkout Proposal的一致性保护，不是数据库级并发控制或事务锁。真正创建订单时仍需要服务端重新校验。

## 真实微信验收

### Scenario A：正常订单预览与信息确认

真实购物车为“柠檬茶 × 2”。用户在“智能点餐 Agent”页面点击“生成订单预览”，正式前端调用：

```json
[
  {
    "dishId": "dish-4",
    "quantity": 2
  }
]
```

真实微信端显示柠檬茶数量2、单价12元、小计24元、总数量2和合计24元。点击“确认订单信息”后显示“订单信息已确认，尚未创建订单。”

验收同时确认：购物车保持不变，没有清空Cart；orders集合没有新增记录；没有生成orderId或orderNo；没有调用 `createOrder()`。真实链路为：

```text
Pinia Cart
 → Server Preview
 → Order Pending Action
 → Explicit Information Confirmation
 → STOP
```

### Scenario B：Cart Snapshot Invalidation

由于当前页面生命周期和TabBar导航行为，本次真实微信验收没有稳定复现“生成旧Preview → 跨页修改Cart → 返回同一个仍保留旧Preview的Agent页面 → 再确认”。没有为此修改导航结构。

该安全边界由自动化测试覆盖，不表述为本次真实UI复现：quantity改变、item新增或item删除时，旧Preview都会失效，不能继续确认，并提示“购物车已发生变化，请重新生成订单预览。”

### Scenario C：不可用菜品

真实验收中将购物车里的测试菜品临时设为 `sold_out`，再点击“生成订单预览”。微信端显示“购物车中有菜品当前不可用，请返回购物车处理。”

没有生成可确认的Order Pending Action，没有显示“确认订单信息”卡，没有创建订单，购物车也没有被结算流程修改。测试完成后，该测试菜品状态已恢复为 `on_sale`。

这验证了正式前端会消费 `orders.previewOrder()` 的安全业务错误，不会为不可用商品生成可确认订单提案。

## 安全错误

前端只映射固定错误码到友好文案：

| errCode | 页面语义 |
| --- | --- |
| `ORDER_ITEMS_INVALID` | 购物车内容无效，请返回检查 |
| `ORDER_DISH_NOT_FOUND` | 菜品已下架，请重新选择 |
| `ORDER_DISH_UNAVAILABLE` | 菜品当前不可用，请返回处理 |
| `ORDER_PREVIEW_FAILED` | 暂时无法生成预览，请稍后重试 |

未知错误统一泛化，不展示stack、数据库信息、云函数路径或原始异常。

## 下一阶段

V5.5C（尚未实现）：

```text
Explicit Order Confirmation
 → orders.createOrder()
 → 服务端再次校验与计价
 → Persisted Order
```

V5.5B停在信息确认，不实现订单持久化、Agent Order Tool或支付。

阶段状态：

- V5.5A：Server-validated Order Preview，已完成。
- V5.5B：Pinia Cart → Preview → Order Pending Action → Explicit Information Confirmation → STOP，已完成并通过真实微信验收。
- V5.5C：Final Order Confirmation → Server Revalidation → createOrder → Persisted Order，下一阶段，尚未实现。
