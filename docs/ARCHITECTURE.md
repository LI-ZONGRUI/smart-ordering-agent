# 项目整体架构

这是Vue3 + uni-app + Pinia + uniCloud的微信点餐项目，包含传统点餐、独立LLM推荐、单轮RAG知识问答。模型不直接操作订单或购物车，当前不是Agent架构。

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
          └─ rag    → knowledge_chunks + dishes
                       ├─ Model Studio / qwen3.7-text-embedding-flash
                       │    Query Embedding（512维）
                       ├─ Exact cosine Top-3（云对象内计算）
                       └─ Model Studio / qwen3.8-flash
                            answerable + evidence IDs
                            → 服务端验证与证据原文渲染
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

## 4. AI推荐与RAG分工

| 能力 | 输入/上下文 | 输出与信任边界 |
| --- | --- | --- |
| ai.recommend(message) | 预算、口味、食材偏好；当前在售dishes | 模型选择菜品；服务器校验真实ID、状态、价格并计算totalPrice；用户手动加购 |
| rag.answer(query) | 单个菜单知识问题；Top-3审核知识及关联实时dishes | 模型选择evidence IDs与answerable；服务器验证后只渲染证据原文；不操作购物车 |

价格、售卖状态必须来自实时数据库，不从模型自由文本提取。后端推荐和RAG分别维护职责，不互相伪装成同一套Agent。

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

## 6. 输出和运行边界

- Generation只允许answerable、dishIds、usedKnowledgeIds；拒绝自由answer/claims等额外字段。
- 服务器验证Top-3引用、实时在售菜品和双向关联，取回证据原文；true按原顺序换行拼接，false使用固定知识不足文案。
- 正式Answer响应不包含similarity、embedding、Prompt、原始模型响应或密钥。前端只显示回答与依据标题/正文，相关菜品重新读取menu service。
- 密钥只存在云对象远程环境变量；前端和admin不保存API Key。保留本地配置的Git忽略规则。
- 当前没有支付、正式登录、多轮会话、流式输出、Agent或Tool Calling；也没有生产级容量与安全治理声明。

## 7. 代码与文档入口

- [前端页面](../src/pages) / [services](../src/services) / [Pinia stores](../src/stores)
- [云对象与管理入口](../uniCloud-aliyun/cloudfunctions) / [数据库定义](../uniCloud-aliyun/database)
- [V4总结](rag/V4_SUMMARY.md) / [Answer API](rag/ANSWER_API.md) / [端到端评测](rag/ANSWER_EVALUATION.md)
- [部署步骤](UNICLOUD_SETUP.md) / [README运行说明](../README.md)
