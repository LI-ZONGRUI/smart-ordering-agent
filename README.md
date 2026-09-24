# 微信智能点餐与 RAG 菜单问答

使用 **Vue 3 + uni-app + Composition API + Pinia + uniCloud + Qwen** 构建的微信点餐学习项目。围绕真实菜单完成点餐、云端订单持久化、自然语言菜品推荐，以及基于人工审核知识的单轮 RAG 菜单问答。

**单轮 RAG 后端已完成端到端评测，菜单问答 UI 已通过真实微信开发者工具验收。** 当前不是生产级客服系统，也没有实现 Agent 或多轮聊天。

- [整体架构](docs/ARCHITECTURE.md)
- [V4 RAG 总结、设计演进与失败案例](docs/rag/V4_SUMMARY.md)
- [简历素材](docs/RESUME_NOTES.md) · [面试说明](docs/INTERVIEW_NOTES.md)

## 为什么做这个项目

在可运行的点餐业务上验证两类不同的模型能力：一类理解预算和偏好并推荐真实菜品；另一类检索审核过的菜品知识回答问题。重点是区分模型判断与业务事实，并通过服务端验证和固定评测定位错误，而不仅是接通一个模型 API。

## 核心能力

| 能力 | 已实现内容 |
| --- | --- |
| 点餐闭环 | 菜单分类、详情、Pinia 购物车、增减/删除/清空、确认订单、订单列表 |
| 云端持久化 | categories / dishes / orders；提交订单时后端重新校验状态与价格，保存订单快照 |
| AI 智能点餐 | Qwen3.8-Flash 理解预算、口味和食材偏好，返回1～3道真实菜品；后端校验ID、在售状态和价格 |
| 菜单问答 | 独立页面调用 rag.answer(query)，支持1～200 Unicode字符的单轮问题，展示服务器回答、依据及实时相关菜品 |
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
      └─ rag    → knowledge_chunks + dishes
                    + Query Embedding + Qwen证据选择
                    → 服务端验证、原文渲染
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

## AI / RAG 如何工作

**AI 智能点餐**读取当前在售菜单，将必要字段提供给 Qwen。模型选择菜品后，服务器校验 ID、再次读取状态与价格、按分计算总价；加购复用 Pinia，订单走原有后端校价流程。LLM 不提供可信价格。

**RAG 菜单问答**先将 Query 转为512维向量，从 verified knowledge_chunks 做 Exact Cosine Top-3，再查询关联实时菜品。Qwen仅返回 `answerable`、`dishIds`、`usedKnowledgeIds`；服务器验证引用，取回本次检索证据，按原文换行生成最终回答。模型不能自由改写最终事实措辞。

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

ai读取 `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`；rag独立读取 `DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`EMBEDDING_MODEL`、`EMBEDDING_DIMENSION`、`RAG_LLM_MODEL`。Embedding为qwen3.7-text-embedding-flash/512，Generation为qwen3.8-flash；真实密钥只配置到云端，不能写入仓库。

日常联调从HBuilderX“运行→运行到小程序模拟器→微信开发者工具”启动，保持“连接云端云函数”。不要同时运行CLI开发监听，避免争用 `dist/dev/mp-weixin`。从首页进入“AI智能点餐”或“菜单问答”。

开发说明：当前微信开发者工具的sourcemap兼容问题通过仅在 `mp-weixin + development` 下关闭sourcemap规避，正式发行和其他平台不受该条件影响。详细配置见 `vite.config.js`。

## 验证与安全边界

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```

V4.4.4收尾时417项本地测试通过，包括前端状态与service、后端校验、评测和冻结文件检查。本地测试使用模拟HTTP/数据库，不代表模型真实效果；远程评测需要人工通过管理入口运行。

- clientId只是开发阶段匿名隔离，不是真正认证；未来可用uni-id/userId替代。不能当作正式用户授权。
- 数据库客户端直连权限关闭，业务通过云对象访问；购物车在Pinia内存，订单持久化在云端。
- `.env`、`.hbuilderx/`、服务空间本地绑定和云函数 `*.param.json` 由Git忽略；不记录真实API Key、Authorization或敏感原始响应。
- 原mock文件保留作参考，正式菜单不回退到mock。图片当前仍为包内静态资源。

## Known Limitations / Roadmap

当前为21-chunk小知识库，12-query评测规模有限；仅支持单轮，Evidence Selection仍可能漏选，Answerability存在False Negative，Top-3可能不完整。尚无reranker、hybrid retrieval、query rewrite、conversation memory、Agent或Tool Calling，当前不是production-ready系统。

未来可先扩展人工评测和失败分析，再以冻结baseline比较检索/选择策略；身份认证、生产治理和更大规模数据需另行设计。多轮与V5 Agent仅为未来方向，本阶段未实现，也不承诺其一定优于现有单轮方案。

## 文档导航

| 文档 | 用途 |
| --- | --- |
| [整体架构](docs/ARCHITECTURE.md) | 前端、状态、服务、云对象与数据库边界 |
| [V4总结](docs/rag/V4_SUMMARY.md) | RAG设计演进、真实结果与失败案例 |
| [知识审核](docs/rag/REVIEW.md) / [索引结构](docs/rag/KNOWLEDGE_CHUNKS.md) | 来源、歧义、字段与索引 |
| [Generation演进](docs/rag/GENERATION_TEST.md) | 自由回答到evidence-first的真实实验 |
| [正式Answer接口](docs/rag/ANSWER_API.md) / [端到端评测](docs/rag/ANSWER_EVALUATION.md) | 调用合同、错误、指标和复现 |
| [简历素材](docs/RESUME_NOTES.md) / [面试说明](docs/INTERVIEW_NOTES.md) | 求职表达，不属于产品运行功能 |
