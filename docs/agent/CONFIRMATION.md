# V5.4：用户确认与前端购物车执行

## 阶段目标

V5.3只生成由服务器校验的Pending Action。V5.4在微信小程序增加明确确认按钮，并在确认时再次读取实时菜单，最后复用现有Pinia购物车执行唯一允许的 `add_to_cart` 动作。

```text
Single Query
 → agent.run(query)
 → Server Validated Pending Action
 → Explicit UI Confirmation
 → Fresh Menu Revalidation
 → Pinia Cart Mutation
 → Success State
```

当前实现是一次Query、一次Agent结果和一次可选动作确认，不是多轮聊天。用户输入“确认”“好的”或“加吧”不会成为执行入口；只有当前页面确认卡上的按钮能触发购物车修改。

## 为什么不让LLM直接执行副作用

LLM负责理解意图、选择Tool并生成动作提案，但模型输出不是授权。模型可能误解数量、选择售罄商品或重复发起动作，因此Function Calling只允许调用无副作用的 `prepare_add_to_cart`。

真正的购物车修改必须同时满足：

1. 正式 `agent.run()` 返回结构合法的Pending Action。
2. 用户点击“确认加入购物车”。
3. 确认期间重新读取真实菜单并通过状态与价格检查。
4. 前端只通过显式分支调用现有 `cartStore.addDish(dish, quantity)`。

代码不使用eval、动态函数名或由 `pendingAction.type` 任意选择Store方法。本阶段唯一允许的动作类型是 `add_to_cart`。

## Pending Action前端校验

页面执行前严格检查以下字段，且不接受额外字段：

| 字段 | 规则 |
| --- | --- |
| type | 必须等于 `add_to_cart` |
| dishId | trim后非空字符串 |
| name | trim后非空字符串 |
| quantity | 1～20的整数 |
| unitPrice | 有限且不小于0，最多两位小数 |
| totalPrice | 有限且不小于0，最多两位小数 |
| requiresConfirmation | 必须严格等于true |

金额转换为整数分后检查 `unitPrice × quantity === totalPrice`。非法提案不会显示可执行确认卡，也不会修改购物车，页面提示“待确认操作无效，请重新发起。”

## 确认时重新读取实时菜单

Pending Action只代表提案生成时的数据库快照。用户可能在页面停留，期间菜品状态或价格可能变化，所以点击确认后必须通过现有 `getDishes()` 重新读取菜单：

- 菜品不存在或不再 `on_sale`：旧提案立即失效，不修改购物车，提示菜品状态已变化。
- 当前价格与提案单价不同：旧提案立即失效，不使用旧价或静默接受新价，提示重新确认最新价格。
- 菜品仍在售且价格一致：使用实时菜品对象和提案中的已校验数量调用现有Pinia Store。
- 菜单暂时加载失败：不修改购物车，保留提案供用户重新点击确认。

这保证用户确认的是页面上看到的数量和价格。例如用户确认 `2 × 12 = 24` 时，不能在价格已变为13元后静默加入。

这是对Pending Action生成与实际使用之间 **time-of-check / time-of-use** 数据变化的保护。它能在前端执行前发现商品售罄、下架或价格变化，但不能被描述成完全解决并发一致性：购物车仍是客户端Pinia状态，最终创建订单时仍由orders云对象再次校验实时数据库。

## 防重复与生命周期

- 点击确认后，在第一个异步请求前同步设置 `confirming=true`，确认、取消和新Query按钮全部禁用。
- 成功后清除Pending Action，同一提案不能再次执行。
- 取消只清除本地提案，不调用Qwen，也不修改购物车。
- 提交新Query前清除旧回答、旧提案和旧动作状态。
- Pending Action不从URL、用户文本或本地存储恢复；页面刷新后可以消失。

## Pending Action不是授权Token

Pending Action是服务端验证过的Action Proposal，但不是cryptographic authorization token、持久事务或服务器购物车命令。购物车仍是客户端Pinia状态，本阶段没有action token、服务端Pending Action存储、云端购物车或数据库写入。

购物车数据最终提交订单时，现有orders云对象仍必须重新查询菜品、校验在售状态和真实价格。不能因为购物车条目来自Agent而降低订单服务端校验。

## 完整Action安全链

```text
User Query
 → Ordering Agent
 → Qwen Function Calling
 → Read Tool / Action Preparation Tool
 → Server Revalidation
 → Pending Action
 → requiresConfirmation=true
 → WeChat Confirmation UI
 → Fresh Menu Revalidation
 → Pinia Cart Mutation
 → Real Cart State Change
```

各层职责：

- **LLM**：理解用户目标并选择Tool，不能直接执行购物车副作用。
- **Server Tool**：重新读取菜品、状态和价格，校验数量并计算金额，生成可信Pending Action。
- **Frontend**：只允许显式 `add_to_cart`；必须由用户点击按钮，并在执行前再次读取实时菜单。
- **Pinia**：只有动作结构、用户确认和实时菜单检查全部通过后，才产生真实购物车状态变化。

## 当前能力边界

已实现代码：正式Agent页面、单次Query、回答展示、Pending Action确认卡、显式确认、实时菜单复核、价格变化失效、售罄失效、Pinia数量执行、防双击、取消和成功状态。

尚未实现：多轮会话、自然语言确认、跨页面Pending Action持久化、action token、服务端Cart Tool、Order Tool、结算和支付。

**V5.4 frontend confirmation flow has been integrated and validated in the WeChat mini-program.**

## 真实微信开发者工具验收

### Scenario A：明确确认后执行

用户在“智能点餐 Agent”页面输入“把柠檬茶加两杯到购物车”。真实Agent结果包含柠檬茶、quantity=2、unitPrice=12、totalPrice=24、`requiresConfirmation=true`，微信页面显示待确认卡。

点击确认之前购物车数量不变。点击“确认加入购物车”后，前端重新读取真实菜单，确认dish仍存在、仍为 `on_sale`、价格仍为12元且提案金额有效，再调用 `cartStore.addDish(currentDish, 2)`。真实购物车准确增加2杯，没有少加、重复增加或自动执行。

该案例真实跑通：

```text
Agent Action Proposal
 → Explicit User Confirmation
 → Fresh Menu Revalidation
 → Real Pinia Cart Side Effect
```

### Scenario B：取消不产生副作用

再次生成同一Pending Action后点击“取消”，没有再次调用Qwen，没有执行菜单复核，没有修改Pinia，购物车数量保持不变，Pending Action被清除。这证明提案本身不产生副作用，只有明确确认才允许执行。

### Scenario C：售罄商品不进入确认链

用户输入“把酸梅汤加到购物车”，真实菜单状态为 `sold_out`。Agent正确识别售罄，没有成功Pending Action；微信页面没有显示确认卡，购物车没有变化。售罄商品未进入前端确认执行链路。
