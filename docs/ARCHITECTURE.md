# 项目整体架构

这是Vue3 + uni-app + Pinia + uniCloud的微信点餐项目，包含传统点餐、独立LLM推荐、单轮RAG知识问答和Ordering Agent。当前Agent后端只生成购物车动作提案；用户在前端明确确认并通过实时菜单复核后，才修改Pinia购物车。它不操作订单，也不是完整自动点餐系统。

## 1. 组件关系

```text
WeChat Mini Program
 └─ Vue3 + uni-app + Composition API
     ├─ 页面：菜单/详情/购物车/确认订单/订单/我的/首页
     ├─ 独立能力页：AI智能点餐、菜单问答
     ├─ Pinia：购物车状态、云端订单查询缓存
     └─ services/：menu.js、orders.js、ai.js、rag.js
          ↓
        uniCloud Cloud Objects
          ├─ menu   → categories、dishes
          ├─ orders → dishes校验 → orders写入/读取
          ├─ ai     → dishes → Model Studio / qwen3.8-flash
          │                      → 菜品ID校验、实时价格计算
          ├─ rag    → knowledge_chunks + dishes
                       ├─ Model Studio / qwen3.7-text-embedding-flash
                       │    Query Embedding（512维）
                       ├─ Exact cosine Top-3（云对象内计算）
                       └─ Model Studio / qwen3.8-flash
                            answerable + evidence IDs
                            → 服务端验证与证据原文渲染
          └─ agent  → Model Studio / qwen3.8-flash Function Calling
                       → Tool Registry → Executor allowlist
                       → Read-only Menu Tools / Action Preparation Tool
                       → dishes → Server Validated Pending Action
                       → UI Confirmation → Live Menu Revalidation
                       → Pinia Cart Mutation
```

Pinia是页面状态层，不是所有网络请求的必经网关。推荐与问答页直接通过services访问云对象；购物车不入库，订单store只缓存云端查询结果。

## 2. 四个Collection

| Collection | 职责与主要数据 |
| --- | --- |
| categories | 分类ID、名称、排序 |
| dishes | 菜名、分类、描述、价格、图片、销量、辣度、配料、在售状态等实时菜单事实 |
| orders | 订单号、菜品快照、数量、金额、备注、状态、clientId、时间 |
| knowledge_chunks | 审核知识及来源、contentHash、版本、模型/维度、向量和时间；knowledgeId唯一 |

这些collection不向小程序开放直接读写。调用云对象不等于已实现完善授权：clientId仅为临时匿名隔离，尚无正式登录与用户认证。

## 3. 传统点餐数据流

1. menu service读取分类、菜品，详情页使用同一正式数据源。
2. Pinia cart维护数量、删除、清空及预览总价，拦截售罄菜品。
3. 确认订单只提交dishId、quantity、remark和clientId；不把客户端价格作为依据。
4. orders云对象重新查询dishes，校验存在与在售状态，按分计算小计和总额，保存菜名、单价、数量、小计快照。
5. 云端创建成功才清空购物车；失败保留。订单按clientId查询，重新打开仍可查看。

历史订单不随菜品改价或改名变化；预览价不替代下单时的服务器真实价格。

## 4. AI推荐、RAG与Agent分工

| 能力 | 输入/上下文 | 输出与信任边界 |
| --- | --- | --- |
| ai.recommend(message) | 预算、口味、食材偏好；当前在售dishes | 模型选择菜品；服务器校验真实ID、状态、价格并计算totalPrice；用户手动加购 |
| rag.answer(query) | 单个菜单知识问题；Top-3审核知识及关联实时dishes | 模型选择evidence IDs与answerable；服务器验证后只渲染证据原文；不操作购物车 |
| agent.run(query) | 单个自然语言目标；只读菜单Tool与购物车Action Preparation Tool | 模型选择工具；服务器返回待确认动作；用户点击确认后前端复核实时菜单并调用Pinia。没有云端Cart/Order写Tool |

价格、售卖状态必须来自实时数据库，不从模型记忆获取。推荐、RAG与Agent分别维护职责；当前Agent没有把RAG注册为Tool，也不会代理推荐接口。

## 5. 离线索引与在线问答

```text
人工维护 docs/rag/knowledge-source.json
 → 本地同步脚本 → rag/resources/knowledge-source.json + manifest
 → 管理索引流程 → Embedding → knowledge_chunks

用户问答 → Query Embedding → 读取verified索引 → Exact Top-3
 → 实时dishes → LLM选择证据 → Server Validation
 → Trusted Evidence Lookup → 原文answer → UI
```

源知识是唯一人工维护源；resources是部署副本，数据库向量是派生索引。以knowledgeId为身份，版本/内容hash/模型/维度变化才重建；批量按item.index映射，部分失败明确报告，孤儿数据只报告不删除。详见 [索引说明](rag/INDEXING.md)。

`rag`管理方法通过独立admin云函数手动调用，涵盖索引、Retrieval Evaluation、Robustness、Generation诊断和Answer评测。平台来源限制用于开发管理入口，不是uni-id管理员身份认证。微信问答页只调用正式answer，不调用评测或索引方法。

## 6. Agent Orchestration

```text
Single Query（管理入口或微信Agent页面）
 → Agent UI / agent.run(query)
 → Ordering Agent
 → Qwen Native Function Calling
 → Tool Registry（唯一Schema来源）
 → Executor（allowlist与参数校验）
 → Read-only Menu Tools / prepare_add_to_cart
 → categories / dishes
 → Server Validated Pending Action（如适用）
 → role=tool结果回传Qwen
 → Explicit User Confirmation
 → Live Menu Revalidation
 → Pinia Cart Mutation
 → STOP
```

正式 `agent.run(query)` 与管理验收入口复用同一个有限Runner。模型返回的 `assistant.tool_calls` 被保留，服务器按匹配的 `tool_call_id` 追加 `role=tool` 结果，再进入下一轮决策。单次任务最多5轮模型决策、8次Tool调用；正式接口不返回Trace，`traceOnly` 只存在于HBuilderX管理入口的返回压缩层。

三个Read Tool是 `search_menu`、`list_available_drinks` 和 `get_dish_detail`。V5.3增加 `prepare_add_to_cart` Action Preparation Tool：它重新查询dishes、按服务端价格计算金额，只生成 `requiresConfirmation:true` 的Pending Action。V5.4微信页面通过明确按钮确认，再调用现有菜单服务复核状态与价格，最后显式调用Pinia `addDish`；没有动态动作派发、云端购物车或订单写Tool。详见 [Agent Loop](agent/AGENT_LOOP.md)、[Action Proposal](agent/ACTIONS.md) 与 [User Confirmation](agent/CONFIRMATION.md)。

V5.4已在微信开发者工具完成真实验收：柠檬茶数量2的提案在确认前不改变购物车，确认并通过实时复核后准确增加2杯；取消不产生副作用；售罄酸梅汤不显示确认卡。这里的重新查询缓解Pending Action生成与用户点击之间的TOCTOU数据变化，但客户端Pinia不是事务系统，订单创建仍必须由orders云对象重新校验状态和价格。

RAG继续作为独立的单轮菜单知识问答能力，当前没有注册为Agent Tool。

## 7. 输出和运行边界

- Generation只允许answerable、dishIds、usedKnowledgeIds；拒绝自由answer/claims等额外字段。
- 服务器验证Top-3引用、实时在售菜品和双向关联，取回证据原文；true按原顺序换行拼接，false使用固定知识不足文案。
- 正式Answer响应不包含similarity、embedding、Prompt、原始模型响应或密钥。前端只显示回答与依据标题/正文，相关菜品重新读取menu service。
- 密钥只存在云对象远程环境变量；前端和admin不保存API Key。保留本地配置的Git忽略规则。
- 当前没有支付、正式登录、多轮会话、流式输出或云端Cart/Order Agent Write Tool；唯一购物车副作用来自用户按钮确认后的前端Pinia调用，且没有生产级容量与安全治理声明。

## 8. 代码与文档入口

- [前端页面](../src/pages) / [services](../src/services) / [Pinia stores](../src/stores)
- [云对象与管理入口](../uniCloud-aliyun/cloudfunctions) / [数据库定义](../uniCloud-aliyun/database)
- [V4总结](rag/V4_SUMMARY.md) / [Answer API](rag/ANSWER_API.md) / [端到端评测](rag/ANSWER_EVALUATION.md)
- [V5.1 Tool Foundation](agent/TOOLS.md) / [V5.2 Agent Loop](agent/AGENT_LOOP.md)
- [V5.3 Action Proposal](agent/ACTIONS.md)
- [V5.4 User Confirmation](agent/CONFIRMATION.md)
- [部署步骤](UNICLOUD_SETUP.md) / [README运行说明](../README.md)
