# 微信点餐小程序：云端点餐与 LLM 智能推荐

本项目使用 Vue 3、uni-app CLI、Composition API 和 Pinia。首页、菜单、购物车、订单、我的五个 TabBar 页面保持原有结构。菜单和订单现已改为调用 uniCloud 云对象；购物车仍保存在本次运行的 Pinia 内存中。

**当前状态：uniCloud 点餐闭环、LLM 智能点餐 V1，以及单轮 RAG 后端与端到端评测均已完成真实云端验证。** A single-turn RAG backend has been implemented and evaluated end-to-end. 微信单轮菜单问答 UI 已接入并完成真实微信开发者工具验收，当前结果不代表完整生产客服系统或 answerability 已解决。

已完成并验证：

- Vue 3 + uni-app + Composition API + Pinia 页面与购物车。
- 云端菜单：分类返回 5 条、菜品返回 8 条，推荐分类显示 4 道菜。
- 云端订单：真实下单成功，数据库中可以看到订单记录。
- 后端重新校验菜品状态和数据库价格，计算金额，并保存下单时的订单快照。
- 匿名 `clientId` 隔离与云端订单持久化；关闭并重新打开小程序后，历史订单仍可查看。

## 第三阶段：LLM 智能点餐 V1

已接入 Alibaba Cloud Model Studio 的 Qwen3.8-Flash，通过 OpenAI-compatible Chat Completions API 调用。用户从首页“AI 智能点餐”进入推荐页，输入一句自然语言需求，获得 1～3 道真实菜品；无法满足时显示明确说明。

推荐流程：

1. 前端 `src/services/ai.js` 调用 uniCloud `ai.recommend(message)`，校验输入为 1～200 字。
2. 后端读取真实 `dishes` 云数据库，将在售菜品的必要字段作为模型上下文。
3. 使用 Structured JSON 输出，模型只返回 `dishIds` 和推荐理由；后端解析并检查结构，执行 dishId 白名单校验、去重和数量限制。
4. 返回前再次查询数据库，二次校验售罄状态并重新读取价格。菜品名称、图片、配料等展示字段来自数据库；后端按分汇总并计算 `totalPrice`，不采信模型返回的价格。
5. 推荐菜品加购前刷新状态，复用现有 Pinia `cartStore.addDish()`；订单仍走原有确认和后端校价流程。

**LLM 负责语义理解和推荐决策；数据库和 uniCloud 负责事实、状态、价格和业务规则。** 常见数字预算和明确食材排除有额外后端校验，复杂口味偏好仍由模型理解。当前 AI 菜品推荐版本是单轮推荐，不是 RAG，也不是 Agent；没有多轮对话、工具执行或聊天历史数据库。

API Key 仅通过云对象运行环境中的 `DASHSCOPE_API_KEY` 读取；`LLM_BASE_URL` 和 `LLM_MODEL` 也从环境变量读取。真实密钥不写入源码或前端，不打印 Authorization 请求头或原始敏感请求。`.env` 等本地配置继续由 `.gitignore` 忽略。`testConnection()` 保留作为手动连通诊断方法，任何页面均不自动调用。

已由开发者通过真实 Qwen3.8-Flash + uniCloud 完成以下五组人工验收，结果符合预期：

- “我想吃辣一点的，50元以内，不要牛肉”
- “随便推荐点清淡的”
- “我预算只有1元”
- “给我推荐宫保鸡丁”
- “我想吃辣的，不要牛肉，再来个饮料，预算50元”

本地回归测试使用模拟接口验证边界与错误处理，不调用真实模型，不使用真实密钥：

```bash
node --test tests/ai-recommend.test.cjs
```

新环境部署可参考 [新手部署步骤](docs/UNICLOUD_SETUP.md)。

## V4.2：Embedding 与知识索引（已完成）

已通过 Alibaba Cloud Model Studio 的 OpenAI-compatible Embeddings API，使用 `qwen3.7-text-embedding-flash` 生成 512 维向量。V4.2 包括单条连通测试、三条批量测试、`knowledge_chunks` 数据结构，以及可重复、幂等的正式 Indexing Pipeline。

知识数据流：

```text
docs/rag/knowledge-source.json（唯一人工维护源）
  → rag/resources/knowledge-source.json（自动生成的部署副本）
  → Embedding（只处理新增或变化的知识，每批最多 10 条）
  → knowledge_chunks（云端派生知识与向量）
```

- Knowledge Source V1 共 21 条，均为 `verified: true`、`sourceVersion: 1`。未来修改知识应先修改、审核源文件，再同步和重新索引，不直接手改部署副本或数据库正文。
- `rag:sync-source` 生成部署副本和 SHA-256 清单；`rag:check-source` 逐字节检查副本。构建前也会检查一致性，云端读取副本时会验证清单。HBuilderX 上传前仍需手动同步并检查。
- 以 `knowledgeId` 为唯一身份。比较 `sourceVersion`、`contentHash`、`embeddingModel`、`embeddingDimension`；未变化则 skip，不调用 Embedding API。`contentHash` 基于固定顺序的知识内容和来源元数据 JSON 计算 SHA-256。
- 批量响应按 `item.index` 映射知识，校验索引完整性、唯一性及 512 个有限数字，允许响应乱序。数据库写入失败会明确计入 failed；重跑时跳过已完成记录。orphan 只报告 ID，不自动删除。
- `testEmbedding()` / `testBatchEmbedding()` 保留用于手动诊断，仅返回短预览。页面不自动调用它们，也没有 `buildKnowledgeIndex()` 前端入口。
- 索引通过受限的 `rag-index-admin` 管理云函数手动执行，不属于普通用户功能。API Key 仅从 rag 的远程环境变量读取；不打印密钥、Authorization 请求头或完整向量。

### 真实环境验收记录

以下记录依据开发者于 **2026-09-21** 确认的真实环境验证；本次收尾仅执行本地检查，没有再次调用远程模型或写入数据库。

| 验证步骤 | 已确认结果 |
| --- | --- |
| 单条 Embedding | 返回 512 维向量，数字有效 |
| 三条 Batch Embedding | 返回 3 条 512 维向量，映射验证成功 |
| 首次正式索引 | 21 条知识插入 `knowledge_chunks` |
| 第二次正式索引 | 21 条全部 skip，验证重复运行的幂等性 |

第二次全部 skip 对应代码中的零 Embedding 请求分支；本地测试也覆盖该行为。这些索引现已用于下述 V4.3 检索与评测，以及 V4.4.1 固定 Query 的 RAG 生成诊断；原有 AI 菜品推荐业务未改为 RAG，正式单轮 rag.answer(query) 已实现并验证，微信 RAG 前端已实现并完成真实验收。

完整操作和失败处理见 [索引说明](docs/rag/INDEXING.md)，字段见 [knowledge_chunks 结构说明](docs/rag/KNOWLEDGE_CHUNKS.md)。

## V4.3：Exact Retrieval 与 Evaluation（已真实验证）

V4.3 完成范围：verified Knowledge Source V1、Embedding + Indexing Pipeline、21 条 512 维 knowledge_chunks、幂等 Indexing、Exact Cosine Retrieval、Top-3 Retrieval、Retrieval Evaluation 和 Robustness Evaluation。

Retriever 使用 `qwen3.7-text-embedding-flash`、512 维、21 条知识，按原始 cosine similarity 排序后取 Top-3。当前没有 threshold、reranker、BM25 / Hybrid Search、keyword/type boost、dish 去重、query rewrite、intent router 或 answerability classifier。

### 真实云端验证结果

以下依据开发者于 2026-09-22 收尾时提供的真实验证结果；本次没有重新执行远程评测：

| 评测 | 主要结果 |
| --- | --- |
| Baseline（19 Query，其中 7 labeled） | Hit@3 = 7/7 = 100%；Average Recall@3 ≈ 0.80；Average Coverage@3 ≈ 95.24% |
| Robustness（24 Query，其中 11 supported、12 hard unsupported、1 exploratory） | supported Top-1 relevant = 11/11；Hit@3 = 11/11；Average Recall@3 ≈ 0.865152；Average Coverage@3 ≈ 96.97% |
| Robustness separation | supported 最低 Top-1 0.373664，unsupported 最高 Top-1 0.405820；gap = -0.032156，真实发生重叠 |

当前相关知识排序表现良好，但 **fixed cosine threshold alone was not sufficient for perfect answerability separation on the tested dataset**。cosine 仍用于相关知识排序；其绝对分数不能独立稳定地判断知识库是否有答案。本阶段只记录实验结论，没有实现 threshold 或拒答策略。

这些结果来自当前 **21-chunk 小型项目知识库与人工评测集**，不能直接推广为大规模生产系统性能。完整的单 Query Top-3、分布、指标定义和复现步骤见 [Retrieval Evaluation 报告](docs/rag/RETRIEVAL_EVALUATION.md)。

### 已完成的边界

V4.3 已完成 RAG indexing and retrieval pipeline 与评测；其冻结结果由下述 V4.4.1 最小 Generation 链路复用。正式单轮接口已在 V4.4.2 完成，微信 RAG 问答页面已实现并完成真实验收，也没有加入 Reranker、Hybrid Search 或 Answerability classifier。

检索与评测是开发/管理工具：`testRetrieval()`、`testEmbedding()`、`testBatchEmbedding()` 保留作诊断；`rag-eval-admin` 与 `rag-robustness-eval-admin` 用于人工执行两套独立固定评测，页面不会自动调用。历史 Baseline、Retriever、Knowledge Source 与 Indexer 均保持冻结，没有为了提高指标修改排名或标签。

## V4.4.1：最小 RAG Generation（已真实验证）

依据开发者提供的真实远程验收，当前已完成 Knowledge Source V1、Embedding / Indexing、Exact Cosine Retrieval、Retrieval Evaluation / Robustness Evaluation，以及最小 Retrieval-Augmented Generation。固定 Query 为“有什么比较清爽的？”，由 `rag-generation-admin → rag.testRagGeneration()` 手动触发，无前端入口。

最终 V4.4.1c 使用 **Qwen evidence selection → server-side evidence ID validation → evidence-first grounded rendering**：Qwen3.8-Flash 只返回 `answerable`、`dishIds` 和 `usedKnowledgeIds`；服务器校验后，从本次 Retrieval results 读取真实正文，按选择顺序换行拼接最终 answer。模型自由 answer、claim.text 和其他额外字段均被拒绝。

真实复验返回 `errCode: 0`，答案由鲜蔬沙拉“清爽”、拍黄瓜“爽脆”、柠檬茶“具有柠檬香气”三条 evidence 原文组成，不再出现“解腻”或“清爽的柠檬香气”等扩写。这关闭了自由 answer 绕过 claims、以及模型 claim.text 在合法引用下扩写事实的输出路径。

当前解决的是事实措辞的信任边界。模型仍可能漏选或错选合法 evidence、误判 answerable，检索 Top-3 也可能漏掉正确知识；不构成 formal correctness 或 semantic grounding 的整体保证。后续 V4.4.2 / V4.4.3 已完成正式单轮接口与固定评测，结果见下节。

rag 继续从自身远程环境变量读取 `RAG_LLM_MODEL=qwen3.8-flash` 和现有 Embedding 配置；密钥不进入源码。原有 AI 推荐、Retriever、Knowledge Source、Indexer、数据库结构及前端保持不变。完整真实演进、当前合同与按需复验步骤见 [Generation 验证记录](docs/rag/GENERATION_TEST.md)。

## V4.4.2 / V4.4.3：单轮 RAG 后端与端到端评测（已真实验证）

当前 RAG Backend 已完成：verified Knowledge Source V1、Embedding / Indexing Pipeline、21 条 knowledge_chunks、Exact Cosine Top-3 Retrieval、Retrieval Evaluation、Robustness Evaluation、Evidence-first Grounded Generation、正式 `rag.answer(query)` 和 End-to-End Generation / Answerability Evaluation。

正式接口支持 1～200 Unicode 字符的单轮文本，通过实时 dishes 和 Qwen evidence selection 后，由服务器校验 IDs 并直接使用证据原文生成答案。不向正式客户端返回 similarity、向量、Prompt、内部诊断或原始模型响应。

以下 baseline 来自开发者完成的真实云端运行，12 条全部完成、无执行失败：

| 指标 | 真实结果 |
| --- | --- |
| Answerability Accuracy | 91.67%（11/12） |
| Unsupported rejection | 100%（6/6） |
| Retrieval Hit Rate | 100%（6/6 supported） |
| Evidence Hit Rate | 83.33%（5/6 supported） |
| Avg Retrieval Recall@3 | ≈80.83% |
| Avg Evidence Precision | 75% |
| Avg Evidence Recall | ≈55.83% |
| Server Grounding Pass | 100%（12/12） |

唯一 False Negative 为“酸梅汤是什么味道？”：`dish-8-taste` 已被检索，但 Generation 未选择并拒答。饮料问题存在 Retrieval availability 和 Evidence Selection 两层完整性损失。这些结果反映当前 **21-chunk 小型知识库、12-query 人工固定评测集**，不能推广为生产性能；Grounding 结构通过不等于语义相关、完整或判断正确。

仍未完成：多轮聊天、Agent / Tool Calling、大规模 Evaluation，以及 Reranker / Hybrid Search 等实验。该后端 baseline 保持冻结，前端接入不调整指标或后端行为。

详见 [Answer API 与人工验收](docs/rag/ANSWER_API.md) 和 [真实端到端评测记录](docs/rag/ANSWER_EVALUATION.md)。HBuilderX 云函数本地 `*.param.json` 参数文件由 Git 忽略，不作为正式源文件提交。

## V4.4.4：微信菜单问答 UI（已真实验收）

**Single-turn RAG menu QA has been integrated and validated in the WeChat mini-program.**

以下记录来自开发者提供的真实微信开发者工具验收，不是本地 mock；本次收尾仅更新文档、执行本地检查，没有再次调用远程 API。

### 三个真实前端案例

1. **有什么比较清爽的？**
   - 成功进入独立“菜单问答”页面，正式 `rag.answer(query)` 正常调用。
   - 页面展示服务器 grounded answer：鲜蔬沙拉项目描述为“清爽”；拍黄瓜中的黄瓜项目描述为“爽脆”；柠檬茶项目描述为具有柠檬香气。
   - “依据”区域展示对应可信证据，没有暴露 knowledgeId、embedding、similarity 等内部字段。
   - 未出现此前“解腻”“清爽的柠檬香气”等无依据扩写。
   - supported Query 的 UI → rag.answer → grounded rendering 链路真实通过。
2. **我想吃牛肉**
   - 真实微信页面正常回答，包括番茄牛肉面使用番茄汤底并搭配牛肉、双椒牛肉由牛肉搭配青椒和红椒，以及番茄牛肉面主要配料为牛肉、番茄、面条、青菜等真实 evidence 内容。
   - “依据”区域与回答对应。前端输入 → 正式单轮 rag.answer(query) → evidence selection → server rendering → 微信页面展示真实通过。
3. **有可乐吗**
   - 页面正常返回“当前提供的知识不足以回答这个问题。”。
   - answerable=false 被作为正常业务结果，没有显示“系统错误”或“请求失败”，没有展示无关依据或相关菜品。
   - 没有编造“有可乐”或“没有可乐”。当前知识库没有关于可乐的可靠知识，因此没有把“没有检索到”解释为“确定不存在”，符合预期的 grounded refusal。

### 当前产品边界

“菜单问答”是 **single-turn menu knowledge QA**，与“AI 智能点餐”推荐页独立。支持单个文本问题、正式 rag.answer(query)、服务器原文回答、可信依据、按 dishIds 获取实时菜单信息，以及正常展示 answerable=false。示例 chip 只填入文本，不自动请求；再次提问覆盖当前结果。

当前没有多轮聊天、会话历史、Agent、Tool Calling、Streaming Chat、自动加购或自动下单，也不是通用客服机器人。相关菜品复用 menu service 的当前价格与状态，并跳转原菜品详情；技术失败使用固定友好提示，请求期间禁止重复提交。

当前知识库仍为 **21 chunks**，后端 baseline 为 **12-query 人工固定评测集**。上述三个前端案例验证界面与后端链路，不是新增准确率评测，不能推广为生产环境性能或 production-ready AI assistant。既有91.67% Answerability baseline 与完整性、证据选择局限继续保留；本次未修改后端、Prompt、检索、评测集或知识库。

## 目录

```text
├── src/
│   ├── App.vue                     启动时生成匿名 clientId
│   ├── constants/dish.js           辣度文案
│   ├── mock/                       原有数据，保留作初始化来源与开发参考
│   ├── services/                   页面调用云对象的入口
│   │   ├── ai.js                   智能推荐调用与友好错误
│   │   ├── clientId.js
│   │   ├── menu.js
│   │   └── orders.js
│   ├── stores/                     Pinia 购物车与云端订单列表缓存
│   └── pages/                      九个页面（含 ai-recommend、rag-qa，TabBar 仍为五项）
├── uniCloud-aliyun/
│   ├── cloudfunctions/
│   │   ├── ai/                      testConnection、recommend
│   │   ├── menu/                    getCategories、getDishes
│   │   ├── orders/                  createOrder、getOrders
│   │   ├── rag/                     索引、检索、评测模块与 resources 部署资源
│   │   ├── rag-index-admin/         手动执行索引的管理入口
│   │   ├── rag-eval-admin/          Baseline 固定评测管理入口
│   │   ├── rag-robustness-eval-admin/ Robustness 固定评测管理入口
│   │   ├── rag-generation-admin/    固定 Query Generation 诊断入口
│   │   ├── rag-answer-admin/        单轮 Answer 人工测试入口
│   │   └── rag-answer-eval-admin/   固定12条端到端评测入口
│   └── database/                    四个 collection 定义；knowledge_chunks 无向量初始化文件
├── scripts/sync-rag-source.cjs     同步、检查知识部署副本
├── tests/                         AI 推荐、Embedding、索引、检索、评测及冻结文件回归测试
└── docs/
    ├── UNICLOUD_SETUP.md           HBuilderX 人工部署与验证步骤
    └── rag/                       冻结知识源、审核记录、索引说明与真实检索评测报告
```

## 数据流

- 菜单页调用 `src/services/menu.js`，再调用 `menu` 云对象。云对象从 `categories` 和 `dishes` collection 读取数据。菜单页有加载中、失败重试和空数据状态。菜品详情同样从云端加载。
- 购物车使用 Pinia；菜品从云端加载后会同步价格和上下架状态。购物车页面显示的价格仅供确认。
- 确认订单页调用 `src/services/orders.js`，只传 `dishId`、`quantity`、`remark` 和临时 `clientId`。`orders` 云对象重新查询 `dishes`，检查是否在售，并用数据库价格计算每项小计、总数量和总价。写入成功后才清空购物车。
- 订单页每次显示时调用 `getOrders(clientId)`，从云端读取该 clientId 的订单，按时间倒序展示。订单 `items` 保存下单时的菜名、价格、数量与小计快照。

**clientId 只是开发阶段的临时隔离方式，不属于真正的身份认证；以后接入 uni-id 后会改成 userId。** 它保存在小程序本地存储，清除小程序数据、换设备或重装后可能改变。知道或伪造其他 clientId 的人可能查询对应订单，因此不要把本阶段用于真实顾客资料或正式经营。

## 数据库字段

| collection | 主要字段 |
| --- | --- |
| `categories` | `_id`、`name`、`sort` |
| `dishes` | `_id`、`name`、`categoryId`、`description`、`price`、`image`、`sales`、`spicyLevel`、`ingredients`、`status`、`recommended`、`createTime`、`updateTime` |
| `orders` | `_id`、`orderNo`、`items`、`totalPrice`、`totalCount`、`remark`、`status`、`clientId`、`createTime` |
| `knowledge_chunks` | `knowledgeId`、`scope`、`dishId`、`type`、`title`、`text`、来源信息、`sourceVersion`、`verified`、`contentHash`、`embedding`、`embeddingModel`、`embeddingDimension`、`createTime`、`updateTime` |

`price` 和 `totalPrice` 单位为元；计算时云对象先转换为分，再汇总。`spicyLevel` 为 0～5，依次是不辣、微辣、中辣、辣、很辣、特辣。`status` 在菜品中是 `on_sale` 或 `sold_out`；订单状态是 `pending`、`preparing`、`completed`、`cancelled`，本阶段只创建 `pending` 订单。

`dishes.image` 暂时沿用 `/static/dishes/*.png`。这些路径指向**小程序包内图片**，不是云存储文件。以后若要让运营人员在云端新增菜品图片，应再迁移到云存储。

四个 schema 的客户端数据库直连读写权限均为 `false`。菜单与订单只通过云对象访问数据库，知识索引由管理流程写入。因为现在没有正式登录，`clientId` 的查询限制仍不能视为安全授权。

## 完整本地检查

```bash
pnpm run rag:check-source
node --test tests/*.test.cjs
pnpm run build:mp-weixin
git diff --check
```

这些测试使用模拟 HTTP 和内存数据库，不调用真实 Embedding 或写入云数据库。源码中的环境变量名、示例值、测试假密钥不是真实凭据；真实 API Key 仅配置在云端，`.env` / `.env.*` 继续被忽略（可公开的 `.env.example` 除外）。

## 构建

准备 Node.js 20+、pnpm、微信开发者工具。项目根目录执行：

```bash
pnpm install
pnpm run build:mp-weixin
```

日常云端联调请在 HBuilderX 中打开当前项目，通过“运行 → 运行到小程序模拟器 → 微信开发者工具”启动，并选择“连接云端云函数”。开发产物位于 `dist/dev/mp-weixin`；不要同时运行 `pnpm run dev:mp-weixin`，避免两个编译进程写入同一目录。

`pnpm run build:mp-weixin` 先检查知识部署副本，再进行前端正式构建，产物位于 `dist/build/mp-weixin`；命令本身不会生成向量、部署云对象或初始化数据库。关联服务空间及云端联调步骤见 [新手部署步骤](docs/UNICLOUD_SETUP.md)。

开发说明：当前微信开发者工具与 development sourcemap 存在兼容问题（`No element indexed by 9`）。`vite.config.js` 暂时只在 `mp-weixin + development` 下关闭 sourcemap，正式发行与其他平台配置不受影响。开发调试期间无法通过 sourcemap 定位原始源码行号；兼容问题修复后可移除该条件配置。

原有 `src/mock/categories.js` 和 `src/mock/dishes.js` 仍保留。页面已不再从它们读取分类或菜品；`uniCloud-aliyun/database/*.init_data.json` 是从它们整理出的初始化数据。确认真实云空间运行后，可在未来阶段删除 mock 数据，但本阶段保留供对照。

## 参考文档

- [DCloud：CLI 项目接入 uniCloud](https://uniapp.dcloud.net.cn/uniCloud/quickstart.html)
- [DCloud：云对象](https://doc.dcloud.net.cn/uniCloud/cloud-obj.html)
- [DCloud：数据库初始化](https://doc.dcloud.net.cn/uniCloud/hellodb.html)
- [DCloud：DB Schema](https://doc.dcloud.net.cn/uniCloud/schema.html)
