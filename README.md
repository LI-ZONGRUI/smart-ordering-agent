# 微信智能点餐、RAG 菜单问答与 Ordering Agent

使用 **Vue 3 + uni-app + Composition API + Pinia + uniCloud + Qwen** 构建的微信点餐学习项目。围绕真实菜单完成点餐、云端订单持久化、自然语言菜品推荐、基于人工审核知识的单轮RAG问答，以及基于原生Function Calling的Ordering Agent。

**单轮RAG已完成端到端评测与微信UI验收；Ordering Agent的多步Function Calling、服务端动作提案、显式用户确认、实时菜单复核和Pinia购物车执行均已完成真实验收。** 只有明确点击确认且实时复核通过后才修改购物车。当前仍不是生产级客服或完整自主下单Agent。

- [整体架构](docs/ARCHITECTURE.md)
- [V4 RAG 总结、设计演进与失败案例](docs/rag/V4_SUMMARY.md)
- [简历素材](docs/RESUME_NOTES.md) · [面试说明](docs/INTERVIEW_NOTES.md)

## 为什么做这个项目

在可运行的点餐业务上验证三类模型能力：理解预算和偏好并推荐真实菜品；检索审核知识回答问题；根据用户目标自主选择并串联实时菜单Tool。重点是区分模型判断与业务事实，并通过服务端验证、Tool执行边界和固定评测定位错误。

## 核心能力

| 能力 | 已实现内容 |
| --- | --- |
| 点餐闭环 | 菜单分类、详情、Pinia 购物车、增减/删除/清空、确认订单、订单列表 |
| 云端持久化 | categories / dishes / orders；提交订单时后端重新校验状态与价格，保存订单快照 |
| AI 智能点餐 | Qwen3.8-Flash 理解预算、口味和食材偏好，返回1～3道真实菜品；后端校验ID、在售状态和价格 |
| 菜单问答 | 独立页面调用 rag.answer(query)，支持1～200 Unicode字符的单轮问题，展示服务器回答、依据及实时相关菜品 |
| Ordering Agent | Qwen原生Function Calling，自主调用真实菜单Tool；生成服务端校验的购物车提案，并由用户在微信页面明确确认后复核实时菜单、修改Pinia购物车 |
| 知识与索引 | 21条人工审核知识，512维 Embedding，批量幂等索引、唯一ID及内容哈希 |
| 评测 | Retrieval、Robustness、12-query端到端 Answerability / Evidence / Grounding 评测 |

首页保留五项 TabBar；AI 推荐页和菜单问答页通过首页独立入口进入。菜单问答不操作购物车；用户可进入已有菜品详情。没有聊天历史或自动下单。

## 技术与架构

```text
微信小程序（Vue3 / uni-app）
 ├─ Pinia：购物车、订单查询缓存
 └─ services：menu / orders / ai / rag
      ↓
    uniCloud 云对象
      ├─ menu   → categories / dishes
      ├─ orders → dishes校价 → orders持久化
      ├─ ai     → dishes + Qwen3.8-Flash → 服务端校验推荐
      ├─ rag    → knowledge_chunks + dishes
                    + Query Embedding + Qwen证据选择
                    → 服务端验证、原文渲染
      └─ agent  → Qwen Function Calling → Registry / Executor
                    → Read-only Menu Tools / prepare_add_to_cart
                    → Pending Action → UI明确确认
                    → 实时菜单复核 → Pinia购物车
```

模型通过 Alibaba Cloud Model Studio 的 OpenAI-compatible API 调用，使用 `uniCloud.httpclient.request`。完整组件和数据边界见 [ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 实现阶段

| 阶段 | 完成内容 |
| --- | --- |
| Local Ordering Flow | 先打通本地菜单→购物车→确认订单→订单列表 |
| uniCloud Persistence | 菜单与订单迁移到云端，重新打开小程序可查看历史订单 |
| Qwen Recommendation | 独立 AI 智能点餐能力，服务端菜品白名单与实时价格校验 |
| RAG Knowledge Source | 冻结21条 verified知识，记录来源字段与版本 |
| Embedding / Indexing | qwen3.7-text-embedding-flash，512维；首次插入21条，第二次全部skip，真实验证幂等性 |
| Retrieval / Evaluation | Exact Cosine Top-3，检索与无答案 Robustness 评测 |
| Grounded Generation | 模型仅选择evidence IDs，服务器读取真实证据并生成事实文本 |
| Single-turn Answer | 正式 rag.answer(query)，诊断与正式接口复用共享逻辑 |
| End-to-End Evaluation | 12条固定问题，区分检索遗漏、证据选择遗漏和拒答错误 |
| WeChat Menu QA UI | 单次输入、回答、依据、相关菜品与正常拒答，真实微信验收通过 |
| Read-only Ordering Agent | 三个菜单Tool、Executor allowlist、原生Function Calling和有限多步Agent Loop，真实云端验收通过 |
| Cart Action Proposal | `prepare_add_to_cart`重新查询菜品状态与价格，生成无副作用的Pending Action；后端本身不修改购物车 |
| Cart Confirmation UI | 用户通过按钮确认提案；前端重新读取实时菜单，状态与价格一致后才调用现有Pinia购物车；真实微信验收通过 |
| Server Order Preview | `orders.previewOrder(items)`与创建订单共用实时校验/计价核心；只返回待确认明细，不写订单，已通过真实uniCloud菜单数据验收 |
| Checkout Proposal UI | Pinia购物车只提交dishId/quantity，校验服务端Preview后展示订单提案；信息确认停在页面状态，真实微信验收通过 |
| Confirmed Order Execution | 用户再次点击“确认下单”；服务端重新校验计价并逐项比较已确认Preview，一致后持久化并在成功后清空Cart；真实微信与uniCloud验收通过 |
| Order Idempotency Foundation | `createConfirmedOrder()`可选接收requestId，使用规范化SHA-256指纹与阿里云稀疏唯一索引防止同键重复订单；真实uniCloud重放与冲突验收通过 |

## AI / RAG 如何工作

**AI 智能点餐**读取当前在售菜单，将必要字段提供给 Qwen。模型选择菜品后，服务器校验 ID、再次读取状态与价格、按分计算总价；加购复用 Pinia，订单走原有后端校价流程。LLM 不提供可信价格。

**RAG 菜单问答**先将 Query 转为512维向量，从 verified knowledge_chunks 做 Exact Cosine Top-3，再查询关联实时菜品。Qwen仅返回 `answerable`、`dishIds`、`usedKnowledgeIds`；服务器验证引用，取回本次检索证据，按原文换行生成最终回答。模型不能自由改写最终事实措辞。

**Ordering Agent**把Registry作为唯一Tool定义源，Qwen通过原生 `tool_calls` 自主选择工具；服务器解析参数并继续通过Executor allowlist和Schema校验，再以 `role=tool` 回传真实结果。V5.3新增的 `prepare_add_to_cart` 只接受dishId和数量，重新查询真实状态与价格并生成待确认提案；它不会修改Pinia购物车。RAG与Agent当前是两项独立能力，RAG尚未注册为Agent Tool。

**V5.4前端确认流程**只接受正式 `agent.run()` 返回的合法提案。用户点击确认后，页面重新读取真实菜单；菜品不存在、售罄或价格变化都会让旧提案失效。只有校验通过后才显式调用现有Pinia `addDish`。V5.4 frontend confirmation flow has been integrated and validated in the WeChat mini-program.

**V5.5A订单预览**把实时菜品校验、数据库价格读取和整数分计价抽成 `previewOrder()` / `createOrder()` 的共享核心。Preview只读dishes并返回 `requiresConfirmation=true`，不会生成订单或写orders；正式创建时仍会再次查询和计价。**Server-validated order preview has been validated against the real uniCloud menu data.** 详见 [Order Preview](docs/agent/ORDER_PREVIEW.md)。

**V5.5B结算提案**从当前Pinia购物车只提取dishId和quantity，调用正式 `orders.previewOrder()`，严格校验服务端明细与整数分金额后在Agent页面展示。用户“确认订单信息”只确认当前提案，购物车快照变化会让旧提案失效；不调用Qwen、createOrder，不清空购物车。**Checkout proposal flow has been integrated and validated in the WeChat mini-program.** 详见 [Checkout Proposal](docs/agent/ORDER_PROPOSAL.md)。

**V5.5C最终订单确认**新增确定性的 `orders.createConfirmedOrder()`：最终按钮点击后，服务器重新读取菜品状态和价格，逐项核对用户已确认Preview，完全一致才复用原订单快照结构持久化；成功响应后才清空Pinia购物车。价格变化返回 `ORDER_CONFIRMATION_STALE`，售罄和任何失败均保留Cart。该流程不经过Qwen，没有Agent Order Tool或支付。**Confirmed order execution has been validated in the WeChat mini-program and the real uniCloud orders collection.** 详见 [Order Execution](docs/agent/ORDER_EXECUTION.md)。

**V5.6A服务器订单幂等基础**为 `createConfirmedOrder()` 增加可选requestId。相同requestId和相同规范化fingerprint返回首次订单；内容或clientId不同返回 `ORDER_IDEMPOTENCY_CONFLICT`。真实控制台已确认 `request_id_unique` 为requestId升序、unique和sparse；真实重试返回第一次的同一orderNo且没有新增第二条记录，不同订单意图被冲突错误拒绝。V5.6B正式微信Checkout在第一次最终提交时生成requestId并冻结payload，结果未知时复用同一key与同一payload。真实微信订单已在orders集合观察到非空requestId与requestFingerprint，金额24元、数量2、状态pending。完整key和fingerprint不写入文档。刷新或小程序重启后的持久恢复尚未实现。**Server-side idempotent order creation has been integrated into and validated through the real WeChat checkout flow.** 详见 [Order Idempotency](docs/agent/ORDER_IDEMPOTENCY.md)。

知识维护单向流转：

```text
docs/rag/knowledge-source.json（唯一人工维护源）
 → rag/resources/knowledge-source.json（部署副本）
 → Embedding / Indexing
 → knowledge_chunks（派生索引）
```

价格、在售状态和销量不进入长期知识正文，实时业务字段由 dishes 提供。Grounding 演进与局限见 [V4_SUMMARY.md](docs/rag/V4_SUMMARY.md)。

## 真实评测与验收

以下来自开发者真实云端执行：**21-chunk小型知识库、12-query人工固定评测集**（6 supported、3 unsupported-domain、3 external-ood），12条全部完成，无执行失败。

| 指标 | 结果 |
| --- | --- |
| Answerability Accuracy | 91.67%（11/12） |
| Supported Answer Rate | 83.33%（5/6） |
| Unsupported Rejection | 100%（6/6） |
| Retrieval Hit Rate | 100%（6/6 supported） |
| Average Retrieval Recall@3 | ≈80.83% |
| Evidence Hit Rate | 83.33%（5/6 supported） |
| Average Evidence Precision / Recall | 75% / ≈55.83% |
| Server Grounding Pass | 100%（12/12） |

这些不是生产环境准确率。酸梅汤问题的正确知识已进入Top-3，却被模型拒答；饮料问题存在完整性不足。结构Grounding通过不意味着证据选择或Answerability正确，详见 [Answer Evaluation](docs/rag/ANSWER_EVALUATION.md)。

检索Robustness真实结果中，supported最低Top-1为0.373664，unsupported最高为0.405820，gap=-0.032156。因此没有以固定similarity threshold自动拒答，详见 [Retrieval Evaluation](docs/rag/RETRIEVAL_EVALUATION.md)。

**Single-turn RAG menu QA has been integrated and validated in the WeChat mini-program.** 微信开发者工具已验证“有什么比较清爽的？”、“我想吃牛肉”的回答与依据，以及“有可乐吗”的正常知识不足拒答；没有把缺少知识错误表达为确定不存在。完整验收记录见 [V4总结](docs/rag/V4_SUMMARY.md)。

**Read-only Ordering Agent已完成真实云端验收。** 对“有可乐吗？没有的话推荐点别的喝的。”，Qwen先调用 `search_menu`，观察count=0后再自主调用 `list_available_drinks`，取得真实在售柠檬茶；这不是程序写死的fallback。柠檬茶存在时会在一次Tool后停止，酸梅汤场景能识别“存在但售罄”，“你好”则不调用Tool。详见 [Agent Loop](docs/agent/AGENT_LOOP.md)。

**Validated Cart Action Proposal也已完成真实云端验收。** “把柠檬茶加两杯到购物车”会先查询实时菜单，再生成数量2、单价12元、总价24元且需要确认的Pending Action；没有购物车写操作。模型面对售罄酸梅汤会停止，直接强制调用Action Preparation Tool也会被服务端以 `AGENT_ACTION_DISH_UNAVAILABLE` 拒绝。Agent can prepare a server-validated cart action that requires explicit confirmation before execution. 详见 [Action Proposal](docs/agent/ACTIONS.md)。

**V5.4微信确认流程已真实验收。** 柠檬茶提案确认前购物车保持不变；点击确认后，前端重新读取实时菜单并验证状态、12元单价与提案金额，随后复用Pinia准确增加2杯。取消不会再次调用Qwen、读取菜单或修改购物车；售罄酸梅汤不会产生确认卡。准确能力名称是：**Action-capable Ordering Agent with server-validated pending actions, explicit user confirmation, and frontend cart execution.**

**V5.5A Server-validated Order Preview已完成真实uniCloud验收。** 柠檬茶两杯的真实Preview由数据库返回名称与12元单价，服务端计算总价24元；售罄酸梅汤返回 `ORDER_DISH_UNAVAILABLE`。验收后检查orders集合，未观察到本次Preview创建的新订单记录。

**V5.5B Checkout Proposal Flow已完成真实微信验收。** 购物车中柠檬茶两杯可生成单价12元、合计24元的服务端订单提案；点击“确认订单信息”后只显示已确认但尚未创建订单，购物车和orders集合保持不变。不可用菜品会显示友好错误且不生成确认卡。购物车数量/项目变化导致旧Preview失效的边界由自动化测试覆盖，本次未把跨页场景表述为真实UI复现。在V5.5B阶段，该确认不是下单，也不执行订单持久化；V5.5C的最终确认与创建状态见下文。Agent Order Tool和支付仍未实现。

**V5.5C Confirmed Order Execution已完成真实微信与uniCloud验收。** 柠檬茶两杯以单价12元、总价24元完成最终确认，页面显示的订单号 `OD1790357975859B4A2B5` 与orders集合持久化记录一致，状态为 `pending`，服务端成功后Cart清空。价格从12元临时变为13元时返回 `ORDER_CONFIRMATION_STALE`，没有按26元创建订单；最终确认前临时售罄时同样拒绝写入。两种失败均保留Cart并使旧Proposal失效，测试数据随后已恢复。V5.6A服务端幂等与V5.6B正式微信Checkout现已真实接通；最新验收订单包含非空requestId与requestFingerprint。

当前主业务链已经真实覆盖：Natural Language Request → Qwen Ordering Agent → Native Function Calling → Multi-step Tool Orchestration → Server-validated Cart Action Proposal → Explicit User Confirmation → Real Pinia Cart Mutation → Server-validated Order Preview → Explicit Order Information Confirmation → Final Explicit Order Confirmation → Fresh Server Revalidation → Persisted Order。它可以描述为“具备多步工具调用、服务端动作校验、显式用户确认和真实订单持久化能力的智能点餐Agent”。最终交易执行仍是确定性的服务器边界，不是LLM自主调用订单Tool；当前没有自动支付、Agent自主支付、无人确认自动下单或完整支付闭环。

## 如何运行

准备 Node.js 20+、pnpm、HBuilderX 和微信开发者工具。在项目根目录执行：

```sh
pnpm install
pnpm run rag:check-source
pnpm run build:mp-weixin
```

构建产物位于 `dist/build/mp-weixin`。构建只检查知识副本并编译，不部署云对象、不初始化数据库、不调用远程模型。

新环境需本人登录DCloud、关联阿里云uniCloud服务空间、配置AppID、初始化数据库、部署云对象及设置远程环境变量：

1. [uniCloud基础部署](docs/UNICLOUD_SETUP.md)：menu、orders及业务数据库。
2. [索引说明](docs/rag/INDEXING.md)：知识副本、knowledge_chunks schema/唯一索引、rag部署与首次索引；已有空间不要重复初始化业务数据。
3. [Answer API](docs/rag/ANSWER_API.md)：rag模型环境变量和管理测试入口。
4. [Agent Loop](docs/agent/AGENT_LOOP.md)：agent独立环境变量、Function Calling协议、管理Trace和真实验收。
5. [Action Proposal](docs/agent/ACTIONS.md)：购物车待确认动作、服务端校价和无副作用边界。
6. [User Confirmation](docs/agent/CONFIRMATION.md)：微信确认按钮、实时菜单复核与Pinia购物车执行边界。
7. [Order Preview](docs/agent/ORDER_PREVIEW.md)：服务端只读订单预览、共享校验计价和HBuilderX验收参数。
8. [Checkout Proposal](docs/agent/ORDER_PROPOSAL.md)：Pinia购物车到服务端预览、订单提案、快照失效与信息确认边界。
9. [Order Execution](docs/agent/ORDER_EXECUTION.md)：最终确认、服务端重新计价、确认值比较与持久化。
10. [Order Idempotency](docs/agent/ORDER_IDEMPOTENCY.md)：requestId、规范化指纹、稀疏唯一索引、前端冻结payload、安全重试与部署步骤。

ai读取 `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`；rag独立读取 `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSION`、`RAG_LLM_MODEL`；agent也在自身云对象中独立读取 `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`AGENT_LLM_MODEL`。Embedding为qwen3.7-text-embedding-flash/512，Generation和Agent目标模型为qwen3.8-flash；真实密钥只配置到云端，不能写入仓库。

日常联调从HBuilderX“运行→运行到小程序模拟器→微信开发者工具”启动，保持“连接云端云函数”。不要同时运行CLI开发监听，避免争用 `dist/dev/mp-weixin`。从首页进入“AI智能点餐”或“菜单问答”。

开发说明：当前微信开发者工具的sourcemap兼容问题通过仅在 `mp-weixin + development` 下关闭sourcemap规避，正式发行和其他平台不受该条件影响。详细配置见 `vite.config.js`。

## 验证与安全边界

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```

本地测试覆盖前端状态与service、后端校验、Agent Loop、Action Proposal、管理Trace、RAG评测和冻结文件检查。本地Agent测试使用Mock Model；真实Agent与Action Proposal效果由开发者通过管理入口完成验收。

- clientId只是开发阶段匿名隔离，不是真正认证；未来可用uni-id/userId替代。不能当作正式用户授权。
- 数据库客户端直连权限关闭，业务通过云对象访问；购物车在Pinia内存，订单持久化在云端。
- `.env`、`.hbuilderx/`、服务空间本地绑定和云函数 `*.param.json` 由Git忽略；不记录真实API Key、Authorization或敏感原始响应。
- 原mock文件保留作参考，正式菜单不回退到mock。图片当前仍为包内静态资源。

## Known Limitations / Roadmap

当前为21-chunk小知识库，12-query评测规模有限；RAG仅支持单轮，Evidence Selection仍可能漏选，Answerability存在False Negative，Top-3可能不完整。Ordering Agent同样是单次用户任务；购物车和订单副作用都需要用户显式确认，最终订单通过确定性的orders云对象创建，没有conversation memory、云端Cart/Order Agent Tool、支付或库存事务。V5.6A的服务器幂等基础已通过真实uniCloud验收，但尚未接入微信正式Checkout；当前不是production-ready系统。

未来可先扩展人工评测和失败分析，再以冻结baseline比较检索/选择策略；身份认证、生产治理和更大规模数据需另行设计。多轮记忆以及服务端Cart/Order Write Tool属于后续阶段。

## 文档导航

| 文档 | 用途 |
| --- | --- |
| [整体架构](docs/ARCHITECTURE.md) | 前端、状态、服务、云对象与数据库边界 |
| [V4总结](docs/rag/V4_SUMMARY.md) | RAG设计演进、真实结果与失败案例 |
| [知识审核](docs/rag/REVIEW.md) / [索引结构](docs/rag/KNOWLEDGE_CHUNKS.md) | 来源、歧义、字段与索引 |
| [Generation演进](docs/rag/GENERATION_TEST.md) | 自由回答到evidence-first的真实实验 |
| [正式Answer接口](docs/rag/ANSWER_API.md) / [端到端评测](docs/rag/ANSWER_EVALUATION.md) | 调用合同、错误、指标和复现 |
| [Agent Tool](docs/agent/TOOLS.md) / [Agent Loop](docs/agent/AGENT_LOOP.md) | 只读工具合同、Function Calling、循环边界与真实验收 |
| [Action Proposal](docs/agent/ACTIONS.md) | Action Preparation Tool、Pending Action与确认边界 |
| [User Confirmation](docs/agent/CONFIRMATION.md) | 显式UI确认、实时菜单复核、Pinia执行与失效规则 |
| [Order Preview](docs/agent/ORDER_PREVIEW.md) | 服务端校验的只读订单预览、共享计价与创建时二次校验 |
| [Checkout Proposal](docs/agent/ORDER_PROPOSAL.md) | 前端订单提案、服务端Preview校验、购物车快照与仅信息确认边界 |
| [Order Execution](docs/agent/ORDER_EXECUTION.md) | 最终订单确认、服务端确认值比较、持久化和失败时Cart保留 |
| [Order Idempotency](docs/agent/ORDER_IDEMPOTENCY.md) | requestId、request fingerprint、稀疏唯一索引和重试冲突处理 |
| [简历素材](docs/RESUME_NOTES.md) / [面试说明](docs/INTERVIEW_NOTES.md) | 求职表达，不属于产品运行功能 |
