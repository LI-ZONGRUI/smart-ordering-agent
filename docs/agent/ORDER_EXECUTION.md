# V5.5C：Explicit Final Order Confirmation

## 阶段目标

V5.5C第一次在Agent页面的Checkout流程中产生服务端持久化副作用：

```text
Pinia Cart
 → Server Preview
 → Information Confirmation
 → Final Explicit Order Confirmation
 → orders.createConfirmedOrder()
 → Fresh Server Validation / Pricing
 → Expected Preview Comparison
 → Persisted Order
 → Cart Clear
```

**Confirmed order execution has been validated in the WeChat mini-program and the real uniCloud orders collection.** 当前没有支付、Agent Order Tool或模型驱动的订单写入。

## 两个确认边界

项目包含两个不同的用户确认边界：

1. Cart Action Confirmation：确认Agent准备的加购提案，实时复核菜品后修改Pinia购物车。
2. Order Execution Confirmation：先确认服务端订单预览，再单独点击“确认下单”产生持久订单。

“确认订单信息”只表示用户看过当前Preview；“确认下单”才会调用正式订单创建接口。最终事务不经过Qwen：自然语言理解和Tool orchestration适合LLM，实时计价和持久化属于确定性的交易边界。

## 正式输入

前端调用正式orders云对象的 `createConfirmedOrder(payload)`，不调用admin入口。payload只包含：

```json
{
  "clientId": "anon-...",
  "items": [
    {
      "dishId": "dish-4",
      "quantity": 2
    }
  ],
  "expectedPreview": {
    "items": [
      {
        "dishId": "dish-4",
        "quantity": 2,
        "unitPrice": 12,
        "lineTotal": 24
      }
    ],
    "totalQuantity": 2,
    "totalPrice": 24
  },
  "remark": "",
  "requestId": "ord-..."
}
```

items从第一次点击最终确认时的当前Pinia购物车提取，不发送客户端name、price或totalPrice。expectedPreview来自已通过前端结构校验并由用户确认的Order Pending Action；它是不可信的用户预期，不是订单价格来源。requestId在这次最终提交前生成一次，同时冻结clientId、items、expectedPreview和remark；结果未知后的重试不再读取可能已经变化的Cart，而是复用完全相同的冻结payload。

## 服务端重新校验和比较

`createConfirmedOrder()` 在同一次请求中依次执行：

1. 严格校验payload和expectedPreview，拒绝额外字段、重复ID、非法数量及不一致金额。
2. 调用共享 `validateAndPriceOrderItems()` 重新读取dishes。
3. 重新检查菜品存在和 `on_sale` 状态。
4. 读取数据库实时价格，以整数分重新计算每行和总额。
5. 以dishId建立Map，不依赖数组顺序，逐项比较dishId集合、quantity、unitPrice、lineTotal、totalQuantity和totalPrice。
6. 全部一致后调用共享 `persistPricedOrder()`，沿用原orders快照结构写入一条订单。

不能只比较总价。两个菜品一涨一降可能让总价不变，逐项比较仍会返回 `ORDER_CONFIRMATION_STALE`。服务端不会使用expectedPreview中的价格创建订单。

## 错误与失效

| errCode | 含义 | 前端处理 |
| --- | --- | --- |
| `ORDER_ITEMS_INVALID` | 请求或确认结构无效 | 保留Cart，清除旧提案 |
| `ORDER_DISH_NOT_FOUND` | 菜品已不存在 | 保留Cart，清除旧提案 |
| `ORDER_DISH_UNAVAILABLE` | 菜品不再可用 | 保留Cart，清除旧提案 |
| `ORDER_CONFIRMATION_STALE` | 实时计价与已确认Preview不同 | 保留Cart，要求重新预览和确认 |
| `ORDER_IDEMPOTENCY_CONFLICT` | requestId已对应不同订单意图 | 保留Cart，清除旧提案和requestId |
| `ORDER_REQUEST_ID_INVALID` | requestId不符合服务端合同 | 保留Cart，清除旧提案和requestId |
| `ORDER_CREATE_FAILED` | 创建结果可能无法确认 | 保留Cart、提案、requestId和冻结payload，用同一payload重试 |

任何失败都不会清空购物车。未知异常不返回stack、数据库信息、内部路径或原始错误。

## 成功后的前端状态

最终点击前再次比较当前Cart与预览时保存的dishId/quantity快照。变化时不发服务器请求，直接让旧提案失效。

请求开始前同步设置 `submittingOrder=true`，禁用最终确认、取消、生成Preview和Agent Query，阻止客户端双击。只有服务端返回经过校验的成功订单后，页面才：

1. 调用现有Pinia `clearCart()`。
2. 清除Order Pending Action和信息确认状态。
3. 显示“下单成功”和真实orderNo。
4. 提供“查看订单”按钮。

页面不显示数据库内部 `_id`，也不自动跳转。

## 共享逻辑与旧接口兼容

旧确认订单页继续调用原 `createOrder()`，其参数、普通Error行为和原始订单返回结构保持不变。两个创建入口共用：

- `validateAndPriceOrderItems()`：实时菜品校验与整数分计价。
- `persistPricedOrder()`：订单号、快照、pending状态、时间和orders写入。

没有创建第二套订单schema。

## 一致性与幂等边界

重新计价、确认值比较和写入位于同一次服务端请求中，显著缩小Preview到Create之间的数据变化窗口，但当前没有库存事务或serializable transaction，不能描述为完全解决数据库并发一致性。

UI继续用 `submittingOrder` 阻止普通双击。V5.6A已经为 `createConfirmedOrder()` 实现可选requestId、request fingerprint和阿里云稀疏唯一索引，并通过真实uniCloud同键重放及冲突拒绝验收。V5.6B正式前端会生成并传递requestId：成功和幂等Replay走同一成功路径；明确业务失败清除旧key；网络、timeout和通用创建失败保留原key与冻结payload供显式重试。该保护当前只覆盖页面生命周期，不包含刷新或小程序重启后的持久恢复。**Server-side idempotent order creation has been integrated into and validated through the real WeChat checkout flow.** 详见 [Order Idempotency](ORDER_IDEMPOTENCY.md)。

## 真实微信与uniCloud验收

以下三个场景均已在微信开发者工具和真实uniCloud环境完成验收。

### Scenario A：持久化成功

购物车中的柠檬茶两杯生成了服务端Preview：单价12元、行金额24元、总数量2、总价24元。用户依次点击“确认订单信息”和“确认下单”后：

- 页面显示“下单成功”和真实订单号 `OD1790357975859B4A2B5`。
- uniCloud `orders` 集合出现同一订单号的新记录。
- 持久化记录的 `totalPrice=24`、`totalCount=2`、`status=pending`。
- 页面订单号与数据库订单号一致。
- 服务器返回并经前端校验成功后，Pinia Cart才被清空。

这验证了 `createConfirmedOrder()` 的重新校验、确认值比较、持久化、真实订单号返回及成功后清空Cart的完整链路。

### Scenario B：价格变化保护

用户确认的Preview为柠檬茶两杯、单价12元、总价24元。随后在真实dishes数据库中临时把单价从12元改为13元，再点击“确认下单”。页面提示“订单信息已变化，请重新生成预览并确认。”，并确认：

- 没有创建新订单，也没有按26元静默下单。
- Cart保持不变。
- 旧Order Proposal失效。
- 测试后价格已恢复为12元。

这验证了expectedPreview只是用户确认过的预期值。服务端仍以最新数据库价格重新计价，不一致时返回 `ORDER_CONFIRMATION_STALE`。

### Scenario C：售罄变化保护

生成Preview并确认订单信息后，测试菜品在真实数据库中由 `on_sale` 临时改为 `sold_out`，再点击最终确认。服务端重新校验后拒绝创建订单，并确认：

- `orders` 集合没有新增对应订单。
- Cart没有被清空。
- 旧Order Proposal失效。
- 页面显示友好的菜品不可用提示。
- 测试后状态已恢复为 `on_sale`。

这验证了Preview阶段可售不代表最终创建时仍然可售，持久化之前必须再次执行实时菜品校验。

### Scenario D：正式Checkout启用服务端幂等

V5.6B部署后再次通过正式微信流程完成柠檬茶两杯的Preview、信息确认与最终确认。真实uniCloud `orders` 记录显示：

- requestId存在且非空，使用 `ord-...` 格式。
- requestFingerprint存在且非空。
- `totalPrice=24`、`totalCount=2`、`status=pending`。
- 服务端返回合法成功订单后，前端显示真实orderNo并清空Cart。

这里不记录完整requestId或requestFingerprint，也不声称微信端人为复现了响应丢失。服务端同键重放由V5.6A真实admin验收证明；前端同key、同冻结payload重试由V5.6B自动化测试证明。

## 已验收的完整安全链

```text
Pinia Cart
 → orders.previewOrder()
 → Fresh Server Validation / Pricing
 → Server-validated Order Preview
 → Explicit Information Confirmation
 → Final Explicit Order Confirmation
 → Generate requestId Once
 → Freeze Submission Payload
 → orders.createConfirmedOrder()
 → Canonical Fingerprint / Unique Sparse Index
 → Fresh Server Validation / Pricing Again
 → Expected Preview Comparison
 → Persisted Order
 → Real orderNo
 → Server Success
 → Pinia Cart Clear
```

Preview和Create是两个独立安全阶段。最终交易执行属于确定性的服务端业务执行边界，由明确的用户操作触发，不由LLM自主调用订单Tool；这里不表示已经具备数据库事务或serializable隔离。
