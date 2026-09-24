# V4.4.2：单轮 rag.answer(query)

## 状态和职责

正式单轮 `rag.answer(query)` 已实现，并由开发者完成真实云端人工验收。V4.4.1c 的固定 Query 真实验收记录仍见 [GENERATION_TEST.md](GENERATION_TEST.md)。本地测试使用模拟 HTTP，不代表模型效果结论。

```text
任意单轮文本 Query
 → 服务端校验与 trim
 → Query Embedding（qwen3.7-text-embedding-flash，512 维）
 → verified knowledge_chunks → 原 Exact cosine Top-3
 → 只查询 Top-3 关联的实时 dishes
 → Qwen3.8-Flash 选择 evidence IDs / 判断 answerable
 → 服务器校验合同、IDs、菜品关联及状态
 → 从真实检索快照取 evidence 原文
 → 再次检查实时菜品快照 → 返回确定性拼接的 answer
```

当前不是多轮聊天、Agent、工具执行系统或完整生产 answerability 方案。没有前端入口、历史会话、二次 LLM Judge 或自动重试，没有新增依赖。

## 已完成的真实云端人工验收

以下为开发者提供的真实远程结果，不是本地 mock；本次收尾未重新调用 API。

| Query | 实际结果 | 人工结论 |
| --- | --- | --- |
| 我想吃牛肉 | answerable=true；evidence 包括 dish-2-description、dish-6-description、dish-2-ingredients；dishIds 为 dish-2、dish-6；答案由服务器使用原文生成 | Answerability 正确、证据选择合理、Grounding 正确 |
| 有什么饮料？ | answerable=true；只使用 dish-4-ingredients，返回柠檬茶信息 | Answerability 与 Grounding 正确，但完整性不足，没有完整覆盖酸梅汤；不能记作完全成功 |
| 可以开发票吗？ | answerable=false；固定回答“当前提供的知识不足以回答这个问题。”；dishIds、usedKnowledgeIds、evidence 全为空 | 餐厅领域内但知识库无答案，正确拒答 |
| 今天香港天气怎么样？ | answerable=false；同一固定拒答文案；所有引用为空 | 外部 OOD 正确拒答 |

饮料问题随后由 V4.4.3 自动 Evaluation 分别分析 Retrieval miss 和 Evidence Selection miss。完整真实 baseline 见 [ANSWER_EVALUATION.md](ANSWER_EVALUATION.md)。这些案例不构成生产级正确性保证。

## 输入

```javascript
const rag = uniCloud.importObject('rag', { customUI: true })
const result = await rag.answer('我想吃牛肉')
```

上面仅说明调用签名，本阶段不放入页面。只接收字符串；去除前后空白后，按 Unicode 码点计数为 1～200 个字符。空值、对象、数组和超长文本返回 `RAG_QUERY_INVALID`，不消耗 Embedding 或 Generation API。不能传 messages、model、topK、自定义系统 Prompt、图片、文件或音频。

所有 Query、检索、证据和答案都属于单次调用的局部变量，不保存用户历史或完整请求日志。

## 冻结 Retriever 的复用

`retriever.js` 及原冻结 fixtures 完全不变。新的 `query-retrieval.js` 仅适配任意文本的单条 Embedding 请求，调用冻结模块导出的 `readConfig`、`readCandidates`、`rankCandidates` 和 `cosineSimilarity`。没有复制 cosine、候选校验或排序实现；原固定检索诊断的 Embedding 传输保留在冻结文件中。

模型、512 维、Exact Search、Top-K=3、分数降序与 knowledgeId 次级排序全部保持原规则。没有 threshold、boost、改写、reranker 或过滤优化。V4.3 Robustness 的 supported 最低 Top-1 约 0.373664、unsupported 最高约 0.405820，gap 约 -0.032156；不根据分数自动判定 answerable。

`generator.js` 的 `answerQuery(query, options)` 为共享底层链路：

- `answer(query)` 返回正式精简响应。
- `testRagGeneration()` 使用固定“有什么比较清爽的？”，保留原 retrieval / generation 诊断响应、旧 evidence 字段及 Retrieval 错误映射。仍由 `rag-generation-admin` 调用，原入口和测试不变。

## Evidence-first 合同与服务端规则

模型恰好只能返回：

```json
{
  "answerable": true,
  "dishIds": ["dish-4"],
  "usedKnowledgeIds": ["dish-4-taste"]
}
```

`answer`、`claims`、`text`、`evidence`、`price`、`reason`、`explanation` 等额外字段全部拒绝。用户文本和知识作为数据分区提供，不能覆盖系统规则。模型不得用自身常识补充餐厅事实。

- true：至少一个本次 Top-3 knowledgeId，去重保留首次顺序；未知 ID 拒绝。
- dishIds 必须来自本次实时菜品且仍在售。每个 dishId 必须对应至少一条选中的 **dish-scope** evidence；选中的 dish-scope evidence 也必须列出其 dishId，避免绕过状态检查。
- restaurant-scope evidence 允许 dishId=null、dishIds=[]。
- false：dishIds 和 usedKnowledgeIds 必须均为空，返回固定“当前提供的知识不足以回答这个问题。”，evidence=[]。
- 服务器按已验证 ID 从本次检索结果读取 knowledgeId、dishId、scope、type、title、text，最终 `answer = evidence.map(item => item.text).join('\n')`。不使用任何模型事实措辞。
- 返回 true 前再次读取关联菜品；实时字段变化、售罄或删除时，拒绝旧结果，不重新生成。价格与状态仍以 dishes 为准；当前答案渲染只展示知识原文，不让模型编写实时价格。

正式响应示例（仅说明结构，不是真实执行记录）：

```json
{
  "errCode": 0,
  "query": "想喝柠檬味的",
  "answerable": true,
  "answer": "柠檬茶，项目描述为具有柠檬香气。",
  "dishIds": ["dish-4"],
  "usedKnowledgeIds": ["dish-4-taste"],
  "evidence": [{
    "knowledgeId": "dish-4-taste",
    "dishId": "dish-4",
    "scope": "dish",
    "type": "taste",
    "title": "柠檬茶：风味或口感",
    "text": "柠檬茶，项目描述为具有柠檬香气。"
  }]
}
```

正式响应不包含 similarity、向量、Prompt、模型配置、原始模型响应、请求头或密钥。合法证据仍可能不相关，模型仍可能误判 answerable，检索可能漏掉正确知识；复制真实正文不等于完整语义正确性保证。

## 错误边界

| 类别 | 安全错误码 |
| --- | --- |
| 输入 | RAG_QUERY_INVALID |
| Embedding 配置/网络/API/向量 | RETRIEVAL_CONFIG_INVALID / RETRIEVAL_QUERY_REQUEST_FAILED / RETRIEVAL_QUERY_HTTP_ERROR / RETRIEVAL_QUERY_RESPONSE_INVALID |
| 知识数据库 | RETRIEVAL_DATABASE_FAILED / RETRIEVAL_EMPTY / RETRIEVAL_DATA_INVALID |
| Generation 配置 | RAG_GENERATION_CONFIG_MISSING / RAG_GENERATION_CONFIG_INVALID |
| Generation 网络/API | RAG_GENERATION_REQUEST_FAILED / RAG_GENERATION_HTTP_ERROR |
| JSON 或合同 | RAG_GENERATION_RESPONSE_INVALID |
| 引用 ID 或关联 | RAG_GENERATION_IDS_INVALID |
| 实时菜品异常或变化 | RAG_LIVE_DISH_FAILED / RAG_LIVE_FACTS_CHANGED |

未知异常返回固定安全兜底错误。所有失败只返回 errCode / errMsg，不返回原始异常或上游内容。

## HBuilderX 人工真实验收

1. 本地运行下方检查；不要重新 Indexing 或初始化数据库。
2. 上传部署更新后的 `rag`，确保包含 `generator.js`、`query-retrieval.js` 和现有资源。
3. 保持 rag 的远程变量：`DASHSCOPE_API_KEY`、`LLM_BASE_URL`、`EMBEDDING_MODEL=qwen3.7-text-embedding-flash`、`EMBEDDING_DIMENSION=512`、`RAG_LLM_MODEL=qwen3.8-flash`。不向测试参数或 admin 写入密钥。
4. 上传 `rag-answer-admin`。此入口只接受平台 `context.SOURCE === 'server'`，不配置 URL 化或前端调用；只转发 event.query 给正式 rag.answer。
5. 在 HBuilderX 对该管理函数“上传并运行”，参数例如 `{"query":"我想吃牛肉"}`。每次完整成功请求会调用一次 Embedding 和一次 Generation。
6. 检查 errCode、answerable、证据关联，以及 answer 是否恰好由 evidence 原文按顺序换行拼接。拒答应为固定文本和空 ID / evidence。
7. 如需历史固定诊断，仍用 `rag-generation-admin` 和 `{}`；不要改旧入口。

正式 rag.answer 是后端单轮接口，不依赖管理入口的权限校验来实现身份认证；本阶段未接前端、未新增登录或生产流量治理。管理入口的来源限制不能等同于整个正式接口已具备生产认证机制。

保留的人工复验 Query 清单（不代表以下每条都已完成单独人工验收）：

| 预期类别 | Query |
| --- | --- |
| 有知识支持 | 有什么比较清爽的？ |
| 有知识支持 | 我想吃牛肉 |
| 有知识支持 | 有什么饮料？ |
| 有知识支持 | 拍黄瓜是什么口感？ |
| 有知识支持 | 酸梅汤是什么味道？ |
| 有知识支持 | 哪些菜里有辣椒？ |
| 无知识支持 | 你们可以开发票吗？ |
| 无知识支持 | 可以订座吗？ |
| 无知识支持 | 今天香港天气怎么样？ |
| 无知识支持 | Python 怎么安装？ |

以上为保留的复验清单。V4.4.3 的独立 12-query 自动评测也已完成真实云端运行，结果见评测文档；本次仅固化文档，不再次运行真实 API。

## 本地检查

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```

新增 `tests/rag-answer.test.cjs` 覆盖输入、真实 Query 传递、输出白名单、拒答、ID/关联、餐厅知识、并发隔离与安全错误；原固定诊断和冻结文件测试继续执行。
