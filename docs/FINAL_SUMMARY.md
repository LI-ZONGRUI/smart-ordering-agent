# V6 项目冻结总结

## Project Goal

构建一个可在微信小程序中真实运行的点餐系统，并验证如何把 LLM、RAG 与 Function Calling Agent 接入业务，同时把事实、权限、副作用和交易一致性保留在可验证的程序边界内。

项目名称：

> 基于 LLM + RAG + Function Calling 的微信智能点餐 Agent

## Final Architecture

~~~text
WeChat Mini Program / Vue 3 / uni-app / Pinia
 → Application Services
 → menu / ai / rag / agent / orders cloud objects
 → Validation and deterministic business logic
 → categories / dishes / knowledge_chunks / orders
~~~

智能能力分为三条路径：

1. **Recommendation**：Qwen 根据偏好选择真实菜品 ID，服务器校验并读取实时价格。
2. **RAG**：Embedding Retrieval 后由模型选择 evidence ID，服务器渲染可信原文。
3. **Ordering Agent**：Qwen 通过原生 Function Calling 编排受限菜单 Tool，并只生成待确认加购 Proposal。

RAG 与 Agent 是独立能力；rag.answer() 没有注册为 Agent Tool。订单 Preview、确认、计价与持久化也不经过 Qwen。

## Implemented Features

- 首页、菜单分类、菜品详情、购物车、确认订单、订单列表和个人页。
- uniCloud 云端 categories、dishes、orders 持久化。
- Pinia 购物车增减、删除、清空、数量与总价。
- 售罄校验、服务端价格计算和订单快照。
- Qwen3.8-Flash 自然语言菜品推荐与服务端 dishId 白名单。
- 单轮 RAG 菜单问答及可信依据展示。
- 原生 Function Calling 多步 Ordering Agent。
- 加购 Proposal、用户显式确认和真实 Pinia mutation。
- 服务端订单 Preview、最终确认、再次校价和持久化。
- requestId、请求指纹、数据库唯一索引与前端同 key 重试。

## RAG

### Knowledge and Retrieval

- Knowledge Source V1：21 条人工逐条审核、verified=true 的知识。
- 类型：description、taste、ingredients。
- Embedding：qwen3.7-text-embedding-flash，512 维。
- Indexing：knowledgeId 唯一，比较 contentHash、sourceVersion、模型和维度；真实首次 inserted 21，二次 skipped 21。
- Retrieval：Exact Cosine Similarity，Top-3，无固定 threshold、reranker、BM25 或 type boost。

### Evidence-first Grounding

真实测试暴露了两类问题：

- 自由回答加入 evidence 未提供的“解腻”。
- claim 把“具有柠檬香气”扩写为“具有清爽的柠檬香气”。

最终信任边界：

~~~text
LLM selects answerable / dishIds / usedKnowledgeIds
 → server validates IDs
 → server reads trusted evidence
 → server renders final factual answer
~~~

这样阻止模型自由改写事实后直接展示，但不能保证模型一定选择最相关或完整的 evidence。

## Agent

Agent 使用 Qwen3.8-Flash 原生 Function Calling，Registry 是 Tool 合同来源，Executor 实施 allowlist、参数 Schema、additionalProperties=false 和静态实现映射。

当前工具：

- search_menu
- list_available_drinks
- get_dish_detail
- prepare_add_to_cart

真实多步验收：

~~~text
“有可乐吗？没有的话推荐点别的喝的。”
 → search_menu("可乐")
 → count = 0
 → model observes the result
 → list_available_drinks()
 → dish-4 / 柠檬茶 / on_sale / ¥12
~~~

第二步由模型基于 Tool Observation 决定，不是硬编码 fallback。

## Action Safety

真实加购路径：

~~~text
“把柠檬茶加两杯到购物车”
 → search_menu
 → prepare_add_to_cart
 → server revalidation
 → Pending Action: quantity=2, unitPrice=12, totalPrice=24
 → requiresConfirmation=true
 → user confirmation
 → fresh menu revalidation
 → Pinia mutation
~~~

LLM 没有任意 Store mutation 权限。不存在或售罄菜品会返回白名单化的安全业务错误，未知内部异常继续泛化。

## Order Safety

~~~text
Pinia Cart
 → previewOrder
 → fresh server validation and pricing
 → information confirmation
 → final explicit confirmation
 → createConfirmedOrder
 → fresh validation and pricing again
 → expected preview comparison
 → persist order
 → real orderNo
 → clear cart after server success
~~~

真实 stale-confirmation 验收：Preview 为柠檬茶 ×2、单价 ¥12、总价 ¥24；确认后数据库价格改为 ¥13，最终创建返回 ORDER_CONFIRMATION_STALE，没有静默按 ¥26 创建订单。

## Idempotency

UI 的 submitting 状态只能防普通双击，无法处理“服务器已落库但响应丢失”。最终设计：

~~~text
requestId
 + canonical(clientId, items, expectedPreview, remark)
 → SHA-256 requestFingerprint
 → request_id_unique (unique + sparse)
~~~

- 同 requestId + 同 payload：重放首次订单。
- 同 requestId + 不同 payload：ORDER_IDEMPOTENCY_CONFLICT。
- 前端在结果未知时保留 requestId 与 frozen payload，以完全相同的请求重试。
- query-then-insert 不是并发保证；数据库 UNIQUE constraint 是最终防线。

## Evaluation

真实云端固定评测范围：

- Knowledge chunks：21。
- Queries：12（6 supported、3 unsupported-domain、3 external-OOD）。
- Answerability Accuracy：91.67%（11/12）。
- Supported Answer Rate：83.33%（5/6）。
- Unsupported-domain Rejection：100%（3/3）。
- External-OOD Rejection：100%（3/3）。
- Retrieval Hit：100%（6/6 supported）。
- Average Retrieval Recall@3：约 80.83%。
- Evidence Hit：83.33%（5/6 supported）。
- Server Grounding Pass：100%（12/12）。

唯一 Answerability 错误是 supported False Negative：相关酸梅汤 evidence 已进入 Top-3，但模型拒答。该结果来自小型项目评测，不是生产 Benchmark。

## Testing

项目冻结检查包括：

- Node.js 自动化测试：747 项。
- 微信小程序生产构建。
- Knowledge Source 与部署副本 SHA-256 一致性检查。
- RAG frozen fixture 回归。
- 文档 diff 与敏感信息扫描。
- 微信开发者工具及真实 uniCloud 管理入口人工验收。

最终自动化数量以冻结时实际重跑结果为准。

## Real Acceptance Cases

- 云端菜单读取 5 个分类、8 道菜。
- 云端订单创建、查询及重启后持久存在。
- Qwen3.8-Flash API 与 512 维 Embedding 链路。
- Knowledge Index 首次插入 21、二次全部 skip。
- RAG “有什么比较清爽的？”展示 server-grounded evidence。
- RAG “有可乐吗”安全返回知识不足，不把未检索到解释为现实中不存在。
- Agent 可乐空结果后的第二次饮料 Tool Call。
- 柠檬茶 ×2 的 Pending Action、用户确认与真实 Cart mutation。
- ¥24 Preview、确认后价格变化的 stale rejection。
- 持久化订单返回真实 orderNo。
- 相同 requestId/payload 重放原订单，不同 payload 冲突。

## Known Limitations

- Knowledge Base 只有 21 chunks；baseline 只有 12 fixed queries。
- RAG 为单轮；Agent 无多轮 conversation memory。
- RAG 不是 Agent Tool。
- Cart 在 Pinia，Pending Action 不持久化。
- 未决 requestId 和 frozen payload 不跨页面刷新或小程序重启恢复。
- clientId 是开发期隔离，不是正式身份认证。
- 没有支付、库存事务或 exactly-once distributed transaction。
- 没有 production-scale Vector DB、ANN 或分布式检索。

## Repository Milestones

| Commit | Milestone |
| --- | --- |
| e525675 | Local ordering flow |
| d534b60 | uniCloud menu and order persistence |
| 210ebf0 | Qwen dish recommendation with server validation |
| 3975709 | Verified Knowledge Source V1 |
| c45bee6 | Embedding and idempotent indexing |
| f555763 | Retrieval and evaluation |
| ba07137 | Evidence-first grounded generation |
| f333b93 | Evaluated single-turn RAG answer pipeline |
| a19a6cd | WeChat RAG menu Q&A interface |
| 038c4f2 | V4 RAG architecture and project notes |
| d3612bf | Read-only Agent Tool foundation |
| f4c0cd5 | Multi-step Ordering Agent |
| 24a5848 | Validated cart action proposals |
| 7f7626b | Confirmed cart execution |
| 73dc610 | Server-validated order preview |
| e694ddd | Checkout proposal flow |
| 59ad9ad | Confirmed persisted order execution |
| e9bf5c5 | Server-side order idempotency |
| 5e6adcb | Frontend idempotent retry integration |

## Final Scope

项目最终证明的不是“让模型自动完成所有事情”，而是如何在真实小程序里划分职责：

- LLM 处理开放式语义与有限决策。
- Retrieval 提供可追溯上下文。
- Registry、Schema 和服务器校验限制工具权限。
- 用户确认控制有感副作用。
- 确定性服务端逻辑控制价格、订单、错误和幂等。

这是一套经过真实小规模验收的工程方案，不是生产级 AI、支付或库存系统声明。
