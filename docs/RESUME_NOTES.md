# 求职项目素材

## 项目名称

**基于 LLM + RAG + Function Calling 的微信智能点餐 Agent**

技术栈：Vue 3、Composition API、uni-app、Pinia、uniCloud、Qwen3.8-Flash、qwen3.7-text-embedding-flash、Function Calling、JSON Schema、云数据库

以下表述基于仓库真实实现、微信开发者工具验收和 uniCloud 云端验证。RAG 菜单问答与 Ordering Agent 是两项独立能力，当前没有把 `rag.answer()` 注册为 Agent Tool。

## A. 中文完整版（4 条）

- 构建 Vue 3 + uni-app 微信点餐闭环，使用 Pinia 管理购物车、uniCloud 持久化菜单与订单；在服务端重新校验菜品状态和价格、按整数分计算金额并保存订单快照，避免信任客户端价格。
- 设计 Evidence-first RAG 菜单问答：将 21 条人工审核知识生成 512 维向量，以 Exact Cosine Top-3 检索，由 Qwen 只选择 evidence ID，再由服务器校验并按可信原文渲染答案；12 条固定云端评测中 Server Grounding Pass 为 12/12，Answerability 为 11/12。
- 实现基于 Qwen 原生 Function Calling 的多步 Ordering Agent，通过 Tool Registry、Executor allowlist 与 JSON Schema 约束工具调用；真实验证模型可观察 `search_menu` 空结果后自主调用 `list_available_drinks`，并将加购限制为待确认 Proposal。
- 建立人机确认与确定性交易边界：购物车动作经服务端复核和用户确认后才修改 Pinia；订单经过 Preview、最终确认、再次校价和逐项预期比较，并以 `requestId + SHA-256 fingerprint + UNIQUE sparse index` 实现同请求重放与冲突检测。

> 指标口径：RAG 数据来自 21-chunk 小型知识库与 12-query 人工固定评测集（6 supported、3 unsupported-domain、3 external-OOD），属于项目级验证，不代表生产准确率。

## B. 中文压缩版（3 条）

- 构建 Vue 3、uni-app、Pinia 与 uniCloud 微信点餐系统，完成云端菜单、购物车、订单预览、服务端实时校价、订单快照与持久化闭环。
- 设计 21 条人工审核知识的 Evidence-first RAG，以 512 维 Embedding + Exact Cosine Top-3 检索，由模型选择证据、服务器渲染事实；12 条固定评测中 Answerability 11/12、Server Grounding 12/12。
- 实现原生 Function Calling 多步 Agent 与 Human-in-the-loop 副作用控制，并通过 Preview 二次校价、`ORDER_CONFIRMATION_STALE`、requestId 指纹和数据库唯一索引保护订单确认与重试。

## C. English Version (4 bullets)

- Built a WeChat ordering flow with Vue 3, uni-app, Pinia, and uniCloud, including cloud-backed menus, cart management, server-side pricing, immutable order snapshots, and persisted order history.
- Designed an evidence-first RAG pipeline over 21 human-reviewed knowledge chunks using 512-dimensional embeddings and exact cosine Top-3 retrieval; constrained Qwen to evidence selection and rendered factual answers on the server, achieving 11/12 answerability and 12/12 server-grounding passes on a fixed 12-query project evaluation set.
- Implemented a multi-step Ordering Agent with native function calling, a centralized tool registry, executor allowlists, and JSON Schema validation; verified that the model can observe a failed menu search and select a second read tool without a hard-coded fallback.
- Established human confirmation and deterministic transaction boundaries for side effects, with live cart revalidation, order preview and repricing, stale-confirmation rejection, and idempotent order creation using request IDs, canonical SHA-256 fingerprints, and a unique sparse database index.

## 推荐使用方式

- 一页中文简历优先使用 **B. 中文压缩版**；版面允许时使用 A 的 4 条。
- 英文简历使用 C，并保留 “fixed 12-query project evaluation set” 的口径。
- 面试时结合 [INTERVIEW_NOTES.md](INTERVIEW_NOTES.md) 解释真实失败案例、信任边界和限制，不把项目描述为生产级支付或库存系统。

## 不应扩写的能力

- 没有微信支付、库存事务、正式用户认证或无人值守自动下单。
- RAG 为单轮菜单问答；Agent 没有多轮会话记忆，也不会自动调用 RAG。
- 当前使用 21 条知识和 Exact Search，没有生产规模 Vector DB。
- Pending Action 与未决订单提交状态没有跨小程序重启恢复。
