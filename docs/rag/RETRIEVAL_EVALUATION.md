# V4.3 收尾：Retrieval Baseline 与 Answerability Evaluation

## Baseline V1：真实云端验证结果

本报告依据开发者于 2026-09-22 收尾时提供的真实云端验证结果固化：V4.3.1 单 Query、19 条 Baseline Evaluation 和 24 条 Robustness Evaluation 均已验证。结果不是本地模拟值；本次收尾只运行本地检查，没有重新调用远程模型。

Retriever Baseline V1 保持冻结。V4.3.2 最初使用 10 条 Query，V4.3.3 扩展到 19 条；下面主要指标明确对应已完成的 **19 条**评测。历史 10 条 fixture 与所有评测数据定义均不修改。

| 配置 | Baseline V1 |
| --- | --- |
| embeddingModel | qwen3.7-text-embedding-flash |
| embeddingDimension | 512 |
| knowledge chunks | 21 条 verified 知识 |
| search | exact cosine similarity |
| topK | 3 |
| threshold / reranker | 均无 |
| keyword boost / BM25 / Hybrid Search / type boost / dish 去重 | 均无 |
| query rewrite / intent router / answerability classifier | 均无 |

| 真实指标 | 结果 |
| --- | --- |
| totalQueries | 19 |
| evaluatedRecallQueries | 7 |
| averageRecallAt3 | 0.80 |
| averageCoverageAt3 | 约 0.952381 |
| hitAt3Count | 7 |
| Hit@3 比例 | 7 / 7 = 100% |

当 relevant 数量超过 3，Recall@3 存在理论上限：4 个 relevant 时为 3/4 = 0.75，5 个 relevant 时为 3/5 = 0.60。本次 7 个 labeled Query 中有 6 个达到各自在 Top-3 下的理论最大 Recall。唯一明显未达到的是“有什么饮料？”，实际 Recall@3 = 0.50，理论最大值为 0.75。

本地历史快照 `tests/fixtures/rag-retrieval-baseline-v1.json` 保存原 10 条评测定义、开发者报告的上述指标及 Retriever 文件 SHA-256。它只用于历史回归校验，不是另一份需要同步维护的部署评测集，也不伪造未提供的逐条云端排名。测试锁定 Retriever 字节及原 7 条 labeled / 1 条 exploratory 的内容和标签。

### V4.3.1 单 Query：真实云端验证结果

“有什么比较清爽的？”真实 Top-3：

| rank | knowledgeId | 标题 | similarity |
| --- | --- | --- | --- |
| 1 | dish-3-taste | 鲜蔬沙拉：风味或口感 | 0.576992 |
| 2 | dish-7-taste | 拍黄瓜：风味或口感 | 0.545429 |
| 3 | dish-4-taste | 柠檬茶：风味或口感 | 0.410384 |

结果来自 Query Embedding 与 21 条知识的 Exact Cosine Search，没有关键词硬编码、taste boost、人工调整排名、reranker 或 threshold。similarity 不是概率或正确率。

上一轮“今天香港天气怎么样？”真实 Top-1 similarity 约为 **0.4166**。一个有效相关结果的分数 0.410384 低于这个领域外问题的最高分，已经出现分数重叠。因此，当前证据不支持直接使用简单固定 threshold 作为唯一拒答机制。这是观察结论，没有据此加入过滤条件或调整排名。similarity 是余弦相似度，不是概率或正确率。

## 扩展评测集：Evaluation V2

当前唯一用于执行的评测集为 `uniCloud-aliyun/cloudfunctions/rag/resources/retrieval-eval.json`，随 rag 部署，本地测试直接读取。`evaluationVersion: 2` 表示评测集与报告字段扩展；`retrieverBaselineVersion: 1` 表示检索算法仍冻结在 V1。

共 **19 条**：7 labeled、1 exploratory、6 external-ood、5 unsupported-domain。原 7 条 labeled 和 1 条 exploratory 的 Query、标签和依据全部保持不变；原 weather / Python 两条仅将 kind 明确为 external-ood。两类无答案都使用空 `relevantKnowledgeIds: []`，不视为有答案问题。

评测集保留冻结 Knowledge Source 的 SHA-256、预期 21 条候选、模型、512 维和 Top-3。执行前检查部署知识副本 hash、标签 ID、云端候选 ID/标题/正文/类型/范围/菜品关联与冻结源一致，避免混用不同语料。没有改动源知识或数据库。

### 保持不变的领域内 Query

| Query | relevantKnowledgeIds / 用途 |
| --- | --- |
| 我想吃牛肉 | dish-2-description、dish-2-ingredients、dish-6-description、dish-6-ingredients |
| 有什么鸡肉？ | dish-1-description、dish-1-ingredients、dish-5-description、dish-5-ingredients |
| 想吃酸甜的 | dish-2-taste、dish-8-taste |
| 哪些菜有辣椒？ | dish-5-description、dish-5-ingredients、dish-6-description、dish-6-ingredients、dish-7-ingredients |
| 有什么饮料？ | dish-4-taste、dish-4-ingredients、dish-8-taste、dish-8-ingredients |
| 有什么比较清爽的？ | dish-3-taste、dish-4-taste、dish-7-taste |
| 我想吃点爽脆的 | dish-7-taste |
| 想看看主要配料是什么 | exploratory：无具体菜品目标，仅观察，不计算 Recall/Hit/Coverage |

全部 ID 已核对真实冻结源。没有删除用户给出的候选 ID；辣椒问题补充明确写有辣椒、青椒或红椒的介绍/配料记录，不以花椒单独推定有辣椒。饮料在当前源中只有 taste / ingredients，没有 description，故不虚构对应 ID。

“清爽”采用用户提供的语义相关标签。只有鲜蔬沙拉原文明确写“清爽”；柠檬茶写“柠檬香气”，拍黄瓜写“爽脆”。后二者是人工偏好相关判断，不能据此改写知识事实或宣称原文保证清爽。需要调整这类标签时应显式更新评测版本、记录理由，不能为了提高分数悄悄调整。

### external-ood（6 条）

完全与餐厅知识无关，仅用于观察：

1. 今天香港天气怎么样？
2. Python 怎么安装？
3. 2 加 2 等于多少？
4. 什么是光合作用？
5. iPhone 怎么截屏？
6. 给我写一首短诗。

### unsupported-domain（5 条）

属于餐厅场景，但当前 Knowledge Source 没有支持答案，不设置人工相关标签：

1. 你们几点营业？
2. 可以开发票吗？
3. 餐厅有停车位吗？
4. 可以外送吗？
5. 支持什么付款方式？

## 指标定义

仅对 7 个 labeled Query 计算：

```text
hits = Top-3 命中的不同 relevant knowledgeId 数量
Recall@3 = hits / relevantCount
coverageAt3 = hits / min(relevantCount, 3)
Hit@3 = hits > 0
averageRecallAt3 = labeled Query 的 Recall@3 算术平均
averageCoverageAt3 = labeled Query 的 coverageAt3 算术平均
```

Coverage 衡量 Top-3 能容纳的相关结果是否找满，是辅助指标，**不替代或修改 Recall@3**。例如 4 个 relevant 命中 3 个，Recall = 0.75、Coverage = 1；5 个 relevant 命中 3 个，Recall = 0.60、Coverage = 1；只有 2 个 relevant 命中 1 个，两者均为 0.5。

同时保留 `expectedRelevantCount`、`retrievedRelevantIds`、`missedRelevantIds`。重复 relevant ID 或检索 ID 会明确报错。Top-3 不足三条时按实际命中计算，Coverage 分母仍为 min(relevantCount, 3)，不会按实际返回数量缩小分母，也不补造结果。

exploratory 的 Recall/Hit/Coverage 返回 null。external-ood 与 unsupported-domain 不计算这些指标，也不把无答案问题按 0 分混入平均值。

## similarity 分布与报告结构

- `queries`：原 7 条 labeled + 1 条 exploratory 的明细，每条包含 `top3`（rank、knowledgeId、title、similarity）。
- labeled 明细增加 `top1Similarity`、`thirdSimilarity`、`lowestRelevantSimilarityInTop3`。第三名不存在或无相关命中时对应值为 null。
- `labeled`：仅 labeled Query 的 top1 分数汇总。
- `externalOod`、`unsupportedDomain`：两组分别汇总，分别在各自的 `queries` 内保存 query、kind、top1Similarity、top3Similarities、top3KnowledgeIds、top3Titles 和 top3 明细。
- 三个分组均有 `count`、`scoredCount`、`minTop1Similarity`、`maxTop1Similarity`、`averageTop1Similarity`。无结果的 top1 为 null，不伪造成 0；平均值只计算存在 top1 的 Query，以 scoredCount 标明分母；没有分数时 min/max/average 均为 null。正式成功评测有 21 条有效候选，通常每条都会有 Top-3。
- 顶层增加 `averageCoverageAt3`，仍保留原 `averageRecallAt3`、`evaluatedRecallQueries` 和 `hitAt3Count`。

Evaluation V2 用上述两个独立无答案分组替代 V1 的 `outOfDomain` 数组。保留 Retriever 已输出的六位小数，包括负分，不重新归一化，不把 similarity 当作概率。比较三组分数分布的目的仅是积累观察数据，不自动产生 threshold。

## 实现边界

- `retriever.js` 本阶段完全不改。原 cosine、Exact Search、完整精度降序、knowledgeId 次级排序和 Top-3 保持一致，没有任何 boost 或 threshold。
- `evaluator.js` 只读取 `knowledge_chunks` 一份候选快照；relevant 标签不传入排名函数，只在排名完成后计分。
- 一次 `/embeddings` 请求发送固定 19 个 query，每个返回独立的 512 维向量；未改变模型或单条诊断请求。响应按 index 映射，拒绝缺失/重复/越界索引、非法维度、非有限数字及零向量。
- 任一请求、候选或排名异常会返回非零 errCode，不生成部分成功的总体平均值。没有数据库写入、自动重试或远程结果历史。
- `rag.evaluateRetrieval()` 仅允许平台 function/server 来源，不接受客户端 query 或标签；`rag-eval-admin` 只接受平台 server 来源，不能用 event 参数伪造权限。
- 所有页面都没有评测入口。`testRetrieval()`、`testEmbedding()`、`testBatchEmbedding()` 继续保留。
- 不调用 Qwen3.8-Flash，不生成回答，不修改 Indexer、AI 推荐或知识数据。

## Baseline 真实评测复现步骤（已验证，按需手动运行）

1. 保持现有服务空间和 21 条正式 knowledge_chunks，不重新索引、不初始化任何 collection。
2. 本地运行 `pnpm run rag:check-source`，确认知识源与部署副本一致；运行下方测试。
3. HBuilderX 中右键 `uniCloud-aliyun/cloudfunctions/rag` → 上传部署。确认包含更新后的 evaluator 和 `resources/retrieval-eval.json`；保留未改动的 retriever 和知识资源。
4. 确认 rag 远程环境变量沿用已验证值：DASHSCOPE_API_KEY、北京 LLM_BASE_URL、EMBEDDING_MODEL=qwen3.7-text-embedding-flash、EMBEDDING_DIMENSION=512。不需要修改真实密钥或增加 LLM_MODEL。
5. 确认/重新上传部署现有 `rag-eval-admin`，其管理入口代码无需改动。保持 120 秒超时，不配置 URL 化或定时器。它不需要保存 API Key。
6. 在 **rag-eval-admin** 右键“配置运行测试参数”，填写 `{}`，选择“上传并运行云函数”。不要运行 rag-index-admin，不从微信页面调用。
7. 成功应返回 `errCode: 0`、`evaluationVersion: 2`、`retrieverBaselineVersion: 1`、`totalQueries: 19`、`evaluatedRecallQueries: 7`、`exploratoryQueries: 1`、`totalCandidates: 21`、`topK: 3`、`externalOod.count: 6`、`unsupportedDomain.count: 5`，以及真实指标和分数组合。
8. 保存完整返回 JSON、运行日期与评测版本。新一轮 Recall/Coverage 及无答案分布以这次返回为准；不能预填历史指标或本地模拟分数。输出不含完整向量和密钥，无数据库写入。

非零 errCode 或超时表示本轮没有完整成功，应检查后手动重试。每次真实执行会重新消耗 19 条 query 的 Embedding 用量。本次开发没有触发真实评测。

## 本地验证

```sh
node --test tests/rag-evaluator.test.cjs tests/rag-retriever.test.cjs
pnpm run build:mp-weixin
git diff --check
```

本地使用模拟 API 和只读内存候选，不使用真实密钥、不调用远程模型。测试覆盖原 Recall/Hit、Coverage、三组分数汇总、无答案排除、Dataset kind、索引映射、重复 ID 防御、无向量返回及 Baseline 文件/标签冻结。

## V4.3.4 Answerability Robustness Evaluation

### Baseline similarity 分布：真实云端验证结果

开发者已完成 V4.3.3 的 19 条 Baseline Evaluation 真实执行。以下数值由开发者提供，不来自本地模拟；分布数值均为约值：

- averageRecallAt3 ≈ 0.80
- averageCoverageAt3 ≈ 0.952381
- Hit@3 = 7/7 = 100%

| Baseline 分组 | min Top-1 | max Top-1 | average Top-1 |
| --- | --- | --- | --- |
| labeled | 0.445395 | 0.680963 | 0.559883 |
| external OOD | 0.256816 | 0.416670 | 0.334321 |
| unsupported-domain | 0.245996 | 0.384954 | 0.308334 |

这些较小样本的 Top-1 极值存在约 `0.445395 - 0.416670 = 0.028725` 的候选间隔。前文有效 Top-3 第三名 0.410384 与天气 Top-1 约 0.4166 的重叠观察仍保留：它与当前 Top-1 分组统计不是同一比较口径，不能混用。本阶段仅扩大样本验证间隔是否稳定，不据此设置业务 threshold。

### Robustness：真实云端验证结果

开发者已完成 24 条独立 Robustness Evaluation，其中 1 条 supported-exploratory 不参与主要统计。以下仅固化已提供的真实汇总值，没有补造逐条排名或 overlap Query 明细。

| supported-paraphrase 指标 | 真实结果 |
| --- | --- |
| count / scoredCount | 11 / 11 |
| minTop1Similarity | 0.373664 |
| maxTop1Similarity | 0.712540 |
| averageTop1Similarity | 约 0.561436 |
| top1RelevantCount | 11 |
| hitAt3Count | 11 |
| averageRecallAt3 | 约 0.865152 |
| averageCoverageAt3 | 约 0.969697 |
| Top-1 relevant 比例 | 11 / 11 = 100% |
| Hit@3 比例 | 11 / 11 = 100% |

| unsupported-domain-hard 指标 | 真实结果 |
| --- | --- |
| count / scoredCount | 12 / 12 |
| minTop1Similarity | 0.247779 |
| maxTop1Similarity | 0.405820 |
| averageTop1Similarity | 约 0.302639 |

真实 Separation Analysis：

```text
supportedMinTop1 = 0.373664
unsupportedMaxTop1 = 0.405820
separationGap = 0.373664 - 0.405820 = -0.032156
hasOverlap = true
```

Robustness Evaluation 中，supported 与 unsupported-domain-hard 的 Top-1 cosine similarity 已发生真实重叠。不存在一个简单固定 cosine threshold，可以在当前真实评测数据上完美区分“知识库有答案”和“知识库没有答案”。代码未据此加入 threshold 或其他解决方案。

原 `retrieval-eval.json`、`rag-retrieval-baseline-v1.json`、Baseline evaluator、Retriever、知识源和数据库定义保持不变。

### 工程结论：Retrieval Quality 与 Answerability Detection

**Retrieval Quality** 关注“知识库中哪些知识最相关”。当前 11 条 supported paraphrase 的 Top-1 relevant 和 Hit@3 均为 11/11，averageCoverageAt3 约 96.97%，说明纯向量 Retriever 在这个人工评测集上的相关知识排序表现良好。

**Answerability Detection** 关注“知识库是否真的包含足以回答用户问题的信息”。supported Top-1 低至 0.373664，unsupported hard Top-1 高至 0.405820，分数重叠说明固定 cosine threshold 不足以独立承担可靠的 answerability / rejection 判断。

cosine similarity 仍然适合当前项目的相关知识排序，但它的绝对分数不能单独作为稳定的“知识库是否有答案”判定标准。这不是“cosine similarity 没用”的结论，也不代表已经实现拒答功能。

这些结果来自当前 **21-chunk 小型知识库与人工评测集**，不能直接推广为大规模生产系统性能。本地模拟测试仅验证代码行为，与以上真实云端指标分别记录。

### Future Work / 后续可研究

可研究 Reranker、Hybrid Retrieval / BM25、Intent / capability routing、Answerability classifier，以及更大规模 Evaluation Dataset。这些仅是未来研究方向，本阶段均未实现，也不预先宣称一定优于当前方案。当前没有完成最终 RAG 回答链路、RAG Prompt 或正式用户问答页面，本次收尾不进入 V4.4。

### 独立固定集

新增 `uniCloud-aliyun/cloudfunctions/rag/resources/retrieval-robustness-eval.json`，`robustnessVersion: 1`、`retrieverBaselineVersion: 1`。本集共 **24 条**：11 supported-paraphrase、1 supported-exploratory、12 unsupported-domain-hard。没有重复增加 external OOD。每条包含人工标签依据；加载时校验真实 knowledgeId、源知识 SHA-256、模型、512 维、Top-3 及分组数量。

| Query | kind | relevantKnowledgeIds |
| --- | --- | --- |
| 有没有牛肉做的东西？ | supported-paraphrase | dish-2-description、dish-2-ingredients、dish-6-description、dish-6-ingredients |
| 想来点鸡肉做的 | supported-paraphrase | dish-1-description、dish-1-ingredients、dish-5-description、dish-5-ingredients |
| 想吃点酸酸甜甜的 | supported-paraphrase | dish-2-taste、dish-8-taste |
| 有没有喝的东西？ | supported-paraphrase | dish-4-taste、dish-4-ingredients、dish-8-taste、dish-8-ingredients |
| 想喝点有柠檬味的 | supported-paraphrase | dish-4-taste |
| 有没有脆脆的东西？ | supported-paraphrase | dish-7-taste |
| 有没有用乌梅做的？ | supported-paraphrase | dish-8-ingredients |
| 什么里面有番茄？ | supported-paraphrase | dish-2-description、dish-2-ingredients、dish-3-ingredients |
| 哪些东西放了辣椒？ | supported-paraphrase | dish-5-description、dish-5-ingredients、dish-6-description、dish-6-ingredients、dish-7-ingredients |
| 有没有带米饭的？ | supported-paraphrase | dish-1-description、dish-1-ingredients |
| 我想找点清爽口感的 | supported-paraphrase | dish-3-taste、dish-4-taste、dish-7-taste |
| 想吃点爽口的 | supported-exploratory | 空，不参与主要统计 |

标签说明：

- “爽口”没有冻结的明确含义，不能直接等同于清爽、爽脆或酸甜，因此保守转为 exploratory，不参与 supported 分布、Recall/Coverage、Separation 或 Overlap。
- 番茄 Query 补充 `dish-3-ingredients`：鲜蔬沙拉主要配料确实包含番茄。沿用材料问题以 description / ingredients 标注的规则，不因为 taste 重复提及汤底就扩大标签。
- “清爽”沿用原人工语义标签，未宣称柠檬茶或拍黄瓜原文写有清爽，也没有修改历史标签。

12 条 unsupported-domain-hard 均无 relevant 标签：

1. 可以订座吗？
2. 有包间吗？
3. 能打包带走吗？
4. 可以带宠物进来吗？
5. 有儿童座椅吗？
6. 店里有 Wi-Fi 吗？
7. 你们几点打烊？
8. 周末几点开门？
9. 可以用支付宝吗？
10. 能刷信用卡吗？
11. 可以提前预约菜吗？
12. 有最低消费吗？

这些是餐厅场景问题，但 21 条知识没有对应答案；不是在评测是否属于餐厅领域。

### 独立评估流程

`rag-robustness-eval-admin → rag.evaluateRobustness() → robustness-evaluator.js`

1. 读取独立固定集与冻结知识部署资源，校验来源。
2. 只读一份 21 条 verified 云端知识快照，确认内容与源一致，复用 Retriever 校验向量。
3. 使用原环境配置，将 24 条 Query 分为 **两批，每批 12 条**，调用 `/embeddings`。每批 index 从 0 开始，响应允许乱序，必须唯一且完整覆盖当前批次；校验 512 维有限数字和非零向量。
4. 每个 Query 复用原 `rankCandidates()`，不复制 cosine 或排序逻辑，不传 relevant 标签给 Retriever。
5. 排名完成后计算指标，只返回分数、ID、标题和统计，不返回完整向量。

任一批或候选校验失败均返回安全错误，不把部分结果当作整套成功。不记录请求头、密钥或原始异常；不写数据库，不自动重试。仅使用项目已有依赖和 Node 内置模块。

### 输出与 Separation Analysis

`supportedParaphrase`：count、scoredCount、min/max/averageTop1Similarity、top1RelevantCount、hitAt3Count、averageRecallAt3、averageCoverageAt3、queries。

每条 supported 明细包括 query、relevantKnowledgeIds、top1KnowledgeId、top1Title、top1Similarity、top1IsRelevant、top3、hits、recallAt3、coverageAt3、hitAt3、命中和遗漏 ID。**top1IsRelevant 单独统计**：高分 Top-1 若不属于人工相关标签，就是错误首位结果，不能把高分本身当成 answerability 成功。不会因此将它从分数分布中悄悄剔除。

`unsupportedDomainHard`：count、scoredCount、min/max/averageTop1Similarity、queries。每条记录 query、Top-1 ID/标题/分数、Top-3 ID/分数及精简明细，不参与 Recall/Coverage 平均。

`supportedExploratory`：仅保存观察明细，Recall/Coverage/Hit 为 null，不进入主要分组。

```text
supportedMinTop1 = 11 条 supported-paraphrase 的最低 Top-1 分数
unsupportedMaxTop1 = 12 条 unsupported-domain-hard 的最高 Top-1 分数
separationGap = supportedMinTop1 - unsupportedMaxTop1
hasOverlap = separationGap <= 0
```

`overlapAnalysis` 返回以上四项，以及：

- hardNegativeQueries：unsupported Top-1 >= supportedMinTop1 的案例。
- lowScoreSupportedQueries：supported Top-1 <= unsupportedMaxTop1 的案例。
- 每个案例仅包含 query、Top-1 ID/标题/分数；supported 额外附 top1IsRelevant。
- gap > 0：仅说明当前 Dataset 仍存在分数间隔；gap <= 0（包括相等）：说明已经重叠，简单固定 threshold 无法在本集完美分离。

若任一组为空或有 Query 缺少 Top-1，gap 与 hasOverlap 返回 null，说明无法比较，不宣称不存在重叠。空分组分数汇总为 null，scoredCount 明确有效分数数量。正式成功运行有 21 条有效候选，预期每条有完整 Top-3。

以上比较只生成评估报告，不过滤返回排名、不生成建议阈值、不实施分类器或拒答逻辑。similarity 不是概率或正确率。

### Robustness 真实评测复现步骤（已验证，按需手动运行）

1. HBuilderX 上传更新后的 `rag`，确保包含 `robustness-evaluator.js`、`resources/retrieval-robustness-eval.json` 和原有资源。
2. 上传新的普通云函数 `rag-robustness-eval-admin`，保留其 120 秒超时；不配置 URL 化、定时器或微信入口。
3. 保持 rag 现有 `DASHSCOPE_API_KEY`、北京 `LLM_BASE_URL`、`EMBEDDING_MODEL=qwen3.7-text-embedding-flash`、`EMBEDDING_DIMENSION=512`。管理函数无需另存密钥。
4. 在 **rag-robustness-eval-admin** 配置运行测试参数 `{}`，执行“上传并运行云函数”。入口校验平台 server 来源，rag 方法仅允许 function/server，event 无法指定 Query 或标签。
5. 完整成功应见 `errCode: 0`、`totalQueries: 24`、`totalCandidates: 21`、`topK: 3`、`supportedParaphrase.count: 11`、`supportedExploratory.count: 1`、`unsupportedDomainHard.count: 12` 及 overlapAnalysis。
6. 保存此次完整 JSON 与日期，再人工观察结果。每次运行消耗 24 条 Query Embedding 用量；没有运行 Indexer、修改 knowledge_chunks 或调用 Qwen3.8-Flash。

原 `rag-eval-admin` 继续运行历史 Baseline Evaluation，两个入口互相独立，不共用可变标签。

### 本地回归

```sh
node --test tests/rag-robustness-evaluator.test.cjs tests/rag-evaluator.test.cjs tests/rag-retriever.test.cjs
pnpm run build:mp-weixin
git diff --check
```

`tests/fixtures/rag-robustness-frozen-files.json` 固定 9 个既有文件的 SHA-256，用来检查历史评测定义与 fixture、Baseline evaluator、Retriever、Indexer、源知识/部署副本、schema/index 没有被本阶段修改。新测试只使用模拟请求和只读候选，不是 Robustness 真实效果报告。
