# 基于 LLM + RAG + Function Calling 的微信智能点餐 Agent

**LLM-powered WeChat Ordering Agent with RAG and Function Calling**

一个基于 Vue 3、uni-app、Pinia 与 uniCloud 的微信点餐项目。它同时实现了 Qwen 菜品推荐、Evidence-first RAG 菜单问答、多步 Function Calling Agent，以及带服务端校价、显式确认和幂等保护的真实订单闭环。

RAG 与 Ordering Agent 是两项独立能力：RAG 负责菜单知识问答，Agent 负责实时菜单 Tool 编排和购物车动作提案；当前没有把 `rag.answer()` 注册成 Agent Tool。

V7.1A 另行建立了一个独立的 Python 3.11 + FastAPI + LangChain 框架服务。它先用离线模型
完成 `create_agent` 多步编排测试，V7.1B-2 再通过正式 `UniCloudHttpMenuGateway` 完成 Python
到真实 uniCloud 菜单的只读验收。V7.1C 已使用真实 Qwen3.8-Flash 完成 LangChain、三个
Structured Tools、HMAC Gateway 与真实菜单数据的端到端验收。V7.2A 已加入项目自有的显式
LangGraph `StateGraph`，并通过 FastAPI 正式入口完成
smalltalk、真实 Qwen 菜单查询和只读拒绝三条路由验收。V7.2B 进一步加入
`knowledge_query → rag_node`：通过同一 HMAC Gateway 的只读 `rag_answer` 复用现有 uniCloud
RAG，并已完成菜单查询、知识问答、闲聊和写操作拒绝四条正式 API 路径的真实验收。详见
[Framework Agent Service](services/framework-agent/README.md)。

V7.2C 已加入第五条 `action_query` 路由：`native_action_node` 经同一 HMAC Gateway 调用现有
Native Agent，只接收其服务端校验后的加购 `pendingAction`。真实验收中，“把柠檬茶加两杯到
购物车”返回柠檬茶 ×2、单价 12 元、合计 24 元且 `requiresConfirmation=true`；Python 节点
随后只根据该结构确定性生成用户提示。LangGraph 不执行购物车或订单写操作。“直接帮我付款”
仍进入 `unsupported_action` 且不返回 `pendingAction`。

V7.1B-1 已在 uniCloud 侧把三个只读菜单能力抽取为同一 Shared Domain，并新增 HMAC-SHA256
认证的只读 Framework Gateway。该 Gateway 已通过真实 uniCloud URL 化、HMAC 和线上菜单数据
验收，Native Agent 也完成抽取后的真实回归。V7.1B-2 已在 Python 侧实现 HMAC v1 HTTP
Gateway Client，通过完全离线的 MockTransport + LangChain Tool Loop 测试，并通过独立脚本
完成 Python 到真实 Gateway 和线上菜单的三个只读操作验收。V7.1C 随后完成真实 Qwen E2E：
模型在 `search_menu("可乐")` 返回空结果后，于下一次模型决策调用
`list_available_drinks()`，没有程序 fallback。协议与验收记录见
[Framework Gateway](docs/framework/FRAMEWORK_GATEWAY.md)。

## 核心亮点

1. **Evidence-grounded RAG**：模型只选择可信 evidence ID，服务器验证后直接使用知识原文渲染答案，避免模型自由改写事实。
2. **Multi-step Function Calling Agent**：Qwen 能观察第一次 Tool Result，再决定第二次 Tool Call；“可乐无结果后查询在售饮料”不是程序硬编码 fallback。
3. **Human-in-the-loop Side Effects**：LLM 只能生成经过服务端校验的 Pending Action，用户明确确认并再次复核实时菜单后，才修改 Pinia Cart。
4. **Deterministic Transaction Boundary**：订单预览、实时计价、确认值比较和持久化全部由普通服务端逻辑执行，不交给 Qwen。
5. **Idempotent Order Creation**：`requestId + canonical fingerprint + UNIQUE sparse index` 为同一订单意图提供服务端重放语义。
6. **Durable WeChat Conversation UI**：微信聊天页通过 capability token 恢复安全历史，以 `AsyncSqliteSaver` 支持同一持久文件系统上的进程重启恢复，并用 UI 显式确认隔离动作提案与购物车副作用。

## Demo / Screenshots

仓库不包含伪造截图。建议按 [Demo Guide](docs/DEMO_GUIDE.md) 从真实微信开发者工具与 uniCloud 控制台截取：

| 场景 | 建议截图 |
| --- | --- |
| 首页能力入口 | AI 智能点餐、菜单问答、智能点餐 Agent |
| RAG 问答 | “有什么比较清爽的？”的 Grounded Answer 与依据 |
| Multi-step Agent | “有可乐吗？没有的话推荐点别的喝的。”的自然语言结果 |
| 安全加购 | 柠檬茶 ×2 Pending Action 与确认按钮 |
| 订单闭环 | ¥24 Preview、最终确认、真实 orderNo |
| 幂等落库 | orders 记录中 requestId 存在，敏感字段打码或裁剪 |

## System Architecture

```mermaid
graph TD
  U[User] --> W[WeChat Mini Program<br/>Vue 3 + uni-app]
  W --> P[Pinia Cart / Order Cache]
  W --> S[Application Services]
  W --> FC[Framework Agent Client<br/>Current Conversation Capability]

  FC --> FAPI[Python 3.11 + FastAPI]
  FAPI --> LG[LangGraph Five-route Workflow]
  FAPI --> SQL[(SQLite / AsyncSqliteSaver)]
  LG --> LCA[LangChain Menu Agent]
  LG --> HMAC[HMAC Framework Gateway]
  LCA --> HMAC

  S --> M[menu cloud object]
  S --> A[ai cloud object]
  S --> R[rag cloud object]
  S --> G[agent cloud object]
  S --> O[orders cloud object]

  HMAC --> R
  HMAC --> G
  HMAC --> D

  A --> Q1[Qwen3.8-Flash<br/>Dish Recommendation]

  R --> E[qwen3.7-text-embedding-flash]
  R --> K[(knowledge_chunks)]
  R --> Q2[Qwen3.8-Flash<br/>Evidence Selection]
  R --> SR[Server Evidence Rendering]

  G --> Q3[Qwen3.8-Flash<br/>Native Function Calling]
  G --> TR[Tool Registry + Executor]
  TR --> D[(dishes)]
  TR --> PA[Pending Cart Action]
  PA --> HC[Explicit User Confirmation]
  HC --> P

  M --> C[(categories)]
  M --> D
  O --> D
  O --> OD[(orders)]
```

图中的 RAG 与 Agent 没有直接连线，因为当前 Agent Loop 不会自动调用 RAG。完整组件、信任边界和数据流见 [Architecture](docs/ARCHITECTURE.md)。

## Core Features

### 基础业务

- 首页、菜单分类、菜品详情、购物车、确认订单、订单列表和个人页。
- Pinia 管理客户端购物车；categories、dishes、orders 使用 uniCloud 持久化。
- 后端读取实时菜品状态与价格，按订单快照保存历史名称、价格、数量和小计。
- 匿名 `clientId` 仅用于开发期数据隔离，不属于身份认证。

### LLM Recommendation

- Qwen3.8-Flash 理解预算、口味、辣度和食材排除条件。
- 模型只能选择当前数据库提供的真实 dishId。
- 服务端再次校验 dishId、`on_sale` 状态与数据库价格，并计算 `totalPrice`。
- 推荐结果可复用现有 Pinia 加购逻辑；模型不能直接创建订单。

## RAG Design

```text
21 verified knowledge chunks
 → qwen3.7-text-embedding-flash / 512 dimensions
 → knowledge_chunks idempotent indexing
 → Query Embedding
 → Exact Cosine Similarity
 → Top-3 Retrieval
 → Qwen evidence selection
 → Server ID validation
 → Server-rendered trusted evidence
```

Knowledge Source 与索引数据保持单向关系：

```text
docs/rag/knowledge-source.json         # 唯一人工维护源
 → rag/resources/knowledge-source.json # 部署副本
 → Embedding / Indexing
 → knowledge_chunks                    # 派生索引
```

价格、销量和在售状态不写入长期知识正文，继续从 dishes 实时读取。

### Evidence-first Grounding 的真实演进

最初让模型基于 Retrieval Evidence 自由生成答案，真实测试中出现了 evidence 没有提供的“解腻”，以及把“具有柠檬香气”扩写为“具有清爽的柠檬香气”。合法 knowledgeId 并不能保证自由文本中的每个 claim 都受支持。

最终合同收紧为模型只返回：

```json
{
  "answerable": true,
  "dishIds": ["dish-3"],
  "usedKnowledgeIds": ["dish-3-taste"]
}
```

服务器验证 ID、读取本次真实 evidence，并按原文生成最终答案。模型仍可能漏选或选择不合适的合法 evidence，但不能自行改写事实后直接展示给用户。

## Agent Design

Agent 使用 Qwen3.8-Flash 的原生 Function Calling，Registry 是唯一机器可读 Tool 合同，Executor 负责 allowlist、Schema 校验和静态实现映射。

当前 Tool：

- `search_menu`
- `list_available_drinks`
- `get_dish_detail`
- `prepare_add_to_cart`

真实多步案例：

```text
User: 有可乐吗？没有的话推荐点别的喝的。
 → Qwen calls search_menu({ query: "可乐" })
 → Tool Result: count = 0
 → Qwen observes the result and re-plans
 → Qwen calls list_available_drinks({})
 → Tool Result: 柠檬茶 / on_sale / ¥12
 → Final natural-language answer
```

第二次调用由模型根据第一次观察决定，不是 `if no cola then list drinks` 的程序分支。

## Safe Action Execution

```text
User: 把柠檬茶加两杯到购物车
 → search_menu
 → prepare_add_to_cart
 → Server revalidates dish / status / price
 → Pending Action: quantity=2, unitPrice=12, totalPrice=24
 → requiresConfirmation=true
 → User clicks 确认加入购物车
 → Frontend reloads live menu and revalidates
 → Pinia addDish(dish, 2)
```

模型不能调用任意 Store mutation。Tool 只生成 Proposal；真正副作用需要服务端事实校验和用户显式确认。

## Order Confirmation & Idempotency

```text
Pinia Cart
 → orders.previewOrder()
 → Fresh Server Validation / Pricing
 → Server-validated Order Proposal
 → Explicit Information Confirmation
 → Final Explicit Order Confirmation
 → Generate requestId once + Freeze Submission Payload
 → orders.createConfirmedOrder()
 → Fresh Validation / Pricing Again
 → Expected Preview Comparison
 → Canonical SHA-256 Fingerprint
 → Persisted Order under UNIQUE sparse request_id_unique
 → Server Success
 → Clear Cart
```

真实保护案例：用户确认柠檬茶 ×2、单价 ¥12、总价 ¥24 后，数据库价格临时变为 ¥13。最终创建返回 `ORDER_CONFIRMATION_STALE`，没有静默按 ¥26 创建订单。

UI 的 `submittingOrder` 只能防普通双击。对于“服务器已写入但响应丢失”，前端会保留 requestId 与冻结的 `clientId/items/expectedPreview/remark`，重试完全相同的 payload：

- 同 requestId + 同 payload：返回首次订单，不重复插入。
- 同 requestId + 不同 payload：返回 `ORDER_IDEMPOTENCY_CONFLICT`。
- 并发安全最终依赖数据库 UNIQUE 约束，而不是存在竞态的 check-then-insert。

## Evaluation

以下为真实云端评测结果，范围是 **21-chunk 小型知识库与 12-query 人工固定评测集**（6 supported、3 unsupported-domain、3 external-OOD），不是生产 Benchmark。

| Metric | Result |
| --- | --- |
| Answerability Accuracy | 91.67%（11/12） |
| Supported Answer Rate | 83.33%（5/6） |
| Unsupported-domain Rejection Rate | 100%（3/3） |
| External-OOD Rejection Rate | 100%（3/3） |
| Retrieval Hit Rate | 100%（6/6 supported） |
| Average Retrieval Recall@3 | ≈80.83% |
| Evidence Hit Rate | 83.33%（5/6 supported） |
| Server Grounding Pass Rate | 100%（12/12） |

唯一 Answerability 错误是 supported False Negative：正确酸梅汤知识已进入 Top-3，但模型仍拒答。这说明 Grounding 结构正确不等于证据选择、完整性和 Answerability 都正确。

Robustness 评测还发现 supported 与 unsupported 的相似度分布发生重叠，因此没有用简单固定 similarity threshold 作为唯一拒答机制。

## Tech Stack

| Layer | Technology |
| --- | --- |
| Client | Vue 3、Composition API、uni-app、Pinia、微信小程序 |
| Backend | uniCloud 阿里云、云对象、云函数、云数据库 |
| Models | Qwen3.8-Flash、qwen3.7-text-embedding-flash |
| Agent Framework | Python 3.11、FastAPI、LangChain、LangGraph StateGraph、AsyncSqliteSaver |
| Protocol | OpenAI-compatible Chat Completions / Embeddings、Native Function Calling |
| Retrieval | 512-dimensional Embedding、Exact Cosine Similarity、Top-3 |
| Validation | JSON Schema、Tool allowlist、服务端事实校验、整数分计价 |
| Testing | Node.js built-in test runner、冻结 fixture、构建与知识副本检查 |

## Project Structure

```text
src/
 ├─ pages/                  # 业务、推荐、RAG、Agent 与会话页面
 ├─ services/               # menu / orders / ai / rag / agent / framework-agent
 └─ stores/                 # Pinia Cart、订单查询缓存与当前会话状态

services/framework-agent/   # FastAPI + LangChain + LangGraph + SQLite durable conversation

uniCloud-aliyun/
 ├─ cloudfunctions/
 │   ├─ menu / orders / ai / rag / agent
 │   └─ *-admin             # 仅开发验收入口
 └─ database/               # categories / dishes / knowledge_chunks / orders

docs/
 ├─ rag/                    # Knowledge、Indexing、Retrieval、Grounding、Evaluation
 ├─ agent/                  # Tools、Loop、Actions、Confirmation、Orders
 ├─ ARCHITECTURE.md
 ├─ DEMO_GUIDE.md
 ├─ FINAL_SUMMARY.md
 ├─ RESUME_NOTES.md
 └─ INTERVIEW_NOTES.md
```

## Run / Setup

准备 Node.js 20+、pnpm、HBuilderX 与微信开发者工具：

```sh
pnpm install
pnpm run rag:check-source
pnpm run build:mp-weixin
```

构建产物位于 `dist/build/mp-weixin`。CLI 构建不会部署云对象、初始化数据库或调用远程模型。

新环境还需要：

1. 在 HBuilderX 登录 DCloud，并关联阿里云 uniCloud 服务空间。
2. 初始化 categories、dishes、orders、knowledge_chunks schema/index。
3. 部署 menu、orders、ai、rag、agent 云对象。
4. 为对应云对象配置远程环境变量。
5. 在 HBuilderX 运行到微信开发者工具，并保持连接云端云函数。

详细步骤见 [uniCloud Setup](docs/UNICLOUD_SETUP.md)、[RAG Indexing](docs/rag/INDEXING.md)、[Agent Loop](docs/agent/AGENT_LOOP.md) 与 [Order Idempotency](docs/agent/ORDER_IDEMPOTENCY.md)。

## Environment Variables

| Cloud Object | Variables |
| --- | --- |
| ai | `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` |
| rag | `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSION`、`RAG_LLM_MODEL` |
| agent | `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`AGENT_LLM_MODEL` |
| framework-gateway | `FRAMEWORK_GATEWAY_SECRET` |
| WeChat client build | `VITE_FRAMEWORK_AGENT_BASE_URL` |

真实 API Key 只配置在远程环境，不写入源码、日志或 Git。`.env`、`.hbuilderx/`、服务空间绑定文件和云函数 `*.param.json` 均由 Git 忽略。

## Testing

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```

当前回归：**851 项 JavaScript 测试与 275 项 Python 测试通过**。测试覆盖 RAG 索引/检索/生成/评测、Agent Tool 与多步循环、五路显式 LangGraph 路由、Hybrid Router、多轮上下文化、SQLite 重启恢复、capability token、History API、微信会话 UI、动作提案、订单预览/创建、幂等并发语义、Agent Benchmark 自检、前端状态以及冻结文件未漂移。

项目另提供独立的 [Agent Benchmark V1](docs/framework/AGENT_BENCHMARK.md)：120 条固定案例分为
80 Dev / 40 冻结 Holdout，并选取 25 条 Golden E2E。默认 Runner 完全离线，只报告实际观察到的
确定性指标；真实 Qwen/Gateway/uniCloud 评测必须使用双重显式 live 开关。Rule Router 的
68/80 Dev 基线已用于设计安全优先的 Hybrid Router，但尚未运行真实 Qwen Dev 或 Golden E2E。

## Known Limitations / Future Work

- Knowledge Base 只有21条人工审核 chunks；12-query baseline 是项目级小样本评测。
- RAG 接口本身仍是单轮；Python LangGraph 通过显式 durable conversation 提供受限多轮语义上下文。
- `AsyncSqliteSaver` 已真实验证同一持久文件系统上的进程重启恢复，但不提供跨机器、多实例或账户级跨设备同步。
- V7.3C 微信聊天页面已完成真实验收；当前没有 conversation list、token expiry/rotation/revocation UI、多轮文本确认执行或长期用户画像。
- History API 只恢复安全文字，旧 `pendingAction` 卡片不会跨页面重进恢复；Markdown-like 内容按安全纯文本展示。
- Framework Agent 正式部署仍需要 HTTPS 和微信合法 request domain；开发者工具关闭域名校验只用于本地验收。
- RAG 没有注册成 Agent Tool，两项能力保持独立。
- 购物车仍在客户端 Pinia；Pending Action 不持久化。
- 未决 requestId 与 frozen payload 不跨页面刷新或小程序重启恢复。
- 没有微信登录、支付、库存事务或 exactly-once distributed transaction。
- 当前使用 Exact Search，没有 production-scale Vector DB、ANN 或分布式检索系统。
- clientId 只是开发期匿名隔离，不是正式认证。

这些是当前作品集范围。后续应先扩大人工评测与失败分析，再比较 reranker、hybrid retrieval、多轮状态和持久化提交恢复；支付与库存需要独立的交易设计。

## Evolution / Milestones

```text
Local Ordering
 → uniCloud Persistence
 → Qwen Recommendation
 → Verified Knowledge Source
 → Embedding / Idempotent Indexing
 → Retrieval / Robustness Evaluation
 → Evidence-first Grounded Answer
 → WeChat RAG UI
 → Tool Foundation
 → Multi-step Ordering Agent
 → Cart Proposal / Explicit Execution
 → Server Order Preview / Checkout Proposal
 → Persisted Confirmed Order
 → Server Idempotency
 → Frontend Same-key Retry Integration
 → V7.2A Explicit StateGraph
 → V7.2B RAG Route Integration
 → V7.2C Native Agent Action Proposal Route
 → V7.3A Thread-aware Multi-turn Backend
 → V7.3B Persistent Conversation + Safe History API
 → V7.3C WeChat Conversation UI + Explicit Cart Confirmation
```

V7.2A、V7.2B、V7.2C 均已完成实现与对应真实验收。V7.3A 在既有五路图上加入可选
`threadId`、进程内 `InMemorySaver`、最多 8 条顶层 user/assistant 消息和 Qwen Contextualizer，
并已完成真实多轮验收。`query` 保留用户原文，`resolved_query` 只用于内部路由；历史负责语义
消歧，实时菜单 Tool 与现有 RAG 继续提供事实。

真实连续请求验证了菜单价格追问、RAG 口味追问、柠檬茶 ×2 动作提案、文本“确认”安全拒绝、
不同 thread 隔离以及无 `threadId` 的旧客户端兼容。首次验收曾因 forced named `tool_choice` 与
单一 normalized Tool Call 假设过窄而统一返回 `FRAMEWORK_CONTEXT_FAILED`；修复后使用普通
Tool Calling，并严格兼容 normalized/raw/JSON 三种形态。本次真实响应走
`normalized_tool_call`，不代表供应商永远只返回该形态。

V7.3B 使用 `langgraph-checkpoint-sqlite==3.1.1` 的 `AsyncSqliteSaver`：服务端通过
`POST /v1/conversations` 生成 `threadId + conversationToken`，只保存 token 的 SHA-256 digest，
并以 `hmac.compare_digest` 校验。真实验收中，Process 1 完成“有柠檬茶吗？”后完全停止，
Process 2 使用同一 SQLite 文件、threadId 与 token 继续询问“多少钱？”，成功恢复语义上下文，
同时价格仍重新进入 live menu path。History API 成功读取两轮安全 user/assistant 消息，错误
token 返回 `FRAMEWORK_CONVERSATION_ACCESS_DENIED`。这只证明同一持久文件系统上的进程重启
恢复；conversationToken 不是用户身份或交易授权。

V7.3C 将 durable conversation 接入微信小程序：真实多轮验收依次覆盖实时菜单、价格追问、RAG
口味追问和柠檬茶 ×2 动作提案。UI 卡片确认后重新读取 uniCloud 菜单、校验价格和状态，再复用
既有 Pinia `addDish`，购物车最终为 ×2、合计 ¥24；文字“确认”没有再次执行动作，也没有创建
订单或支付。页面退出重进与 FastAPI 完全重启后均恢复了安全历史；新对话创建新 capability，
旧会话不删除。CLI 开发产物缺少 HBuilderX uniCloud 运行环境时，实时复核按预期 fail closed；
改用已关联远程服务空间的 HBuilderX 运行后确认成功。

当前阶段状态：

- V7.3A Thread-aware multi-turn backend：✅
- V7.3B Persistent conversation + safe History API：✅
- V7.3C WeChat ChatGPT-style conversation UI：✅ 真实微信开发者工具验收完成

完整冻结状态与真实 commit 里程碑见 [Final Summary](docs/FINAL_SUMMARY.md)。

## Interview Highlights

- 为什么合法 citation ID 仍不能保证 claim 语义受支持？
- 为什么相似度分数重叠后没有直接加 threshold？
- 为什么 Agent 算多步，但没有把 RAG 硬绑成 Tool？
- 为什么 LLM 只能生成 Proposal，不能直接修改 Cart？
- 为什么订单 Preview 后还要在 Create 阶段再次校价？
- 为什么数据库 UNIQUE index 比 check-then-insert 更可靠？
- 为什么 History 只用于语义消歧，价格和状态仍必须查实时 Tool？
- 如何定位真实 Qwen Contextualizer output shape 兼容问题？

可直接用于求职的材料见 [Resume Notes](docs/RESUME_NOTES.md)、[Interview Notes](docs/INTERVIEW_NOTES.md) 和 [Demo Guide](docs/DEMO_GUIDE.md)。
