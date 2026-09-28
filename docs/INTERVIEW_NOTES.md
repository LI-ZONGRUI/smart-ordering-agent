# 面试准备：微信智能点餐 Agent

## 30 秒项目介绍

我用 Vue 3、uni-app、Pinia 和 uniCloud 做了一个微信智能点餐项目。除了菜单、购物车和云端订单闭环，还实现了 Evidence-first RAG、原生 Function Calling Ordering Agent，以及独立的 Python + FastAPI + LangChain + LangGraph 智能路由。模型负责开放式理解、证据或工具选择和动作提案；价格、状态、副作用、订单确认和幂等由服务器与用户确认控制。当前 JS 851 项、Python 197 项自动化测试通过，并完成真实微信多轮会话、uniCloud 与 Qwen/LangChain/LangGraph 链路验收。

## 90 秒项目介绍

项目先完成传统点餐闭环：菜单来自 uniCloud，购物车由 Pinia 管理，订单 Preview 和最终创建都由服务端读取实时价格与状态。

RAG 使用 21 条人工审核知识、512 维 Embedding 和 Exact Cosine Top-3。真实测试中，模型曾在证据之外加入“解腻”，也曾把“柠檬香气”扩写成“清爽的柠檬香气”。所以我把信任边界改为 Evidence-first：模型只选择 `answerable`、dishIds 和 knowledgeIds，服务器验证后直接用可信证据原文生成答案。12 条固定云端评测中，Answerability 为 11/12，Server Grounding 为 12/12。

Ordering Agent 使用原生 Function Calling、Tool Registry、Executor allowlist 和参数 Schema。真实案例中，模型先搜索可乐得到空结果，再自主调用在售饮料工具返回柠檬茶，这个第二步不是代码写死。写操作则采用 Proposal → 服务端校验 → 用户确认：LLM 不能直接修改购物车。订单还实现 Preview 后再次校价、旧确认拒绝，以及 requestId、请求指纹和数据库唯一索引共同构成的幂等重试。

独立的 Python Framework Agent 使用 LangChain `create_agent` 和三个只读 Structured Tools，
通过 HMAC Gateway 读取相同的真实菜单。最终真实 trace 为
`search_menu → result(count=0) → list_available_drinks → result`，证明该案例中 Qwen 根据
Tool Result 做了下一次模型决策；它没有购物车或订单 Tool。V7.3C 已通过独立 Framework Agent
service 将五路 LangGraph 接入微信聊天 UI。

V7.2A 在这条链路外增加项目自有的 LangGraph `StateGraph`。LangGraph 负责顶层 state、路由和
节点流转；进入 `menu_agent` 后，现有 LangChain Agent 继续负责 Qwen Tool Calling、
ToolMessage observation 与 sequential replanning。这样没有为了展示 LangGraph 而重写已验收
的 Tool Agent。

V7.2B 在同一个 StateGraph 中加入 `knowledge_query → rag_node`。它没有把 RAG 复制到
Python，而是通过 `RagGateway → HMAC Framework Gateway → rag_answer` 调用现有 uniCloud
`rag.answer(query)`。真实“柠檬茶是什么味道？”案例返回了柠檬香气和红茶、柠檬配料事实；
正式 API 仍不暴露 route、chunks、scores 或 evidence IDs。

V7.2C 增加 `action_query → native_action_node`。该节点经认证 Gateway 复用现有 Native Agent，
只接收经过服务端校验的加购 `pendingAction`。真实“把柠檬茶加两杯到购物车”案例返回数量 2、
单价 12 元、合计 24 元并要求确认；“直接帮我付款”仍进入 `unsupported_action`，没有
`pendingAction`。模型负责理解意图、选择 Tool 和生成 proposal，实时状态、价格、用户确认、
幂等与交易持久化仍由确定性代码负责。

V7.3A 再通过可选 `threadId` 和进程内 `InMemorySaver` 增加短期多轮上下文。Qwen
Contextualizer 只把“多少钱？”、“它是什么味道？”等 follow-up 转成 standalone query；历史只
解决指代，价格仍查实时菜单 Tool，口味事实仍走现有 RAG。真实连续验收还验证了动作追问只生成
proposal、文本“确认”不执行、线程隔离和无 threadId 兼容。

V7.3B 使用 `AsyncSqliteSaver` 将显式创建的 durable conversation 保存到 SQLite。Process 1 完全
停止后，Process 2 使用同一文件、threadId 与 capability token 成功恢复柠檬茶上下文；价格仍
重新查询实时 Tool。threadId 不是秘密，因此创建时另发一次性返回的高熵 token，服务端只保存
SHA-256 digest 并用 constant-time compare 校验。History API 只投影安全 user/assistant 文本。

V7.3C 将 durable conversation 接入微信小程序。真实连续操作覆盖菜单、价格追问、RAG 口味追问、
加购提案和动作卡确认；确认时前端重新读取 uniCloud 菜单并调用既有 Pinia mutation，购物车得到
柠檬茶 ×2、合计 24 元。输入文字“确认”不会再次加购、创建订单或支付。页面重进以及 FastAPI
完全重启后均恢复了文字历史，新对话则生成新的 capability。

## 3 分钟项目介绍

### 1. 业务基础

客户端是 Vue 3 + uni-app 微信小程序，Pinia 保存购物车。categories、dishes 和 orders 在 uniCloud；页面通过 service 调用云对象，数据库不直接暴露给客户端。订单只提交 dishId 和 quantity，服务端读取真实状态和价格并保存快照。

### 2. RAG

人工源是 21 条 verified 菜单知识，部署时生成 512 维 Embedding，按 knowledgeId、contentHash、版本、模型和维度幂等索引。查询采用 Exact Cosine Top-3，因为只有 21 条数据，简单、可解释且易测试。

系统没有使用固定 similarity threshold。真实 robustness 数据中 supported 与 unsupported 分数发生过重叠，相似度不是答案概率。生成阶段经历了三次收紧：自由答案会扩写事实；claim citation 只能证明 ID 合法；server-composed claims 仍会接受被扩写的 claim text。最终改成模型只选 evidence ID，服务器直接渲染原文。

### 3. Agent

Agent 与 RAG 独立。Agent 使用 Qwen3.8-Flash 原生 Function Calling，Registry 定义四个工具，Executor 做 allowlist、Schema 校验与静态实现映射。模型每轮接收 Tool Result，再决定继续调用或结束，因此“可乐搜索为空后查在售饮料”属于真实多步循环。

对副作用，我没有给模型任意 Store 或订单写权限。`prepare_add_to_cart` 只返回 Pending Action；用户确认时客户端重新读取菜单，确认菜品仍存在、在售且价格未变化，才调用 Pinia mutation。

V7 还增加了一条独立 Python LangChain 只读链路。较早一次真实验收中，Qwen 在同一个
`AIMessage` 预先发出 `search_menu` 和 `list_available_drinks`，trace 是
`call → call → result → result`，所以我没有把它描述成 sequential replanning。随后只增加
通用 Prompt 约束，要求 `search → wait Tool Result → consider fallback`，没有写
`if count == 0` fallback。最终重测得到 `call → result → call → result`，才把该案例记录为
Tool-result-driven sequential replanning。

V7.2A 进一步补上项目级显式 Workflow：`route_request` 通过 Conditional Edges 把请求分到
实时菜单查询、知识问答、确定性闲聊或只读拒绝，再统一进入 `normalize_result`。菜单分支
适配现有 FrameworkAgent；知识分支复用现有 uniCloud RAG。LangGraph 决定“走哪条业务
路径”，LangChain 决定“菜单查询中如何调用 Tool”。

### 4. 订单与幂等

Checkout 完全走确定性服务端逻辑，不经过 Qwen。Preview 先校价，用户确认后 Create 再校价，并逐行比较 expected preview。真实测试中，柠檬茶从 12 元变成 13 元后，系统返回 `ORDER_CONFIRMATION_STALE`，没有静默创建 26 元订单。

前端防重复按钮不能覆盖“服务端已落库但响应丢失”。因此每次确认生成一次 requestId，并冻结 payload。服务端把 clientId、items、expectedPreview 和 remark 规范化后计算 SHA-256 fingerprint。相同 key 与 payload 返回原订单，不同 payload 报冲突；并发下最终由数据库 UNIQUE sparse index 保证唯一性。

### 5. 结果和边界

项目完成真实微信多轮聊天、uniCloud、RAG、Agent、购物车确认、持久化订单和同一持久文件系统的重启恢复验收。当前仍是 21 条知识、12 条问题的小规模系统，没有支付、库存事务、分布式会话存储、长期用户画像或生产规模 Vector DB。

## 架构讲解顺序

1. **Client**：微信小程序、Vue 3、Pinia。
2. **Services**：menu、ai、rag、agent、orders 调用边界。
3. **Intelligence**：推荐、RAG、Ordering Agent 三项能力。
4. **Validation**：Tool Registry、Executor、Pending Action、订单计价与确认。
5. **Backend / Data**：uniCloud 云对象与 categories、dishes、knowledge_chunks、orders。

独立 Python 服务中再区分两层：LangGraph 负责顶层 Workflow Orchestration，LangChain
`create_agent` 负责菜单分支内部的 Tool Calling Loop。

RAG 与 Agent 共享真实菜单数据。LangGraph 可以在顶层选择 RAG 分支，但 `rag.answer()` 不是
LangChain Agent Tool，菜单 Agent 不会在 Tool Loop 中自行调用它。

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

这里以最终真实 observable trace 的 `call → result → call → result` 为依据。曾有一次运行是
`call → call → result → result`，两个 Tool Call 来自同一个模型决策，不能证明模型观察了第一
个结果。保留真实 trace 顺序并区分两者，比只看最终答案更重要。

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

菜单知识问答与实时工具编排有不同的输入、评测和信任边界。V7.2B 只在 LangGraph 顶层把
问题路由到其中一条独立分支，没有把 RAG 注册为 Agent Tool。这样可以组合能力，又不会让
菜单 Agent 自由调用知识链路或混合两套错误边界。

### 26. 当前系统还有什么问题？

知识只有 21 chunks，评测只有 12 query；SQLite 会话只证明同一持久文件系统上的重启恢复，不支持跨机器、多实例或账户级跨设备同步；购物车和 Pending Action 不持久化；未决订单提交状态不跨重启恢复；没有正式登录、支付、库存事务、exactly-once 分布式事务或生产规模向量检索。

### 27. 为什么同时使用 LangGraph 和 LangChain？

V7.1C 已有稳定的 LangChain Tool Agent，但缺少项目级显式 Workflow。LangGraph 负责请求
路由、Graph State 和节点流转；菜单节点继续复用 LangChain `create_agent`，知识节点复用
现有 uniCloud RAG。这样把“走哪条业务路径”“菜单查询中如何调用 Tool”和“知识问答如何
grounding”分开。V7.2C 的 Native Agent 路由也只生成 proposal；V7.3A 增加进程内多轮语义
上下文，V7.3B 进一步以 `AsyncSqliteSaver` 和 capability token 提供持久恢复，但仍没有文本确认执行。

### 28. 为什么不让 LangGraph 直接执行购物车或订单？

LLM 适合 intent understanding、Tool selection 和 proposal generation，但交易正确性需要实时
价格与状态校验、明确用户确认、幂等键、唯一约束和持久化结果。项目因此采用 Human-in-the-loop：
`User intent → Native Agent → pendingAction → frontend UI → explicit confirmation → deterministic execution`。
LangGraph 与 Native Agent 都不会因为产生 `pendingAction` 而自动修改购物车或创建订单。

早期真实验收中，Native Agent 自由文本曾提示“回复确认，我再执行”，但系统没有文本确认后的
执行能力。即使 V7.3A 增加 conversation history，该权限边界也没有扩大。最终由 `native_action_node` 根据已验证的
`pendingAction` 确定性生成提示，名称、数量、单价和总价都来自该合同，从而避免错误能力暗示。

### 29. 为什么不把 RAG 复制到 Python？

uniCloud RAG 已有稳定的 Embedding、Exact Retrieval、Top-3、Evidence-first grounding 和
服务器确定性渲染。Python 这一层只需要 orchestration，因此通过认证 Gateway 复用正式能力，
保持 single source of truth，也避免两套知识副本、向量和 Retrieval 实现随时间漂移。

### 30. 为什么 History 不能直接作为事实源？

History 用来判断“它”“多少钱”“那来两杯”指向哪个菜品，但历史价格、库存和供应状态可能已
变化。Contextualizer 只生成 standalone query；菜单分支仍调用实时 Tool，知识分支仍调用现有
RAG。这样把 semantic reference resolution 和 factual source of truth 分开。

### 31. V7.3A 的 Contextualizer 兼容问题是什么？

旧实现使用 forced named `tool_choice`，并只接受一种 normalized Tool Call。第一次真实多轮验收中
三个 follow-up 因输出形态假设过窄全部返回 `FRAMEWORK_CONTEXT_FAILED`。修复后改用普通
Tool Calling，并对 normalized Tool Call、原始 OpenAI Tool Call 和严格 JSON content 做相同的
窄 schema 校验。真实单独验收走 `normalized_tool_call`，但没有据此假设供应商永远只返回该形态。

### 32. 为什么从 InMemorySaver 升级到 SQLite？

V7.3A 的进程内状态在 Python 重启后丢失。`AsyncSqliteSaver` 与现有 `ainvoke` 调用方式匹配，
能够在同一持久文件系统上恢复 checkpoint。它适合当前单机项目验收，但不是分布式数据库或
多实例一致性方案。

### 33. 为什么知道 threadId 仍不能直接读取历史？

threadId 是 correlation identifier，不是秘密或身份凭据。只凭可猜测或泄露的 ID 读取历史会
造成 conversation disclosure。因此服务端创建 durable conversation 时同时生成高熵 capability
token，只保存 SHA-256 digest，并要求 History/Resume 同时提交 threadId 与 token。

### 34. 为什么没有 conversation list？

当前没有成熟用户身份与 ownership 模型，服务端无法安全判断“哪些会话属于当前用户”。所以
只提供创建会话、凭 capability 恢复指定会话和读取指定历史，不提供全局 list。

### 35. 为什么 CLI 运行时聊天正常但动作确认失败？

CLI 的 `pnpm run dev:mp-weixin` 产物能访问本地 FastAPI，但没有 HBuilderX 已关联的 uniCloud 运行
环境。动作确认必须重新读取实时菜单，所以首次返回“暂时无法确认菜品状态”，并且没有信任旧
`pendingAction` 或修改购物车。这说明实时复核按预期 fail closed。改用 HBuilderX 连接阿里云
远程服务空间运行后，同一确认流程成功复核并加入柠檬茶 ×2。

### 36. 为什么 UI 确认和聊天文字“确认”权限不同？

动作卡按钮调用经过校验的本地确定性流程：重读菜单、检查状态和价格、再执行 Pinia mutation。
聊天文字只是新的自然语言 Query，只能进入 LangGraph 安全路由，不能成为交易授权。真实验收中
UI 确认后购物车是 ×2；随后发送文字“确认”，购物车仍是 ×2。2026-09-28 验收时订单页最新
可见记录仍为 2026-09-26 16:20 的历史订单，证明没有通过聊天或动作卡创建新订单。

## 如果再给两周

1. 扩大并版本化独立评测集，加入更多同义问法、困难拒答和回归样本。
2. 分析 supported False Negative，比较 evidence selection 策略，而不直接按当前小集调 Prompt。
3. 设计 Pending Action 与未决订单提交的安全本地恢复，并加入过期和用户切换处理。
4. 增加 uni-id 身份与服务端授权，再评估受限订单查询 Tool。
5. 为支付和库存建立独立状态机、幂等回调和事务/补偿设计，不让 Agent 直接执行。

## Current Scope / Future Work

- Knowledge Base：21 chunks；baseline：12 fixed queries。
- RAG 接口是 single-turn；Python LangGraph 的 durable conversation 已支持同一持久文件系统重启恢复。
- RAG 不是 LangChain Agent Tool；LangGraph 只在独立知识分支调用它。
- Cart 在 Pinia；Pending Action 不持久化。
- 未决 requestId 与 frozen payload 不跨刷新或小程序重启恢复。
- 没有支付、库存事务或 exactly-once distributed transaction。
- 没有 production-scale Vector DB。
- LangGraph 已有 `AsyncSqliteSaver`、capability token、受限 history 和上下文化；没有跨机器或
  多实例一致性、账户级跨设备状态、conversation list、token expiry/rotation/revocation、多轮文本
  确认执行或长期用户画像。V7.3C 微信聊天 UI 已完成真实验收，旧动作卡不随 History 恢复，
  Markdown-like 内容仍按安全纯文本展示。
- Framework Agent 正式部署仍需要 HTTPS 和微信合法 request domain；关闭域名校验仅用于本地开发。

这些边界说明当前工程验证覆盖到哪里，也给出了下一步可以被独立评测的方向。
