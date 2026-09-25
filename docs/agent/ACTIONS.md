# V5.3：Cart Action Proposal 与确认边界

## 目标

V5.3让Ordering Agent理解“加入购物车”意图，并生成一个由服务端校验、等待用户确认的结构化动作。它不会修改Pinia购物车，也不会创建云端购物车、订单或其他持久化记录。

```text
User Intent
 → Agent
 → search_menu
 → prepare_add_to_cart
 → Server Validated Pending Action
 → User Confirmation Required
 → STOP
```

后续阶段才会设计用户确认后如何由微信前端执行Pinia Cart Mutation。本阶段没有确认执行接口、action token、pending_actions collection或服务端会话存储。

## 三类Tool

| 类型 | 当前工具 | 是否产生业务副作用 |
| --- | --- | --- |
| Read Tool | `search_menu`、`list_available_drinks`、`get_dish_detail` | 否，只读取真实菜单 |
| Action Preparation Tool | `prepare_add_to_cart` | 否，只生成待确认提案 |
| Write Tool | 当前没有 | 不适用 |

`prepare_add_to_cart` 不是 `add_to_cart`。Pending Action不代表动作已执行，不能被描述成“已经加入购物车”。

## Tool合同

模型只能提交：

```json
{
  "dishId": "dish-4",
  "quantity": 2
}
```

- `dishId`：必填、trim后非空字符串。
- `quantity`：必填、1～20的整数。
- `additionalProperties: false`：禁止模型提交name、price、status、totalPrice、collection等字段。

参数仍由同一个Executor验证，工具名仍需同时存在于Registry和固定handler映射。没有第二套Action Executor、动态require、eval或客户端指定集合。

## 服务端重新校验

Action Preparation不能信任模型对菜名、状态和金额的陈述。工具按 `dishId` 重新查询 `dishes`，并执行：

1. 菜品不存在：返回 `AGENT_ACTION_DISH_NOT_FOUND`，不生成Pending Action。
2. `status !== on_sale`：返回 `AGENT_ACTION_DISH_UNAVAILABLE`，不生成Pending Action。
3. 在售：读取最新name和price。
4. 将单价转换为整数分，计算 `unitCents × quantity`，再转换为元，避免直接累加浮点金额。
5. 生成服务端可信的Pending Action。

成功结构：

```json
{
  "type": "add_to_cart",
  "dishId": "dish-4",
  "name": "柠檬茶",
  "quantity": 2,
  "unitPrice": 12,
  "totalPrice": 24,
  "requiresConfirmation": true
}
```

该对象只可能从成功的 `prepare_add_to_cart` Tool Result进入Runner。模型在普通文本中自行输出同形JSON，不会成为正式响应的 `pendingAction`。

## Runner边界

Runner会严格校验Pending Action的字段、类型、数量范围、金额精度和 `unitPrice × quantity === totalPrice`。成功后：

- 下一轮只允许模型生成请求确认的自然语言。
- 如果模型再次请求Tool，Runner返回 `AGENT_ACTION_CONFIRMATION_REQUIRED`，不会执行该Tool。
- 正式 `agent.run(query)` 增加服务端Pending Action，但仍不返回Trace。
- 没有动作的原有菜单查询响应不增加 `pendingAction` 字段。

正式成功示例：

```json
{
  "errCode": 0,
  "query": "把柠檬茶加两杯到购物车",
  "answer": "准备将2杯柠檬茶加入购物车，共24元。请确认是否加入。",
  "completed": true,
  "pendingAction": {
    "type": "add_to_cart",
    "dishId": "dish-4",
    "name": "柠檬茶",
    "quantity": 2,
    "unitPrice": 12,
    "totalPrice": 24,
    "requiresConfirmation": true
  }
}
```

这里的 `completed:true` 表示本次Agent提案任务结束，不表示购物车动作已经执行。

## Prompt与单轮限制

System Prompt明确：

- Pending Action只是proposal，必须请求用户确认。
- 不得声称“已加入”“已添加”“下单完成”。
- 当前没有购物车或订单写入能力。
- “它”“刚才那个”“第一个”等指代如果不能从本次单个Query明确解析，应要求用户明确菜品，不得编造dishId。

Prompt是模型行为约束；真正的安全边界仍是服务端没有注册任何Write Tool，且Runner不会从模型自由文本提取可信动作。

## 三层安全模型

购物车动作的安全性不只依赖模型是否做出正确判断，而是由三层共同约束：

1. **LLM Decision**：模型理解用户意图和前序Tool Result，决定是否调用 `prepare_add_to_cart`。这是行为决策层，不是最终安全边界。
2. **Server Revalidation**：`prepare_add_to_cart` 按 `dishId` 重新读取真实 `dishes`，校验菜品是否存在、当前状态，并读取最新name和price；金额由服务端计算。
3. **Confirmation Boundary**：校验成功也只生成 `requiresConfirmation:true` 的Pending Action，随后停止。当前没有执行购物车写入的Tool或接口。

因此，即使模型误判售罄状态并尝试调用Action Preparation Tool，服务端仍会拒绝生成Pending Action。LLM correctness不是唯一安全边界，Server Enforcement必须独立成立。

## 安全错误合同

| errCode | 对外含义 |
| --- | --- |
| `AGENT_ACTION_DISH_NOT_FOUND` | 未找到对应菜品 |
| `AGENT_ACTION_DISH_UNAVAILABLE` | 当前菜品不可用 |
| `AGENT_TOOL_EXECUTION_FAILED` | 未知内部Tool执行异常 |

Executor与管理入口只允许前两个明确列入白名单的业务错误安全穿透，并使用服务器固定文案。任意其他 `error.code`、`error.message`、stack、数据库异常或内部路径均不得直接返回；未知错误继续统一映射为 `AGENT_TOOL_EXECUTION_FAILED`。

## Trace与管理验收

完整管理Trace保留真实Tool Result。`traceOnly:true` 会将 `prepare_add_to_cart` 压缩为：

```json
{
  "step": 2,
  "type": "tool_result",
  "toolName": "prepare_add_to_cart",
  "summary": {
    "pendingAction": {
      "type": "add_to_cart",
      "dishId": "dish-4",
      "name": "柠檬茶",
      "quantity": 2,
      "unitPrice": 12,
      "totalPrice": 24,
      "requiresConfirmation": true
    }
  }
}
```

开发者在HBuilderX使用以下参数完成了真实uniCloud验收：

```json
{
  "query": "把柠檬茶加两杯到购物车",
  "traceOnly": true
}
```

具体Tool调用由Qwen决定，不是服务器固定工作流。本地自动测试仍使用Mock Model，不发起真实Qwen请求；以下结果来自开发者在真实uniCloud环境中的人工验收。

## V5.3真实云端验收

### Case 1：在售商品生成服务端动作提案

用户输入“把柠檬茶加两杯到购物车”。真实Trace为：

```text
Step 1: search_menu({query:"柠檬茶"})
 → dish-4 / 柠檬茶 / on_sale / 12元

Step 2: prepare_add_to_cart({dishId:"dish-4",quantity:2})
 → type=add_to_cart
 → dishId=dish-4
 → name=柠檬茶
 → quantity=2
 → unitPrice=12
 → totalPrice=24
 → requiresConfirmation=true
```

Qwen在观察Read Tool结果后自主进入Action Preparation Tool，并正确解析数量2。价格来自真实数据库，totalPrice由服务端计算，没有发生购物车写操作。

### Case 2：正常响应停在确认边界

同一Query的正常模式回答为：

```text
已为您准备加入：柠檬茶 2 杯，单价 12 元，合计 24 元（在售）。

请确认后我再执行加入购物车。
```

正式响应包含 `pendingAction` 且 `requiresConfirmation=true`。Agent没有声称已经加入购物车；当前状态是Proposal / Pending Confirmation。

### Case 3：模型观察售罄结果后主动停止

用户输入“把酸梅汤加到购物车”。真实Trace先调用 `search_menu({query:"酸梅汤"})`，得到dish-8、14元、`sold_out`，随后Agent停止，没有成功调用 `prepare_add_to_cart`，也没有产生Pending Action。

这说明本次真实模型调用能够根据Tool Result识别售罄并停止，但服务端安全不能只依赖这一行为。

### Case 4：强制调用仍被服务端拒绝

为验证独立安全边界，开发者通过 `agent-tool-admin` 直接调用：

```json
{
  "toolName": "prepare_add_to_cart",
  "args": {
    "dishId": "dish-8",
    "quantity": 1
  }
}
```

第一次真实运行时，`cart-actions` 已返回结构化业务错误，但uniCloud云对象代理把非零 `errCode` 转成异常，管理入口又将其统一泛化为 `AGENT_TOOL_EXECUTION_FAILED`。修复后，Executor和admin只允许白名单业务错误穿透，未知内部错误仍保持通用映射。

最终真实云端复验结果：

```json
{
  "errCode": "AGENT_ACTION_DISH_UNAVAILABLE",
  "errMsg": "当前菜品不可用"
}
```

结果不含Pending Action。这证明即使模型或管理员直接尝试对售罄商品调用Action Preparation Tool，服务端仍会阻止其进入待确认动作。

## V5.3最终能力边界

V5.3已经完成Read-only Menu Tools、原生Function Calling、多步Agent Loop、Action Preparation Tool、服务端菜品重查与金额计算、Pending Action、确认边界、售罄拒绝和安全业务错误合同。

准确描述是：**Agent can prepare a server-validated cart action that requires explicit confirmation before execution.**

当前仍未实现真实购物车Mutation、Pinia确认执行、action token、Pending Action持久化、跨请求多轮确认上下文、Order Tool、结算或支付。不能描述为“Agent已经可以自动加入购物车”。

## 尚未实现

- 用户确认后的动作执行
- Pinia Cart Mutation
- Cart/Order Write Tool
- actionId、签名token、过期机制或服务端Pending Action存储
- 多轮会话记忆
- Agent前端页面
- RAG Tool、推荐Tool或订单能力
