# V4 RAG 菜单问答总结

## 1. V4目标

给现有微信点餐系统增加基于真实菜单知识的单轮问答能力。AI智能点餐根据预算、偏好推荐菜品；RAG菜单问答回答口味、配料、介绍等知识问题，两者页面、服务和后端职责独立。

V4主链路已完成实现、真实云端检索/生成/评测和微信开发者工具验收。本总结使用现有验收记录，不把本地mock测试当作模型真实效果，也没有在文档整理时再次调用API。

## 2. 完整RAG架构

```text
User Query（单轮文本）
    ↓
rag.answer(query)
    ↓
Query Validation（trim，1～200 Unicode字符）
    ↓
qwen3.7-text-embedding-flash
    ↓
512-d Query Embedding
    ↓
knowledge_chunks（读取verified候选）
    ↓
Exact Cosine Top-3 Retrieval
    ↓
Live Dish Facts（仅关联的实时dishes）
    ↓
qwen3.8-flash
    ↓
answerable + evidence IDs
    ↓
Server Validation（合同、ID、关联、状态）
    ↓
Trusted Evidence Lookup（本次检索快照）
    ↓
Server-rendered Grounded Answer
    ↓
WeChat Mini Program UI
```

LLM不拥有最终factual wording，只判断answerable并选择证据IDs。服务器按合法usedKnowledgeIds读取真实text，保持顺序去重后换行拼接；false固定返回“当前提供的知识不足以回答这个问题。”。正式接口不返回向量、similarity或内部诊断。`testRagGeneration()`保留固定问题诊断，与正式接口共用底层逻辑。

## 3. 知识与索引设计

Knowledge Source V1为21条人工审核知识，全部verified=true、sourceVersion=1；type仅description、taste、ingredients，scope为dish或restaurant。来源是项目菜品初始化数据与辣度常量，保留sourceFields及来源版本；不补充未经依据支持的营养、功效、过敏保证或餐厅政策。

```text
docs/rag/knowledge-source.json（唯一人工维护源）
 → uniCloud-aliyun/cloudfunctions/rag/resources/knowledge-source.json（部署副本）
 → qwen3.7-text-embedding-flash（512 dimensions）
 → knowledge_chunks（派生知识与向量索引）
```

同步脚本与SHA-256清单防止部署副本漂移。knowledgeId唯一索引标识记录；sourceVersion、contentHash、embeddingModel、embeddingDimension相同则skip，变化则重建。每批最多10条，只生成需要insert/update的向量；按上游item.index映射并校验512个有限数字，不依赖返回数组顺序。

真实索引首次inserted=21，第二次skipped=21，验证了幂等性。部分数据库写入失败计入failed；孤儿ID只报告，不自动删除。人工源与embedding index职责不同：后续文本变更先审核源文件，再同步和重新索引，不能反过来手改向量库作为知识源。

价格、status、sales不写入长期知识正文，实时业务字段继续由dishes提供。详见 [知识审核](REVIEW.md)、[索引结构](KNOWLEDGE_CHUNKS.md)、[索引流程](INDEXING.md)。

## 4. 为什么最终不让模型自由回答

以下演进来自真实远程测试，是V4的关键工程决策：

| 阶段 | 设计 | 真实发现 |
| --- | --- | --- |
| V4.4.1 | LLM自由生成answer，服务器校验JSON与引用ID | 出现上下文未明确支持的“解腻”等扩写 |
| V4.4.1a | 加强Prompt，加入claim-level evidence references | claims引用可以合法，但自由answer仍出现claims之外事实 |
| V4.4.1b | Server从通过校验的claims.text拼接answer | claim.text本身将“具有柠檬香气”扩写为“具有清爽的柠檬香气” |
| V4.4.1c | LLM只选择evidence IDs，Server校验并使用真实原文 | 真实复验恢复为“柠檬茶，项目描述为具有柠檬香气。” |

最终设计：

```text
LLM selects evidence IDs
 → Server validates IDs
 → Server reads trusted evidence
 → Server renders factual answer
```

把factual wording的信任边界移到Server + Trusted Evidence，关闭模型自由事实措辞进入最终输出的路径。代价是答案更接近资料原文，表达不如自由生成灵活。

这没有彻底解决hallucination或获得formal correctness：模型仍可能选错合法证据、漏选或误判answerable，知识源本身也依赖人工审核质量。引用合法、措辞可追溯、语义相关和答案完整是不同问题。详见 [Generation真实演进](GENERATION_TEST.md)。

## 5. Retrieval Evaluation的意义

基线固定为21 chunks、512维、Exact Search、Cosine Similarity、Top-K=3；分数相同按knowledgeId排序，无threshold、reranker、BM25/Hybrid Search、type boost、query rewrite或dish去重。Top-K=3是当前实验设置，不是普适最优值。

V4.3把检索指标与无答案问题分布分开观察。真实Robustness结果：supported最低Top-1为0.373664，unsupported最高为0.405820，separationGap=-0.032156，已经发生重叠。

因此similarity用于相关性排序；在当前测试集上，单一固定阈值不能完美分开有答案与无答案问题，也不能单独承担稳定Answerability判断。这不是证明所有未来阈值策略都无效，而是本项目没有足够证据将其作为唯一拒答机制。

历史Retrieval Baseline平均Recall@3约0.80、Coverage@3约0.952381、Hit@3=7/7；这些来自另一套检索评测，不应与下面12-query端到端指标混算。完整数据与定义见 [RETRIEVAL_EVALUATION.md](RETRIEVAL_EVALUATION.md)。

## 6. 真实End-to-End Baseline

12条固定Query：6 supported、3 unsupported-domain、3 external-ood。completedCount=12，failedCount=0。下表来自真实云端Evaluation：

| 指标 | 结果 |
| --- | --- |
| Answerability Accuracy | 91.67%（11/12） |
| Supported Answer Rate | 83.33%（5/6） |
| Unsupported Rejection | 100%（6/6） |
| Retrieval Hit Rate | 100%（6/6 supported） |
| Average Retrieval Recall@3 | ≈80.83% |
| Evidence Hit Rate | 83.33%（5/6 supported） |
| Average Evidence Precision | 75% |
| Average Evidence Recall | ≈55.83% |
| Server Grounding Pass | 100%（12/12） |

这只适用于当前21-chunk知识库与人工固定12-query评测集，不是生产准确率。没有False Positive，但有1个False Negative。Grounding结构通过与Answerability正确率应分别解释。

四层观察：

- Retrieval Availability：相关ID是否进入本次Top-3。
- Evidence Selection：模型是否选择相关ID；Precision分母为所选ID，Recall分母为全部人工相关ID，空选择Precision=0。
- Answerability：模型true/false是否符合人工标签。
- Server Grounding：true答案是否等于证据原文拼接，false是否为固定文案且引用为空；不进行语义裁判。

Evaluator复用正式answerQuery，最多3路并发，结果按原Query下标保存；不增加LLM Judge。失败单独计数，不伪装成正常拒答，报告实际指标分母。详见 [ANSWER_EVALUATION.md](ANSWER_EVALUATION.md)。

## 7. 两个真实失败案例

### A. 酸梅汤是什么味道？

expectedAnswerable=true，actualAnswerable=false；正确`dish-8-taste`已进入Top-3，retrievalHit=true、retrievalRecallAt3=1。因此定位为Evidence Selection / Answerability False Negative，而不是Retrieval miss。

这定位了错误环节，但不能从输出反推模型内部为何拒答。本次没有为了消除该失败修改Prompt或标签。

### B. 有什么饮料？

真实人工调用answerable=true，但只选择`dish-4-ingredients`，回答柠檬茶，没有完整覆盖酸梅汤。Grounding正确不等于Answer completeness。

自动评测观察到Retrieval availability与Evidence Selection两层完整性损失。没有保存完整逐条真实输出时，不编造具体遗漏ID，也不把人工单次结果当作自动评测明细。后续优化必须和冻结baseline比较，不能用本地mock或调标签“提高”结果。

## 8. 真实微信前端验收

菜单问答是独立页面，经service调用正式rag.answer；每次提交覆盖旧结果，没有连续聊天历史。依据只显示title/text；相关菜品通过menu service读取当前价格与状态，再进入原详情页。

| 真实Query | 已验收现象 |
| --- | --- |
| 有什么比较清爽的？ | 沙拉“清爽”、黄瓜“爽脆”、柠檬茶“具有柠檬香气”的服务器原文正常显示；依据对应，无“解腻”等扩写，无内部字段暴露 |
| 我想吃牛肉 | 番茄牛肉面、双椒牛肉相关真实answer/evidence正常；任意单轮Query从输入到页面展示链路通过 |
| 有可乐吗 | 正常显示“当前提供的知识不足以回答这个问题。”；不说有/没有可乐，无无关evidence或相关菜品，无技术错误提示 |

“知识不足”与“确定不存在”含义不同。可乐案例表明本次系统没有把未检索到知识变成确定的菜单事实。这些是开发者真实微信开发者工具验收记录，不是新增准确率统计。

## 9. Known Limitations与后续方向

- 21-chunk知识库与12-query端到端评测较小，不能外推生产性能。
- 单轮Query，没有conversation memory、streaming或会话历史。
- Evidence Selection可能漏选或选错；Answerability已有False Negative。
- Top-3可能不完整；没有reranker、hybrid retrieval、query rewrite。
- 没有Agent / Tool Calling；不是production-ready系统。
- clientId不是真正认证，尚无支付和完整生产治理。

可先扩展独立人工评测，保存逐条真实输出，再针对已定位问题比较改进效果；任何检索/Prompt优化都应对照当前baseline。多轮与Agent只属于未来设计，本次不实现V5。

## 10. 复现与材料导航

- [整体架构](../ARCHITECTURE.md)、[README](../../README.md)
- [Answer API](ANSWER_API.md)、[评测运行步骤](ANSWER_EVALUATION.md)
- [简历素材](../RESUME_NOTES.md)、[面试说明](../INTERVIEW_NOTES.md)

V4.4.4收尾已通过417项本地测试及构建、知识副本和冻结校验。文档整理不改代码、不执行远程API，保持既有baseline。
