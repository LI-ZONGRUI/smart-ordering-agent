# RAG Retrieval + Evidence-first Grounding Benchmark v1

## 范围与生产审计

这是独立的评分基础设施，不修改生产 RAG，也不沿用旧版评测的数字。

生产链路：

```text
Query → qwen3.7-text-embedding-flash / 512
      → verified knowledge_chunks / 21 条
      → Exact Cosine / Top-3
      → Live Dish Facts
      → Qwen3.8-Flash 选择 evidence IDs 与 answerable
      → server-side ID / on_sale / 双向关联校验
      → 从真实 knowledge text 原文按选择顺序拼接 answer
```

- Retriever 不设 threshold，没有 reranker、BM25、boost 或 dish 去重。
- Generation 只接受 `answerable / dishIds / usedKnowledgeIds`；自由 answer、claims、额外字段被拒绝。
- `usedKnowledgeIds` 必须来自本次 Top-3；dishIds 必须来自本次在售菜品，证据和菜品双向关联。
- answerable=false 返回固定拒答，IDs 和 evidence 都为空。
- 生成后重新核对 live dishes；数据变化时拒绝旧结果。
- 合法 ID 和原文渲染保证身份与文本来源，不保证证据相关、完整或 answerable 决策正确。

人工知识源仍是 `docs/rag/knowledge-source.json`：21 条 verified、sourceVersion=1；
6 description、7 taste、8 ingredients。dish-4 / dish-8 没有 description，dish-5 / dish-6 没有 taste，不能补造。
知识不包含实时价格、状态、销量。辣度定义有 restaurant 级知识。

旧 `answer-eval.json` 的 12-case 评测与 Agent Benchmark Dev 中的 RAG 检查保持原样。
它们的分母、测试任务、指标不能与本 Benchmark 合并。

## 目录与冻结

`services/framework-agent/evals/rag_benchmark/`：

- `datasets/dev.jsonl`：30 条开发集。
- `datasets/holdout.jsonl`：10 条冻结集，创建后不得人工查看或用于调优。
- `datasets/manifest-v1.json`：版本、数量、类别、知识源与文件 SHA-256。
- `fixtures/knowledge.json`：人工源的逐字冻结副本，仅供 Benchmark；不是第二份维护源。
- `fixtures/dishes.json`：初始化菜单的冻结测试快照，不代表当前云数据库状态。
- `schema.py`：严格字段、证据身份、分组、标签/在售策略、唯一性、哈希与导出向量校验。
- `validators.py / metrics.py / report.py`：确定性评分、分母、无原始回答的安全报告。
- `runner.py / bridge.cjs`：离线默认与真实 Model Studio 边界；bridge 直接复用生产 JS exports。
- `.local/`：Git ignored，放本地导出向量与非公开 observation；不要将原始模型回答持久化。

Manifest 自身 SHA-256 固定在 schema.py，不能同时改数据和 manifest 来悄悄通过冻结检查。
新 Holdout 创建时建立标签，随后只做程序化 schema / 数量 / 唯一性 / 哈希检查；未运行评测。
其他 Benchmark 的 Holdout 不属于本任务，未读取。

Holdout SHA-256：

```text
db380d9ce60c156e589c3ab0b0a8c4745d4f0bd51e812e95c342105c723f67c9
```

| 类别 | Dev | Holdout | 总数 |
| --- | ---: | ---: | ---: |
| direct_fact | 6 | 2 | 8 |
| paraphrase | 5 | 2 | 7 |
| multi_evidence | 4 | 2 | 6 |
| similar_dish | 4 | 1 | 5 |
| unsupported_inference | 4 | 1 | 5 |
| out_of_scope | 3 | 1 | 4 |
| live_fact_boundary | 4 | 1 | 5 |
| **总计** | **30** | **10** | **40** |

标签只使用真实知识 ID；`requiredEvidenceGroups` 的每组是同一子事实的可替代证据，
组合问题必须每组至少命中一条。`relevantKnowledgeIds` 是各组并集。
菜名近似、口语问法、子事实组合、未知功效/营养/政策均单独覆盖，没有通过换菜名批量凑数。

`knowledgeAnswerable` 指冻结知识能否支持；`answerable` 还受当前生产的 on_sale 与原文 renderer 边界限制。
价格问题的 live fact 可能存在，但当前 renderer 只输出所选知识原文；它不能凭稳定知识回答实时价格。
此类 case 的拒答标签基于 **no-renderable-knowledge-answer**，不表示数据库没有价格。

`default / lemon_repriced / lemon_sold_out` 都是本地、可重复测试场景。
改价 30.5 仅是测试值；不修改初始化数据或云数据库，不把改价/售罄写入知识文本。

## 阶段与指标

### Retrieval

只在 real query embedding + 审核过的完整向量导出模式下记录检索指标。
没有可靠向量时，默认不会生成伪造向量，也不会用 expected labels 代替检索。

- Retrieval Hit@3：有 relevant IDs 的问题，Top-3 至少命中一个。
- Recall@3：命中不同 relevant IDs 数 / relevant 总数；保留部分命中数值。
  relevant 数大于 3 时存在 Top-K 理论上限；不足 1 不等于错误或幻觉。
- Correct Knowledge ID Retrieval：Top-3 身份/唯一性/rank/finite score 合同有效。
  它是 ID 合同指标，不替代 Recall 或语义相关性。

### Evidence Selection / Answerability

- Evidence Relevance：正样本的 selected IDs 全部属于 relevant，并覆盖所有 required groups。
  只使用有限人工标签，不声称通用语义证明。
- Answerability Accuracy：实际 answerable 与冻结 corpus + live profile 的 expected 对比。
- Context Answerability Accuracy：实际 answerable 与 **实际 Top-3 的可用证据**对比，
  帮助区分“检索没找到”与“找到了但没使用”。
- Correct Rejection Rate：预期无法回答的子集，正确返回 answerable=false。
- Unsupported Answer Rate：预期无法回答的子集，返回 answerable=true 的比例。
  正文来自真实但无关知识仍可能是 Unsupported Answer；它不等于伪造事实。

### Grounded Answer

- UsedKnowledgeIds Validity：Top-3 子集、唯一性、知识存在、在售、dish 双向关联。
- Evidence Attribution Accuracy：evidence 顺序与六个字段逐字等于真实源记录。
- Grounding Accuracy：证据校验通过，answer 严格等于 selected texts 以换行拼接；拒答为固定文本。
  这是生产 rendering contract，不是 formal semantic entailment。
- Unsupported Claim Rate：响应级的证据外文字筛查，而非原子 claim 的通用语义判定。
  严格原文渲染可以确定未新增文字；不同自由文本可能是合法改写也可能是扩写，进入 REVIEW。
  此时只报告已检测错误的下界，必须同时看 REVIEW 数；**不能把下界 0 当作零幻觉**。

所有指标区分 PASS / FAIL / REVIEW / N/A：

- PASS：受支持的确定性规则通过。
- FAIL：明确的 benchmark 标签/结构/渲染合同违背；不自动解释为人工确认的模型幻觉。
- REVIEW：API 失败、观测缺失或自由文本语义无法可靠判定。
- N/A：该问题/运行模式不适用，没有可靠检索观测时 retrieval 指标为 N/A。

REVIEW 留在 applicable 分母中，不能算 PASS。报告同时记录保守自动通过率、确定性检查覆盖率、
machine-detected failures、人工复核数和原因。Recall 的平均使用部分命中数值，不用“完全命中 case 数”代替。
错误比例在 REVIEW 存在时是 observed lower bound；不剔除 REVIEW 提高准确率。
不使用第二个 LLM Judge，不把 similarity 解释为概率或正确率。

## 运行边界

在 `services/framework-agent` 执行。默认不读取 Holdout、不构建网络客户端：

```bash
PYTHONPATH=. .venv/bin/python -m evals.rag_benchmark.runner
```

默认 `validation-only`：校验 Dev30 与冻结源，所有性能指标为 N/A。

`supplied-observations` 仅用于离线评分合同自测：

```bash
PYTHONPATH=. .venv/bin/python -m evals.rag_benchmark.runner \
  --mode supplied-observations --observations evals/rag_benchmark/.local/observations.json
```

该模式不对 fixture 排名宣称真实检索准确率；retrieval 指标仍 N/A。
CLI 不生成 oracle observation，也不保存答案。提供者若手工创建 observation 文件，须使用脱敏测试文本；
不要将真实原始模型回答持久化到该文件。正式 live 结果只在内存/子进程 IPC 中评分。

### 准备真实检索输入

本阶段没有调用/导出云数据库，也没有现成经过核验的完整真实向量。
首次 live 前，需你单独从现有 knowledge_chunks 导出 21 条审核过的记录到本地：

`evals/rag_benchmark/.local/knowledge-index.json`

导出须包含源字段、sourceVersion、verified、embedding、embeddingModel、embeddingDimension。
不要生成假向量，不要提交向量文件。建立同目录 `knowledge-index-manifest.json`：

```json
{
  "origin": "unicloud-knowledge_chunks-export",
  "sha256": "导出 JSON 原始字节的 SHA-256",
  "sourceSha256": "fixtures/knowledge.json 原始字节的 SHA-256",
  "embeddingModel": "qwen3.7-text-embedding-flash",
  "embeddingDimension": 512
}
```

哈希与 origin 是可追溯声明，不能加密证明向量确实由指定模型生成；需人工核验导出来源。
runner 检查 21 条完整唯一、源字段不漂移、512 个 finite number、非零、模型维度一致。

运行前在进程环境设置 DASHSCOPE_API_KEY、LLM_BASE_URL、EMBEDDING_MODEL、EMBEDDING_DIMENSION；
Generation 还需 RAG_LLM_MODEL=qwen3.8-flash。runner 不自动加载本机 .env，不输出配置值。

真实 Embedding-only Dev：

```bash
PYTHONPATH=. .venv/bin/python -m evals.rag_benchmark.runner \
  --split dev --mode live-retrieval --live-model --confirm-live \
  --index-fixture evals/rag_benchmark/.local/knowledge-index.json \
  --index-manifest evals/rag_benchmark/.local/knowledge-index-manifest.json \
  --report evals/rag_benchmark/reports/dev-retrieval-live-v1.md
```

首次完整 Dev Generation（会真实消耗 Model Studio API）：

```bash
PYTHONPATH=. .venv/bin/python -m evals.rag_benchmark.runner \
  --split dev --mode live-generation --live-model --confirm-live \
  --index-fixture evals/rag_benchmark/.local/knowledge-index.json \
  --index-manifest evals/rag_benchmark/.local/knowledge-index-manifest.json \
  --report evals/rag_benchmark/reports/dev-generation-live-v1.md
```

两者直接复用冻结 production JS 的 retrieveQuery / answerQuery，无另写 cosine 或 Prompt。
真实模型上下文只包含 Query、实际检索与本地 dishes profile；expected labels 不传给模型。
**这是 real Model Studio + frozen local corpus/menu snapshot，不是当前生产云 DB E2E。**
不调用 Gateway / uniCloud，不写数据库。

未来正式 Holdout 需要额外 `--split holdout --confirm-holdout`；live 同时要求 `--live-model --confirm-live`。
无确认在加载数据前拒绝。当前未运行 Holdout，也没有真实 Dev 结果，不填性能数字。
已有报告不可覆盖，report 路径限制在本 Benchmark reports 或 .local 中。

## 安全观测与回归

报告只含 case ID、类别、证据 IDs/ranks/similarity、评分状态/数值、失败与复核原因，
以及模型配置名、源码指纹、dataset manifest/source/index hashes、模式与 split。
不包含 Query、回答原文、完整 evidence text、vectors、provider response、reasoning、密钥、个人信息。

测试：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python -B -m pytest \
  -p no:cacheprovider tests/test_rag_benchmark.py -q
node --test ../../tests/rag-*.test.cjs
.venv/bin/ruff check .
.venv/bin/ruff format --check .
uv lock --check --offline
```

完整 Python 回归需排除/阻断会打开其他冻结 Holdout 的测试；不能以“回归”为由读取 Tool Replanning Holdout。
新 Holdout 的程序化 freeze 测试只检查完整性，不输出或运行任何 query。

本阶段没有优化生产 RAG，没有声称 benchmark 自测通过等于模型准确率提升。

### 本次离线验证结果

- 新 Benchmark Python：60 项通过；JS bridge：6 项通过。
- 现有 RAG/Evidence-first 与新 bridge 合计：395 项通过。
- 隔离后的完整 Python 回归：629 项通过，33 项因其他冻结 Holdout/子进程隔离而跳过；
  旧 Holdout 内容实际读取数为 0。
- Ruff check / format check、uv offline lock check、git diff --check 通过。
- 审计前后的 64 个受保护生产/知识/旧评测文件 SHA-256 全部相同。
- 待提交文件扫描未发现真实凭证；.local、.env、HBuilderX/服务空间本地文件继续忽略。
- 未调用任何远程服务。以上为基础设施回归，不是 Dev live 或 Holdout 性能结果。
