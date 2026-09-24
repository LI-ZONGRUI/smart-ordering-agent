# V4.4.3：RAG Generation / Answerability Evaluation

## 状态与目标

本阶段增加固定、可重复的开发评测工具，评估 Answerability、Evidence Selection、Retrieval availability 和 Server Grounding structure。12 条固定评测已由开发者完成真实云端运行，下列 baseline 来自开发者提供的真实结果，不是本地 mock；本次收尾未重新调用远程 API。

依据开发者提供的 V4.4.2 真实人工验收：

- “我想吃牛肉”：answerable=true，返回牛肉相关 evidence 和服务器原文回答。
- “有什么饮料？”：answerable=true，evidence 正确但只覆盖柠檬茶；grounding 正确，完整性不足。后续自动评测已观察到 Retrieval availability 与 Evidence Selection 两层的完整性损失，不只归因于单一模块。
- “可以开发票吗？”与“今天香港天气怎么样？”：answerable=false，固定拒答、空 evidence。

这些是四条人工观察，不是本轮 12 条自动评测结果。

## 已冻结的真实 End-to-End Baseline

本轮计划及完成数量：totalQueries=12，supported=6、unsupported-domain=3、external-ood=3；completedCount=12，failedCount=0。以下仅适用于当前 **21-chunk 小型知识库与 12-query 人工固定评测集**，不能推广为生产性能。

| 层次 / 指标 | 真实结果 |
| --- | --- |
| answerabilityCorrectCount / answerabilityAccuracy | 11；11/12 ≈ 0.9166666667（91.67%） |
| truePositiveCount / supportedAnswerRate | 5；5/6 ≈ 0.8333333333（83.33%） |
| trueNegativeCount / rejectionRate | 6；6/6 = 1（100%） |
| unsupportedDomainRejectionRate | 3/3 = 100% |
| externalOodRejectionRate | 3/3 = 100% |
| falsePositiveQueries | [] |
| falseNegativeQueries | 仅“酸梅汤是什么味道？” |
| retrievalHitCount / retrievalHitRate | 6；6/6 = 100% |
| averageRetrievalRecallAt3 | ≈ 0.8083333333（80.83%） |
| evidenceHitCount / evidenceHitRate | 5；5/6 ≈ 83.33% |
| averageEvidencePrecision | 0.75（75%） |
| averageEvidenceRecall | ≈ 0.5583333333（55.83%） |
| serverGroundingPassCount / serverGroundingPassRate | 12；12/12 = 100% |

本轮没有 expected=false、actual=true 的 False Positive。这是本评测集的事实，不代表任意无答案 Query 都能正确拒答。

### 唯一 False Negative：酸梅汤是什么味道？

expectedAnswerable=true，actualAnswerable=false；但 retrievalHit=true、retrievalRecallAt3=1，正确知识 `dish-8-taste` 已进入本次实际 Top-3。

```text
Query → Retriever 已找到 dish-8-taste
      → Generation / evidence selection 未选择正确 evidence
      → answerable=false
```

因此这是 **Evidence Selection / Answerability False Negative**，不是 Retrieval miss。该诊断定位输出环节，并不推断模型内部产生拒答的具体原因。

### 饮料问题：保留完整性不足的观察

人工调用曾仅选择 `dish-4-ingredients`。自动评测进一步确认：**饮料问题同时观察到 Retrieval availability 和 Evidence Selection 两层的 completeness 损失。**

项目文档与 fixtures 中未找到保存的完整真实逐条输出，因此此处不编造具体 `retrievalMissKnowledgeIds` 或 `evidenceSelectionMissKnowledgeIds`；也不拿人工单次调用的选择 ID 冒充自动评测明细。未来如补存真实输出，应按该输出逐项补充，不能凭印象猜测。

### 四层工程结论

1. **Retrieval Availability**：相关知识是否进入 Top-3。Hit=100%，平均 Recall≈80.83%；每条 supported 至少召回一条，不代表全部 relevant 都进入 Top-3，更不代表 Retriever 完美。
2. **Evidence Selection**：模型是否选择正确证据。Hit≈83.33%，平均 Recall≈55.83%，相较 Retrieval 仍明显损失；遗漏不仅来自检索层。
3. **Answerability**：模型是否判断上下文足够回答。Accuracy≈91.67%，无答案拒答率100%；唯一错误是 supported False Negative。
4. **Server Grounding**：最终答案是否遵守可信证据渲染。12/12通过；true 的答案与 evidence 原文拼接一致，false 使用固定文案且 IDs/evidence 全空。

Server Grounding 结果支持本轮工程输出没有绕过 trusted evidence rendering，但不保证证据语义相关、完整或 answerability 正确，也不是整个 RAG 的 formal correctness guarantee。

**保留该真实 baseline。** 本次不因酸梅汤拒答、饮料完整性或55.83%的 Evidence Recall 调整 Prompt、Top-K、标签、数据集或知识源。后续任何优化必须与该 baseline 对比，才能判断是否有效。

## 固定 Dataset

唯一人工维护文件为 `uniCloud-aliyun/cloudfunctions/rag/resources/answer-eval.json`，直接随 rag 部署。它独立于历史 Retrieval / Robustness 评测集，包含版本和冻结知识源 SHA-256。加载时校验部署源哈希、Query 唯一性、6/3/3 数量、标签类型与真实知识 ID。

| id | kind | Query | relevantKnowledgeIds |
| --- | --- | --- | --- |
| clean | supported | 有什么比较清爽的？ | dish-3-taste、dish-7-taste、dish-4-taste |
| beef | supported | 我想吃牛肉 | dish-2-description、dish-2-ingredients、dish-6-description、dish-6-ingredients |
| drinks | supported | 有什么饮料？ | dish-4-taste、dish-4-ingredients、dish-8-taste、dish-8-ingredients |
| cucumber-texture | supported | 拍黄瓜是什么口感？ | dish-7-taste |
| plum-taste | supported | 酸梅汤是什么味道？ | dish-8-taste |
| peppers | supported | 哪些菜里有辣椒？ | dish-5-description、dish-5-ingredients、dish-6-description、dish-6-ingredients、dish-7-ingredients |
| invoice | unsupported-domain | 可以开发票吗？ | 无此字段 |
| reservation | unsupported-domain | 可以订座吗？ | 无此字段 |
| opening-hours | unsupported-domain | 你们几点营业？ | 无此字段 |
| weather | external-ood | 今天香港天气怎么样？ | 无此字段 |
| python | external-ood | Python 怎么安装？ | 无此字段 |
| arithmetic | external-ood | 2 加 2 等于多少？ | 无此字段 |

supported 的 expectedAnswerable=true，其余为 false。所有标签已对照 `docs/rag/knowledge-source.json`，未改动或扩大。辣椒的五条分别有辣椒、干辣椒、青椒、红椒的文字依据。“清爽”采用用户指定的语义标签，不能由此将柠檬茶知识原文改写为清爽。

## 执行链路和冻结范围

```text
rag-answer-eval-admin（仅 server 来源，参数 {}）
 → rag.evaluateAnswers()（仅 function/server 来源）
 → answer-evaluator.js 读取固定12条
 → 每条调用正式共享 answerQuery(query, options)
 → Query Embedding → 原 Exact Cosine Top-3 → Live dishes
 → 正式 Qwen evidence selection → 原服务器验证和原文渲染
 → 本次实际检索诊断 + generation → 纯评估计分
 → 汇总与逐条明细
```

`answerQuery()` 原本就返回内部诊断，故无需增加 includeDiagnostics 或修改 generator。正式 `rag.answer(query)` 继续使用原白名单返回，不加入标签、similarity 或评测字段。testRagGeneration、Retriever、Query 适配、Prompt、合同、渲染、Knowledge Source、Indexer、knowledge_chunks 和前端保持不变；新增冻结 fixture 检查 Answer 管线，原 frozen fixtures 不改。

没有额外 Judge、NLI、threshold、评分用 Embedding、Prompt 调优或检索优化。正式 evaluator 默认调用真实 answerQuery；依赖注入只用于本地测试，管理入口不转发外部依赖、数据集或 event。

## 每条明细

每条返回 id、query、kind、expectedAnswerable、actualAnswerable、answerabilityCorrect、answer、selectedKnowledgeIds、selectedDishIds、evidence、retrievedKnowledgeIds、serverGroundingPass。evidence 仅保留 knowledgeId / dishId / scope / type / title / text，不展开原始对象。

supported 另有相关标签、选中相关/无关 ID、遗漏相关 ID、Evidence 指标与 Retrieval 指标。所有计分按不同 ID 计数，重复不增加得分。

### Answerability

- answerabilityCorrect：实际 boolean 与人工 expected 相等。
- truePositiveCount / supportedAnswerRate：supported 回答 true 的数量 / supported 数量。
- trueNegativeCount / rejectionRate：expected=false 且回答 false 的数量 / 所有 expected=false 数量。
- unsupportedDomainRejectionRate、externalOodRejectionRate：各无答案分组的拒答比例。
- answerabilityAccuracy：正确数量 / 已完成 Query 数量。
- falsePositiveQueries：expected=false、actual=true；falseNegativeQueries：expected=true、actual=false。均返回 id 和 query。

回答 true 不代表选中了正确 evidence，所以 Answerability 与 Evidence Selection 分开统计。

### Evidence Selection（仅 supported）

- evidenceHit：至少选择一个 relevant ID。
- evidencePrecision：选中相关 ID 数 / 所选不同 ID 数；空选择为 0。
- evidenceRecall：选中相关 ID 数 / 全部人工 relevant ID 数。
- evidenceHitCount / evidenceHitRate、averageEvidencePrecision、averageEvidenceRecall：supported 分组计数和算术平均。正常拒答的 supported 仍计入，Evidence 指标为 0。

这是端到端 evidence recall，即使相关知识没进入 Top-3，也仍计入 missedRelevantKnowledgeIds。Top-3 对 4 或 5 个 relevant 的 Query 有召回上限；不能把该指标误认为仅衡量模型选择。

### Retrieval Availability

读取同一次 answerQuery 的真实 Top-3，不为评估额外检索：

- retrievedRelevantKnowledgeIds：Top-3 与 relevant 的交集。
- retrievalHit：交集非空。
- retrievalRecallAt3：交集数量 / 全部 relevant 数量。
- 汇总 retrievalHitCount / retrievalHitRate / averageRetrievalRecallAt3。
- retrievalMissKnowledgeIds：relevant 中未进入 Top-3 的 ID。
- evidenceSelectionMissKnowledgeIds：已进入 Top-3、却未被模型选中的 relevant ID。

这两类 missed 分开列出，可分析“饮料”完整性问题。运行期间实时菜品状态可能影响选择，不能仅由 miss 自动推断模型失误或优化排名。

### Server Grounding Structure

true 时检查：选中非空、ID 去重保序、evidence 与选中 ID 一致、证据六字段与本次 Retrieval 原文一致、菜品关联一致，以及 `answer === evidence.map(e => e.text).join('\n')`。

false 时检查：固定文案“当前提供的知识不足以回答这个问题。”，且 knowledge IDs、dish IDs、evidence 全空。

汇总 serverGroundingPassCount / serverGroundingPassRate。这仅验证工程结构，**不证明 evidence 与 Query 语义相关，也不证明完整性或 formal correctness**。

## 失败与分母

API、配置、数据库错误或无法读取的诊断格式：该条 status=failed，actualAnswerable / answerabilityCorrect / serverGroundingPass=null，不将执行失败伪装成正常拒答、FP、FN 或 TN。只返回固定安全错误，不输出原始异常。

- totalQueries、supportedCount、unsupportedDomainCount、externalOodCount 保持计划数量 12 / 6 / 3 / 3。
- completedCount、failedCount、evaluatedSupportedCount、evaluatedUnsupportedDomainCount、evaluatedExternalOodCount 明确展示实际分母。
- 指标仅在已完成的对应分组计算；空分母返回 null。部分失败的结果不可当作完整基准比较。
- 有执行失败则整轮 errCode=ANSWER_EVAL_PARTIAL_FAILED；可读结果存在结构异常则为 ANSWER_EVAL_STRUCTURE_FAILED。
- 普通模型 FP/FN 属于有效评测结果，不是执行错误；errCode=0 不表示准确率 100%。

## 并发、耗时与运行步骤

最多并发 **3** 个完整 Query，按原数组下标保存结果，完成顺序不会改变 Query 映射。正常整轮为 12 次 Embedding + 12 次 Generation，不重试、不调用第二个模型评分。

rag 与新 admin 的 timeout 设置为 **240 秒**：12 条按3并发约4批，每条现有 Embedding / Generation 超时预算约15+30秒，外加连接和数据库耗时，因此原120秒对慢请求可能不足。这里只提高管理评测所需的函数运行上限，正式接口单次HTTP超时及行为不变。240秒不保证平台或网络一定完成；平台硬超时/调用失败不算完整报告，不补造指标。并发额度由实际服务空间和模型配额决定。

1. 执行本地下方检查，不运行 Indexer，不初始化或修改数据库。
2. 上传更新后的 rag，包含 answer-evaluator.js 和 resources/answer-eval.json，并确认平台应用 package.json 的240秒超时设置。
3. 保持 rag 已验证的 DASHSCOPE_API_KEY、LLM_BASE_URL、EMBEDDING_MODEL、EMBEDDING_DIMENSION、RAG_LLM_MODEL 环境变量，无需新变量。
4. 上传新 rag-answer-eval-admin，同样确认240秒超时；它不存密钥，不配置 URL 化、定时器或微信入口。
5. 在 HBuilderX 对 **rag-answer-eval-admin** 使用空参数 `{}`，“上传并运行云函数”。不要调用索引入口，也不需要逐条手工调用 rag-answer-admin。
6. 检查 totalQueries=12、分组6/3/3，completedCount=12、failedCount=0；再阅读整体指标和queries中的证据、miss及FP/FN。结构失败或执行失败需单独排查。
7. 保存实际返回作为真实记录；该步骤已由开发者真实完成；本次收尾没有重复执行。后续按需复验时，固定标签评测仍可能因模型选择与实时菜品变化而波动，不承诺每次数字完全一致。

## 本地验证

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```

新增测试涵盖固定集、标签、指标、结构异常、错误分母、并发映射、安全白名单，以及使用模拟 HTTP / DB 贯穿真正共享 Answer 链路。原正式接口、固定 Generation、Retriever、历史评测和知识源冻结测试继续执行。

本阶段不自动运行真实评测，不进入 V4.4.4，不根据本地模拟结果修改模型 Prompt 或排名。
