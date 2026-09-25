# V5.2：Read-only Ordering Agent Loop

## 阶段边界

V5.1 建立并真实验证了三个只读菜单工具：`search_menu`、`list_available_drinks`、`get_dish_detail`。V5.2 在这些工具之上增加原生 Function Calling 和有限循环，使模型可以在一次用户任务中根据工具结果继续决策。

V5.2仍然是 **single-user-query Agent task**。它没有前端入口、跨请求会话记忆、多轮聊天历史、购物车或订单写操作。V5.3在同一循环上增加无副作用的购物车Action Preparation Tool，确认协议见 [ACTIONS.md](ACTIONS.md)。

## 架构

```text
agent.run(query) / agent-run-admin
  → shared runAgent(query)
  → qwen3.8-flash Chat Completions
     messages + Registry tools + tool_choice=auto
  → assistant.tool_calls
  → JSON.parse(function.arguments)
  → V5.1 executeTool allowlist + schema validation
  → role=tool + matching tool_call_id
  → 下一轮模型决策
  → final assistant content
```

相关文件：

```text
uniCloud-aliyun/cloudfunctions/
 ├─ agent/
 │   ├─ index.obj.js        正式run与受限runForAdmin入口
 │   ├─ model-client.js     Model Studio HTTP与Function Calling响应解析
 │   ├─ runner.js           有限Agent Loop、messages和安全trace
 │   └─ tools/              V5.1 Registry / Executor / Menu Tools
 └─ agent-run-admin/
     └─ index.js            HBuilderX管理验收入口
```

## Model Studio 调用

`agent` 云对象独立读取以下远程环境变量：

```text
DASHSCOPE_API_KEY
LLM_BASE_URL
AGENT_LLM_MODEL
```

目标模型为 `qwen3.8-flash`，实际值通过 `AGENT_LLM_MODEL` 配置。基础地址来自 `LLM_BASE_URL`，代码只接受没有账号、查询参数和片段的 HTTPS 地址，并在其后添加 `/chat/completions`。代码不硬编码区域地址或密钥，也不读取 `rag` 云对象的配置。

请求使用现有项目已验证的 `uniCloud.httpclient.request`，主要字段为：

```text
model: process.env.AGENT_LLM_MODEL
messages: 当前协议消息
tools: getToolDefinitions()
tool_choice: auto
enable_thinking: false
stream: false
```

没有 OpenAI SDK、Agent Framework 或新依赖。代码不读取、保存或返回 `reasoning_content`。

## Registry 是唯一工具定义来源

每次模型请求的 `tools` 直接调用 `tools/registry.js` 的 `getToolDefinitions()`，没有复制Schema。V5.2真实验收时模型只看到三个Read Tool：

1. `search_menu`
2. `list_available_drinks`
3. `get_dish_detail`

V5.3在同一Registry和Executor中增加 `prepare_add_to_cart`，它只准备待确认动作，不是Write Tool；三个Read Tool行为保持不变。

模型给出的工具名和参数都不可信。`function.arguments` 必须先成为合法 JSON，随后仍经过 V5.1 Executor 的固定 allowlist、参数字段校验与静态 handler 派发。未知工具、额外 `collection`、空查询等不会因为来源是模型而绕过校验。Executor 仍是工具执行的安全边界。

## Messages 协议

收到工具调用时，Runner 会保留模型返回并已白名单清洗的 assistant 消息：

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call-id",
      "type": "function",
      "function": {
        "name": "search_menu",
        "arguments": "{\"query\":\"可乐\"}"
      }
    }
  ]
}
```

服务器执行工具后追加：

```json
{
  "role": "tool",
  "tool_call_id": "call-id",
  "content": "{\"errCode\":0,\"tool\":\"search_menu\",\"query\":\"可乐\",\"count\":0,\"items\":[]}"
}
```

`tool_call_id` 必须与对应调用一致。代码也能处理同一响应中的多个 `tool_calls`，按返回顺序执行并逐个关联；总调用数仍受硬限制。

## 循环与资源限制

- `MAX_AGENT_STEPS = 5`：一次任务最多五轮模型决策。
- `MAX_TOOL_CALLS = 8`：一次任务最多执行八个工具调用。

超过模型轮次返回 `AGENT_MAX_STEPS_EXCEEDED`；单轮或累计工具数超过限制返回 `AGENT_MAX_TOOL_CALLS_EXCEEDED`，不继续调用模型或工具。Tool 执行失败时，本次任务直接返回 V5.1 的安全 Tool error，不让模型把失败改写成成功。

## 事实边界

System Prompt 明确规定菜单商品、存在性、价格、状态、饮料和配料必须来自 Tool Result：

- 查询存在性时先使用 `search_menu`。
- 只有实际看到无匹配，且用户要求替代品或同类推荐时，才继续获取候选。
- `count=0` 表示当前菜单查询没有匹配，不能扩张为餐厅从来不卖。
- `status=sold_out` 表示商品存在但当前售罄，不能表达为不存在。
- 简单问候可以直接回答，不强制调用工具。
- 最终自然语言不得增加 Tool Result 中不存在的价格、销量、健康属性或其他事实。
- 最终回答不主动展示 `dishId`、`categoryId`、`on_sale`、`sold_out`、Tool名称、`tool_call_id`、collection名称或JSON字段名；`on_sale` 转成“在售/可以购买”，`sold_out` 转成“已售罄/暂时无法购买”。结构化字段仍保留在服务器Tool Result和诊断Trace中。

这里通过 Prompt 建立模型行为约束，Tool Result 是权威数据，但 V5.2 尚未建立对最终自然语言的形式化语义证明。真实验收仍需核对回答是否忠实使用工具结果。

## 正式接口与管理 Trace

正式 `agent.run(query)` 接受 trim 后 1～200 个 Unicode 字符。成功只返回：

```json
{
  "errCode": 0,
  "query": "有可乐吗？没有的话推荐点别的喝的。",
  "answer": "模型最终回答",
  "completed": true
}
```

它不返回 messages、System Prompt、trace、模型原始响应或 reasoning。

`agent-run-admin` 只用于 HBuilderX“上传并运行”，通过受限 `runForAdmin()` 调用同一个 Runner。成功时在正式字段之外增加清洗后的 `trace`：

```json
[
  { "step": 1, "type": "tool_call", "toolName": "search_menu", "arguments": { "query": "可乐" } },
  { "step": 1, "type": "tool_result", "toolName": "search_menu", "result": { "errCode": 0, "tool": "search_menu", "query": "可乐", "count": 0, "items": [] } },
  { "step": 2, "type": "tool_call", "toolName": "list_available_drinks", "arguments": {} }
]
```

Trace 不含 API Key、Authorization、System Prompt、隐藏推理或完整模型响应。管理来源限制用于开发验收，并不等同于 uni-id 管理员认证。

HBuilderX输出较长时可向 `agent-run-admin` 传入 `traceOnly: true`。管理函数仍先完整执行同一个 `runForAdmin()`，随后只压缩返回：Tool Call保留参数，Tool Result按类型保留count/found及菜品的dishId、name、status、price。正式 `agent.run()` 不支持该参数，也不返回Trace。

## V5.2 Real Cloud Acceptance

以下四个案例均由开发者在真实uniCloud阿里云空间中使用 `qwen3.8-flash`、真实 `dishes` 数据库和已部署Tool完成，不是本地Mock结果。

### Case A：无匹配后继续寻找替代饮料

Query：

```text
有可乐吗？没有的话推荐点别的喝的。
```

真实compact trace证明了以下流程：

```text
User Query
 → Qwen调用 search_menu({query:"可乐"})
 → Server Tool返回 count=0、items=[]
 → Qwen观察第一次Tool Result后再次决策
 → Qwen调用 list_available_drinks({})
 → Server Tool返回柠檬茶、12元、on_sale
 → Qwen完成任务
```

第二个Tool Call不是服务器写死的fallback。模型先收到 `search_menu` 的真实空结果，再自主决定调用 `list_available_drinks`。这是本项目第一次真实的multi-step Tool-using Agent Loop，也体现了当前Agent Loop与固定Workflow的区别。

### Case B：目标满足后正确停止

Query为“有柠檬茶吗？”。Qwen只调用一次 `search_menu({query:"柠檬茶"})`，真实结果为count=1、dish-4、柠檬茶、on_sale、12元，随后直接完成，没有额外调用饮料列表。该案例证明模型不会为了展示Function Calling而继续无意义调用。

### Case C：区分不存在、售罄和在售

Query为“有酸梅汤吗？”。真实 `search_menu` 结果为count=1、dish-8、酸梅汤、14元、sold_out；最终回答正确说明菜单中存在酸梅汤，但当前已售罄、不能点。这证明Agent能区分“没有匹配”“存在但售罄”和“存在且在售”。

本次回答同时暴露了 `dish-8` 和 `sold_out` 等内部字段。这是用户表达问题，不是Agent Loop或Tool事实错误。V5.2收尾在System Prompt中增加用户表达规则，要求保留内部结构化事实，但把状态转换为自然语言且不展示内部ID。该Prompt修复仍需远程复验，不能由本地Mock证明真实模型一定遵循。

### Case D：无需事实时不调用工具

Query为“你好”。真实结果 `errCode=0`、`completed=true`、trace为空。简单交互无需菜单事实时，Agent可以直接回答，不会无意义访问数据库。

### 正式能力边界

V5.2可准确描述为 **Read-only Ordering Agent**，已经具备LLM Tool Selection、原生Function Calling、Tool Result Observation、多步Tool Orchestration、条件分支、正确停止、无Tool回答和实时只读菜单Grounding。

它仍不是完整自动点餐Agent：没有Cart/Order Write Tool、确认执行协议、跨请求多轮记忆或自主完成下单。V5.3只能准备购物车待确认动作；RAG也尚未注册为Agent Tool。

## V5.3真实Action Proposal验收

V5.3在同一个真实Agent Loop中加入 `prepare_add_to_cart`，已完成以下uniCloud云端验收：

1. “把柠檬茶加两杯到购物车”：Qwen先调用 `search_menu` 得到dish-4、在售、12元，再自主调用 `prepare_add_to_cart`；服务端生成数量2、单价12元、总价24元且 `requiresConfirmation=true` 的Pending Action。
2. 正常模式回答明确请求确认，没有声称已经加入购物车；正式响应携带同一服务端Pending Action。
3. “把酸梅汤加到购物车”：模型从 `search_menu` 观察到dish-8售罄后停止，没有成功Action Preparation和Pending Action。
4. 通过管理入口强制调用售罄dish-8：服务端重新校验后返回 `AGENT_ACTION_DISH_UNAVAILABLE`，且没有Pending Action。该业务错误经过明确白名单安全穿透，未知内部异常仍统一返回 `AGENT_TOOL_EXECUTION_FAILED`。

完整Trace、三层安全模型、错误合同和能力边界见 [ACTIONS.md](ACTIONS.md)。真实结果证明模型可以做出正确决策，也证明安全边界不依赖模型正确性：Action Preparation必须重新读取数据库，成功也只能停在确认边界。

## HBuilderX 部署与验收

1. 在 `agent` 云对象单独配置并保存 `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`AGENT_LLM_MODEL=qwen3.8-flash`。不要假设 `rag` 的环境变量会共享。
2. 上传部署更新后的 `agent` 云对象，确认 `model-client.js`、`runner.js` 和 `tools/` 随包上传。
3. 上传部署 `agent-run-admin` 普通云函数。不需要新数据库或重新初始化 dishes。
4. 在 HBuilderX 对 `agent-run-admin` 使用不含敏感信息的诊断参数：

```json
{
  "query": "有可乐吗？没有的话推荐点别的喝的。",
  "traceOnly": true
}
```

5. 选择“上传并运行云函数”，检查最终 `errCode=0`、`completed=true`，并检查 trace 是否先查询可乐、在无匹配后再列出真实在售饮料。
6. 核对最终回答中的菜名、价格和状态都能在 Tool Result 中找到，不包含未返回的属性。
7. Prompt修复部署后，以正常模式运行 `{"query":"有酸梅汤吗？"}`，确认最终answer使用“已售罄/暂时无法购买”等自然语言，不再展示 `dish-8`、`sold_out`、Tool名称或JSON字段名。可另用 `traceOnly:true` 核对内部真实状态仍然保留。

不要提交 HBuilderX 生成的 `agent-run-admin.param.json`。现有 `**/*.param.json` 忽略规则会继续保护该本地文件。

## 本地验证

本地测试使用可注入 Mock Model，不访问 Model Studio。覆盖两步循环、存在商品、售罄上下文、详情串联、无工具回答、未知工具、参数 JSON、Schema、循环限制、模型错误、正式返回和安全 Trace。

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```
