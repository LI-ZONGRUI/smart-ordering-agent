# 项目整体架构

这是Vue3 + uni-app + Pinia + uniCloud的微信点餐项目，包含传统点餐、独立LLM推荐、单轮RAG知识问答和Ordering Agent。当前Agent后端只生成购物车动作提案；用户在前端明确确认并通过实时菜单复核后，才修改Pinia购物车。结算与最终订单确认由Pinia购物车直接调用orders服务，不经过模型；当前不包含支付，也不是完整自主点餐系统。

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
          ├─ orders → 共享dishes校验/计价
          │            ├─ previewOrder → 只读预览 → STOP
          │            ├─ createOrder → 再次校验 → orders写入/读取
          │            └─ createConfirmedOrder → 确认值比较 + 可选requestId幂等 → orders
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
| orders | 订单号、菜品快照、数量、金额、备注、状态、clientId、时间；confirmed路径可选保存requestId和内部fingerprint |
| knowledge_chunks | 审核知识及来源、contentHash、版本、模型/维度、向量和时间；knowledgeId唯一 |

这些collection不向小程序开放直接读写。调用云对象不等于已实现完善授权：clientId仅为临时匿名隔离，尚无正式登录与用户认证。

## 3. 传统点餐数据流

1. menu service读取分类、菜品，详情页使用同一正式数据源。
2. Pinia cart维护数量、删除、清空及预览总价，拦截售罄菜品。
3. 确认订单只提交dishId、quantity、remark和clientId；不把客户端价格作为依据。
4. `previewOrder(items)`与创建订单复用同一个服务端校验/计价核心，只读dishes并返回待确认明细；它不写orders，也不生成订单号。
5. `createOrder(payload)`仍会重新查询dishes，校验存在与在售状态，按分计算小计和总额，保存菜名、单价、数量、小计快照。
6. 云端创建成功才清空购物车；失败保留。订单按clientId查询，重新打开仍可查看。

历史订单不随菜品改价或改名变化；预览价不替代下单时的服务器真实价格。V5.5A Server-validated Order Preview已用真实uniCloud菜单数据完成验收，Agent仍没有Order Tool。

当前订单阶段边界：

```text
Pinia Cart
 → only dishId / quantity
 → orders.previewOrder()
 → Shared Validation / Pricing
 → Fresh dishes DB
 → Server Validated Checkout Proposal
 → Frontend Structure / Cents Validation
 → Order Pending Action
 → Explicit Information Confirmation
 → Final Explicit Order Confirmation
 → orders.createConfirmedOrder()
 → 再次 Server Validation / Pricing
 → Expected Preview Comparison
 → Persisted Order
 → Cart Clear
```

Preview与Create共享items校验、重复dishId拒绝、实时菜品查询、在售校验、1～99数量规则和整数分计价；订单最多包含1～30种菜品。Preview是server-validated checkout proposal，不是持久订单、交易、预留、支付意图、授权Token或不可变价格保证。真实验收中，柠檬茶两杯返回总价24元，售罄酸梅汤被 `ORDER_DISH_UNAVAILABLE` 拒绝；检查orders集合未观察到本次Preview创建的新记录。V5.5B前端保存dishId/quantity快照，确认信息时检测购物车变化；确认只改变页面状态。**Checkout proposal flow has been integrated and validated in the WeChat mini-program.**

V5.5C增加独立最终按钮和 `createConfirmedOrder()`。服务器在同一次请求中重新计价，以dishId Map逐项比较quantity、unitPrice、lineTotal及汇总金额，一致后才调用共享持久化helper。成功后前端才清空Cart；失败保留Cart。**Confirmed order execution has been validated in the WeChat mini-program and the real uniCloud orders collection.** 真实成功场景持久化了柠檬茶两杯、总价24元、状态 `pending` 的订单，页面与数据库订单号均为 `OD1790357975859B4A2B5`；价格变化与最终售罄场景均拒绝写入、保留Cart并让旧Proposal失效。V5.5C真实验收时只有客户端防双击；当前仍没有库存事务或serializable transaction。

V5.6A为 `createConfirmedOrder()` 增加可选requestId与规范化SHA-256 fingerprint，并在orders配置 `request_id_unique` 稀疏唯一索引。同键同意图返回首次订单，同键不同意图返回 `ORDER_IDEMPOTENCY_CONFLICT`；并发insert冲突后必须精确查询requestId并核对clientId/fingerprint，不能把任意duplicate错误当成重放。历史订单缺少这两个可选字段，无需迁移。真实控制台已确认 `_id_`、`client_time_desc`、`order_no_unique`、`request_id_unique` 同时存在，requestId索引为升序、unique和sparse；同键同payload重试返回相同orderNo且不增加第二条记录，不同意图真实返回冲突错误。

V5.6B把该能力接入正式微信Checkout：Preview和信息确认阶段不生成key；第一次最终确认时生成一次 `ord-...` requestId，并冻结requestId、clientId、items、expectedPreview与remark。成功或服务端Replay成功后，前端显示orderNo、清Cart并清除提交状态；明确业务失败保留Cart但清除旧意图；结果未知时保留Cart、Proposal、key和冻结payload，显式重试同一内容。真实微信创建的验收订单在orders集合中具有非空requestId与requestFingerprint，并保持 `totalPrice=24`、`totalCount=2`、`status=pending`。**Server-side idempotent order creation has been integrated into and validated through the real WeChat checkout flow.** 当前恢复只覆盖页面生命周期，不包含刷新或小程序重启后的持久恢复，也不等于exactly-once分布式事务、支付幂等、分布式锁或全局事务隔离。

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

V5.5B在同一Agent页面增加独立的 `orderPendingAction`。它从Pinia购物车发起确定性的orders Preview，不调用Agent或Qwen；服务器响应经字段、数量和整数分金额校验后才显示。信息确认前再次比较购物车快照，变化即失效。`cartPendingAction` 与 `orderPendingAction` 互不混用，详见 [Checkout Proposal](agent/ORDER_PROPOSAL.md)。

V5.5B真实微信验收确认：柠檬茶两杯显示单价12元、合计24元；“确认订单信息”后购物车不变且orders集合无新增记录；测试菜品临时设为 `sold_out` 时显示安全业务错误且不生成确认卡。跨页保留旧Preview再修改Cart的场景受当前页面生命周期和TabBar导航影响，本次没有稳定复现；数量改变、项目新增和删除导致快照失效由自动化测试覆盖。该快照机制是客户端提案一致性保护，不是数据库并发控制。

V5.5C订单创建仍不注册为Agent Tool。Qwen不接收Cart状态或expectedPreview，也不能触发订单写入；只有微信页面的显式最终确认调用orders云对象。详见 [Order Execution](agent/ORDER_EXECUTION.md)。

当前已真实验收的端到端主链为：自然语言请求 → Qwen Ordering Agent → 原生Function Calling → 多步Tool编排 → 服务端校验的购物车动作提案 → 用户显式确认 → Pinia购物车真实变更 → 服务端订单预览 → 订单信息确认 → 最终下单确认 → 服务端再次校验 → 持久化订单。它仍不包含自动支付、Agent自主支付、无人确认自动下单或完整支付闭环；最终交易执行属于确定性的服务器边界。

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
- [V5.5A Order Preview](agent/ORDER_PREVIEW.md)
- [V5.5B Checkout Proposal](agent/ORDER_PROPOSAL.md)
- [V5.5C Order Execution](agent/ORDER_EXECUTION.md)
- [V5.6A Order Idempotency](agent/ORDER_IDEMPOTENCY.md)
- [部署步骤](UNICLOUD_SETUP.md) / [README运行说明](../README.md)
