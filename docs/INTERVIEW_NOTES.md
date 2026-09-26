# 面试准备：微信智能点餐 Agent

## 30 秒项目介绍

我用 Vue 3、uni-app、Pinia 和 uniCloud 做了一个微信智能点餐项目。除了菜单、购物车和云端订单闭环，还实现了两项独立的智能能力：Evidence-first RAG 菜单问答，以及基于 Qwen 原生 Function Calling 的多步 Ordering Agent。模型负责开放式理解、证据或工具选择；价格、状态、副作用、订单确认和幂等由服务器与用户确认控制。项目冻结时 747 项自动化测试通过，并完成真实微信端和 uniCloud 验收。

## 90 秒项目介绍

项目先完成传统点餐闭环：菜单来自 uniCloud，购物车由 Pinia 管理，订单 Preview 和最终创建都由服务端读取实时价格与状态。

RAG 使用 21 条人工审核知识、512 维 Embedding 和 Exact Cosine Top-3。真实测试中，模型曾在证据之外加入“解腻”，也曾把“柠檬香气”扩写成“清爽的柠檬香气”。所以我把信任边界改为 Evidence-first：模型只选择 `answerable`、dishIds 和 knowledgeIds，服务器验证后直接用可信证据原文生成答案。12 条固定云端评测中，Answerability 为 11/12，Server Grounding 为 12/12。

Ordering Agent 使用原生 Function Calling、Tool Registry、Executor allowlist 和参数 Schema。真实案例中，模型先搜索可乐得到空结果，再自主调用在售饮料工具返回柠檬茶，这个第二步不是代码写死。写操作则采用 Proposal → 服务端校验 → 用户确认：LLM 不能直接修改购物车。订单还实现 Preview 后再次校价、旧确认拒绝，以及 requestId、请求指纹和数据库唯一索引共同构成的幂等重试。

## 3 分钟项目介绍

### 1. 业务基础

客户端是 Vue 3 + uni-app 微信小程序，Pinia 保存购物车。categories、dishes 和 orders 在 uniCloud；页面通过 service 调用云对象，数据库不直接暴露给客户端。订单只提交 dishId 和 quantity，服务端读取真实状态和价格并保存快照。

### 2. RAG

人工源是 21 条 verified 菜单知识，部署时生成 512 维 Embedding，按 knowledgeId、contentHash、版本、模型和维度幂等索引。查询采用 Exact Cosine Top-3，因为只有 21 条数据，简单、可解释且易测试。

系统没有使用固定 similarity threshold。真实 robustness 数据中 supported 与 unsupported 分数发生过重叠，相似度不是答案概率。生成阶段经历了三次收紧：自由答案会扩写事实；claim citation 只能证明 ID 合法；server-composed claims 仍会接受被扩写的 claim text。最终改成模型只选 evidence ID，服务器直接渲染原文。

### 3. Agent

Agent 与 RAG 独立。Agent 使用 Qwen3.8-Flash 原生 Function Calling，Registry 定义四个工具，Executor 做 allowlist、Schema 校验与静态实现映射。模型每轮接收 Tool Result，再决定继续调用或结束，因此“可乐搜索为空后查在售饮料”属于真实多步循环。

对副作用，我没有给模型任意 Store 或订单写权限。`prepare_add_to_cart` 只返回 Pending Action；用户确认时客户端重新读取菜单，确认菜品仍存在、在售且价格未变化，才调用 Pinia mutation。

### 4. 订单与幂等

Checkout 完全走确定性服务端逻辑，不经过 Qwen。Preview 先校价，用户确认后 Create 再校价，并逐行比较 expected preview。真实测试中，柠檬茶从 12 元变成 13 元后，系统返回 `ORDER_CONFIRMATION_STALE`，没有静默创建 26 元订单。

前端防重复按钮不能覆盖“服务端已落库但响应丢失”。因此每次确认生成一次 requestId，并冻结 payload。服务端把 clientId、items、expectedPreview 和 remark 规范化后计算 SHA-256 fingerprint。相同 key 与 payload 返回原订单，不同 payload 报冲突；并发下最终由数据库 UNIQUE sparse index 保证唯一性。

### 5. 结果和边界

项目完成真实微信端、uniCloud、RAG、Agent、购物车确认和持久化订单验收。当前仍是 21 条知识、12 条问题的小规模单轮系统，没有支付、库存事务、多轮记忆或生产规模 Vector DB。

## 架构讲解顺序

1. **Client**：微信小程序、Vue 3、Pinia。
2. **Services**：menu、ai、rag、agent、orders 调用边界。
3. **Intelligence**：推荐、RAG、Ordering Agent 三项能力。
4. **Validation**：Tool Registry、Executor、Pending Action、订单计价与确认。
5. **Backend / Data**：uniCloud 云对象与 categories、dishes、knowledge_chunks、orders。

RAG 与 Agent 共享真实菜单数据，但当前没有调用关系；`rag.answer()` 不是 Agent Tool。

## 高频问题与回答要点

### 1. RAG 是什么？

先从外部知识中检索与问题相关的内容，再把检索结果提供给生成模型。本项目把人工知识、派生向量索引、Retrieval、evidence 选择和服务器渲染分开，便于追溯答案来源。

### 2. Embedding 是什么？

把文本编码为数值向量，使语义相近的文本在向量空间中更接近。本项目使用 qwen3.7-text-embedding-flash 的 512 维向量；向量相近只表示检索相关性，不表示事实正确或一定可回答。

### 3. 为什么用 cosine similarity？

它用向量夹角衡量方向相似性，适合作为文本向量排序基线。实现会检查等长、有限数字与非零范数，计算 `dot / (normA * normB)`。

### 4. 为什么 Top-3？

这是冻结的实验设置，在上下文长度和召回之间取一个简单起点。它不是普适最优值；当 relevant 超过 3 条时，Recall@3 存在理论上限。

### 5. 为什么没有 similarity threshold？

真实 robustness 评测出现 supported 与 unsupported Top-1 分数重叠。固定阈值无法在现有数据上完美分离，两者的 similarity 也不是概率，因此没有把某个观察值写进业务规则。

### 6. 为什么没有向量数据库？

当前只有 21 条知识，逐条 Exact Search 计算量小，行为更透明且容易冻结测试。规模扩大后再评估 ANN 或专用 Vector DB，当前引入只会增加运维复杂度。

### 7. 为什么只有 21 chunks？

第一版强调人工审核、来源追踪和知识边界，使用真实菜单 description、taste、ingredients。它足以验证完整工程链路，但不足以代表生产知识覆盖率。

### 8. RAG 会 hallucination 吗？

会。检索到证据不代表模型只会说证据内容，也不代表模型一定选对证据。本项目的真实“解腻”和“清爽的柠檬香气”就是例子。

### 9. Evidence-first Grounding 如何降低 hallucination？

模型只返回合法 evidence ID；服务器验证 ID 属于本次 Top-3，再直接使用 evidence 原文生成答案。这样阻断模型改写事实进入最终答案，但不能保证模型一定选全或选对证据。

### 10. Function Calling 与普通 prompt JSON 有什么区别？

原生 Function Calling 让模型通过协议化的 tool call 返回工具名和结构化参数，Tool Result 也以专门角色回传；普通 prompt JSON 只是要求模型输出一段符合格式的文本。两者都需要服务端做 allowlist、Schema 和业务校验。

### 11. Agent 和普通 LLM API 调用有什么区别？

普通调用通常一次输入到一次输出；Agent Loop 会执行“模型决策 → Tool → Observation → 再决策”，直到得到最终答案或达到步数上限。模型可根据运行结果改变下一步动作。

### 12. 为什么“可乐”案例属于 multi-step Agent？

第一步 `search_menu("可乐")` 得到 count=0，结果回传模型；模型观察后第二步选择 `list_available_drinks()`，返回在售柠檬茶。服务器没有写死 no-cola fallback。

### 13. Tool Result 为什么不能直接信模型？

模型只提出工具名和参数，真实结果来自服务器实现与数据库。即便模型描述了某个价格或状态，也必须使用 Tool Result 或数据库事实，不能把模型文本当业务数据。

### 14. 为什么 Tool 使用 allowlist？

防止模型调用未授权函数、动态路径或任意代码。Registry 和静态 implementation map 限定可达能力，未知工具直接拒绝。

### 15. 为什么需要 parameter schema？

它限制字段、类型、必填项和范围，并使用 `additionalProperties=false` 拒绝额外参数。Schema 解决结构输入问题，后端仍需校验菜品状态和价格等业务事实。

### 16. 为什么 Cart Action 先 Proposal 再 Confirmation？

加购是用户可见副作用。Tool 只生成经过服务端校验的 Pending Action，UI 明确展示数量与价格；用户点击确认后再次读取实时菜单，才修改 Pinia，避免模型直接执行和旧事实提交。

### 17. 为什么订单不直接做 Agent Tool？

订单包含金额确认、持久化和失败语义，适合确定性事务流程。Qwen 不参与 Preview、校价、expected comparison、request fingerprint 或数据库写入，减少不可重复决策进入交易边界。

### 18. 什么是 TOCTOU？

Time-of-check to time-of-use：检查事实和真正使用事实之间存在时间窗口。菜品可能在 Preview 后改价或售罄，因此 Create 必须再次读取数据库并比较用户确认的预期。

### 19. 为什么 Preview 后 Create 还要重新计价？

Preview 只是当时的快照。若只信 Preview，确认到创建之间的价格或状态变化会被忽略。Create 重新校验并逐行比较，变化时返回 `ORDER_CONFIRMATION_STALE`，让用户重新确认。

### 20. 什么是 idempotency？

同一逻辑请求重复执行时，不产生额外副作用。本项目对相同 requestId 和相同 fingerprint 返回已创建订单，而不是重复插入。

### 21. requestId 和 orderNo 有什么区别？

requestId 是客户端为一次提交意图生成的幂等键；orderNo 是订单成功落库后的业务编号。requestId 不能替代订单号、身份认证或授权。

### 22. 为什么还需要 fingerprint？

只有 requestId 无法判断重试 payload 是否被换掉。服务端规范化关键字段并计算 SHA-256；同 key 不同 fingerprint 返回 `ORDER_IDEMPOTENCY_CONFLICT`。

### 23. 为什么使用 sparse unique index？

`unique` 在数据库层阻止相同 requestId 并发插入；`sparse` 让旧订单或不走 confirmed 路径、没有 requestId 的记录不互相冲突。

### 24. 为什么 check-then-insert 有 race condition？

两个并发请求可能同时查询“未存在”，随后都尝试插入。应用层预查不能原子保证唯一，数据库 UNIQUE constraint 才是最终并发防线。

### 25. 为什么 Agent 与 RAG 没有硬绑在一起？

菜单知识问答与实时工具编排有不同的输入、评测和信任边界。当前需求可分别完成，强行连接会增加链路、成本和故障面。未来只有出现需要知识检索的 Agent 任务时，才考虑把受限 RAG 能力注册为 Tool。

### 26. 当前系统还有什么问题？

知识只有 21 chunks，评测只有 12 query；RAG 与 Agent 均无多轮记忆；购物车和 Pending Action 不持久化；未决订单提交状态不跨重启恢复；没有正式登录、支付、库存事务、exactly-once 分布式事务或生产规模向量检索。

## 如果再给两周

1. 扩大并版本化独立评测集，加入更多同义问法、困难拒答和回归样本。
2. 分析 supported False Negative，比较 evidence selection 策略，而不直接按当前小集调 Prompt。
3. 设计 Pending Action 与未决订单提交的安全本地恢复，并加入过期和用户切换处理。
4. 增加 uni-id 身份与服务端授权，再评估受限订单查询 Tool。
5. 为支付和库存建立独立状态机、幂等回调和事务/补偿设计，不让 Agent 直接执行。

## Current Scope / Future Work

- Knowledge Base：21 chunks；baseline：12 fixed queries。
- RAG 是 single-turn；Agent 没有 multi-turn conversation memory。
- RAG 不是 Agent Tool。
- Cart 在 Pinia；Pending Action 不持久化。
- 未决 requestId 与 frozen payload 不跨刷新或小程序重启恢复。
- 没有支付、库存事务或 exactly-once distributed transaction。
- 没有 production-scale Vector DB。

这些边界说明当前工程验证覆盖到哪里，也给出了下一步可以被独立评测的方向。
