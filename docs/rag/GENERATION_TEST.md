# V4.4.1c：Evidence-first server rendering

## 真实验收背景与当前状态

以下历史情况来自开发者的真实远程验收，不是本地模拟值：

- **V4.4.1**：固定 Query“有什么比较清爽的？”经 Query Embedding、Retrieval Top-3、实时 dishes、Grounded Prompt、Qwen3.8-Flash、JSON 和 ID 校验，最小链路真实跑通。但自然语言回答出现无依据的“解腻”等扩写。
- **V4.4.1a**：更严格 Grounding Prompt、claim-level evidence references 和 claim knowledgeId / dishId 白名单验证真实运行成功；claims 本身可以较干净，但仍发现自由 answer 有 claims 之外的附加陈述。claim-level citation improves traceability, but free-form answer can still bypass validated claims。
- **V4.4.1b**：服务器改为拼接通过结构和 ID 校验的 claim.text，解决 **free-form answer bypasses validated claims**。真实复验又发现：引用合法的 dish-4-taste / dish-4 时，模型把“具有柠檬香气”扩写为“具有清爽的柠檬香气”。

这确认了 claim-level citation + ID validation 不能保证 claim semantic grounding。V4.4.1c 不再使用模型自由生成的事实文本，进一步关闭 **LLM-generated claim text can semantically expand beyond cited evidence** 这条输出路径。

**V4.4.1c 已由开发者完成真实远程验证。** 以下记录来自开发者的云端验收反馈；本次阶段收尾只做文档与本地检查，没有再次调用远程模型、执行 Indexer 或进入 V4.4.2。

## V4.4.1c 真实远程结果

固定 Query：**有什么比较清爽的？** 实际 Retrieval Top-K = 3：

| 排名 | knowledgeId | 真实 text |
| --- | --- | --- |
| 1 | dish-3-taste | 鲜蔬沙拉，项目描述为“清爽”。 |
| 2 | dish-7-taste | 拍黄瓜中的黄瓜，项目描述为“爽脆”。 |
| 3 | dish-4-taste | 柠檬茶，项目描述为具有柠檬香气。 |

真实返回 `errCode: 0`，最终服务器 answer 为：

```text
鲜蔬沙拉，项目描述为“清爽”。
拍黄瓜中的黄瓜，项目描述为“爽脆”。
柠檬茶，项目描述为具有柠檬香气。
```

对应 evidence IDs 为 `dish-3-taste`、`dish-7-taste`、`dish-4-taste`。人工复验确认：不再出现“解腻”，不再出现“清爽的柠檬香气”，也没有 evidence 之外的事实扩写；final answer factual content 直接来自 trusted evidence。

本次真实调用约为 **2 秒量级**，仅是一次运行观察，不代表稳定延迟或性能保证。

## 当前信任边界

```text
LLM selects evidence IDs
  → server validates evidence IDs
  → server reads trusted Retrieval evidence
  → server deterministically renders factual answer
```

模型只负责判断提供的上下文是否足够，并选择合法 evidence IDs。服务器验证身份、关联和实时在售状态，再从本次真实 Retrieval results 中取回原文生成最终答案。

没有第二次 LLM Judge、NLI、threshold、reranker、Hybrid Search 或任意用户 Query 接口；没有前端改动。Retriever 的 Query Embedding、Exact Cosine Search、Top-K=3、排序和模型配置完全不变；Knowledge Source、knowledge_chunks、Indexer、Evaluation 及 ai.recommend() 不改动。

## 固定诊断链路

```text
HBuilderX 上传并运行 rag-generation-admin，参数 {}
  → rag.testRagGeneration()
  → generator.js
  → 原 retriever.testRetrieval()
    → 固定 Query：有什么比较清爽的？
    → qwen3.7-text-embedding-flash / 512 维
    → knowledge_chunks → Exact Cosine Search → Top-3
  → 关联 dishId 去重 → 查询实时 dishes
  → Prompt → Qwen 只返回 answerable 与选择的 IDs
  → 服务器校验 → 用真实 knowledge text 生成 answer / evidence
  → answerable=true 时再次读实时菜品，确认事实未变化
  → 返回诊断结果
```

不硬编码历史 Top-3，不扫描全部菜品，不对 Top-3 按 dish 去重。只对实时查询用的 dishId 去重。

## Prompt 与模型合同

Prompt 仍明确区分 SYSTEM RULES、USER QUERY、RETRIEVED KNOWLEDGE、LIVE DISH FACTS、OUTPUT CONTRACT。

- 模型只选证据，不生成、改写、压缩或润色知识正文。
- 用户问题与数据库内容是数据，不能覆盖系统规则；不能用模型常识补充依据。
- 提供的知识只有本次 Top-3 的 knowledgeId、dishId、scope、type、title、text，没有 embedding 或 similarity 数值。
- 关联菜品的实时字段包括名称、价格、priceText、状态、描述、辣度和配料；缺失菜品明确标记。
- 上下文不足应拒答，不能为了凑数量选择无关证据。

通过现有 `uniCloud.httpclient.request` 调用 OpenAI-compatible `/chat/completions`，继续使用 `response_format: { type: "json_object" }`、`stream: false`、`enable_thinking: false`，没有新依赖。

模型现在只允许返回三个字段：

```json
{
  "answerable": true,
  "dishIds": ["dish-4"],
  "usedKnowledgeIds": ["dish-4-taste"]
}
```

这是合同示例，只有这些 ID 在本次上下文中且通过校验才可使用，不是预填的真实运行结果。

**旧 answer / claims 合同不再接受。** 模型输出 answer、claims、text、evidence、price、embedding 或其他额外字段时，整次返回安全格式错误，不忽略后偷偷使用，也不作为事实来源。模型不生成任何最终 factual wording。

拒答合同：

```json
{
  "answerable": false,
  "dishIds": [],
  "usedKnowledgeIds": []
}
```

## 服务器校验与渲染

1. JSON 为对象，只能有三个规定字段；answerable 必须为 boolean，两个 ID 字段必须是非空字符串元素组成的数组。
2. 两类 ID 分别按首次出现顺序去重，不丢弃未知 ID、不截断后冒充成功。
3. usedKnowledgeIds 必须是本次 Top-3 的子集。库内存在但不在本次 Top-3 的 ID 也拒绝。
4. dishIds 必须来自本次 Live Dish Facts，且 status 为 on_sale；售罄或缺失菜品拒绝。
5. 保留每个推荐菜品必须有选中关联知识的检查；同时要求所选 dish 级知识关联的 dishId 出现在已校验 dishIds 中，防止省略 dishIds 绕过实时在售检查。restaurant 级知识允许 dishId=null，不强制关联菜品。这是输出身份校验，不改变检索排名。
6. answerable=true 必须至少选一条知识。answerable=false 时两个模型 ID 数组必须为空。
7. 校验后，服务器从**本次 Retrieval 快照**按 ID 取出 knowledgeId、dishId、title、text，构造 `generation.evidence`。不展开模型对象，不使用模型提供的正文。
8. `generation.answer = evidence.map(item => item.text).join('\n')`。按选中 ID 的顺序原样连接正文，不添加前缀或属性、不改标点、不 trim 原文、不截断、不按分数重排。相同 ID 只渲染一次；不同 ID 即使文字相同，仍保留各自证据，不做语义去重。
9. 拒答由服务器固定返回“当前提供的知识不足以回答这个问题。”，dishIds、usedKnowledgeIds、evidence 全部为空。
10. answerable=true 返回前沿用实时菜品二次读取。提供给模型的字段变化、售罄或删除时拒绝本次旧结果，返回 `RAG_LIVE_FACTS_CHANGED`，不自动重新生成。

本次固定问题不展示价格或状态文本。实时字段用于选择和有效性检查，不从知识 chunk 推断实时价格。未来若展示实时价格/状态，必须由服务器使用已验证菜品的数据库字段确定性格式化，不能接受模型生成的价格事实。

## 最终返回示例

以下仅演示单条 evidence 的渲染关系，不是本次远程输出：

```json
{
  "model": "qwen3.8-flash",
  "answerable": true,
  "answer": "柠檬茶，项目描述为具有柠檬香气。",
  "dishIds": ["dish-4"],
  "usedKnowledgeIds": ["dish-4-taste"],
  "evidence": [
    {
      "knowledgeId": "dish-4-taste",
      "dishId": "dish-4",
      "title": "柠檬茶：风味或口感",
      "text": "柠檬茶，项目描述为具有柠檬香气。"
    }
  ]
}
```

这对应成功结果中的 `generation`；外层仍有 errCode、query、retrieval。retrieval 保留实际 Top-3 的精简明细和 similarity，供管理诊断，不传给模型作事实。retrieval.dishIds 是原始关联 ID，不等于可推荐清单；可使用的菜品 ID 在 generation.dishIds。

原模型 answer、claim.text 与 modelAnswerPreview 均不存在于最终返回。evidence 本身由服务器生成，不由模型提供。不返回完整向量、API Key、Authorization、请求头或原始完整上游响应，错误只使用固定安全文案。

## 解决的风险与仍存在的边界

- V4.4.1b 阻止自由 answer 绕过 claims，但 claim.text 仍由模型写作。
- V4.4.1c 移除模型对事实措辞的控制；输出事实文本逐字来自真实 evidence，不再允许模型把“柠檬香气”扩写为“清爽的柠檬香气”后直接送给用户。旧自由文本字段会被拒绝。

仍未解决的风险：

1. 模型可能漏选真正相关 evidence。
2. 模型可能选择合法但与 Query 不够相关的 evidence。
3. 模型可能错误判断 `answerable=true`。
4. 模型可能错误判断 `answerable=false`。
5. Retrieval Top-3 本身可能遗漏正确知识。

ID 合法和正文复制正确不等于问题已被正确回答。
服务器依赖当前审核知识和数据库本身的事实质量；本阶段不重新审核知识，也不保证这些事实永久不变。

**这不是整个 RAG 的 formal correctness guarantee。** V4.4.1c 解决 factual wording trust boundary，并未解决完整 answerability / evidence-selection correctness。正式 `rag.answer(query)` 和多 Query Generation / Answerability Evaluation 留待后续阶段。本次不实现这些评测或进入 V4.4.2，也不按本地结果调整 Retriever。

## 环境变量与 HBuilderX 按需复验

rag 继续使用自身已验证的配置，不会继承 ai 云对象变量：

| 环境变量 | 配置/用途 |
| --- | --- |
| DASHSCOPE_API_KEY | rag 现有远程密钥，不写入源码、日志或测试参数 |
| LLM_BASE_URL | 现有北京 OpenAI-compatible 基础地址 |
| EMBEDDING_MODEL | qwen3.7-text-embedding-flash |
| EMBEDDING_DIMENSION | 512 |
| RAG_LLM_MODEL | qwen3.8-flash，代码仍从环境变量读取 |

1. 本地执行 `pnpm run rag:check-source`，不要运行 Indexer 或初始化数据库。
2. 上传更新后的 `rag`，确保包含本次 generator.js；管理方法与原 Retriever 不需修改。
3. 保持远程环境变量不变，本阶段不新增变量。
4. 使用现有 **rag-generation-admin**，空参数 `{}`，执行“上传并运行云函数”。入口继续只接受平台 server 来源，rag 方法只允许 function/server；没有微信页面入口。
5. 成功时检查 `errCode: 0`、固定 query、实际 Top-3 及 generation。核对每条 evidence 的 knowledgeId/title/text/dishId 与本次检索一致，answer 恰好为选中正文换行拼接，没有“清爽的”等自行修饰。
6. 继续人工判断所选证据是否真正适合回答问题。非零错误码不是成功；answerable=false 是合法拒答，但不等于本固定问题的质量验收通过。

每次完整执行仍是一次 Query Embedding 和一次 Chat Completions，没有第二次 LLM 校验或自动重试。本次阶段收尾没有触发这些真实请求，也不需要为文档更新重新部署。

## 本地验证

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```

旧自由文本/claim 合同的测试已替换为三个字段的新合同测试；保留配置、安全错误、实时菜品、管理入口和冻结文件回归。新测试覆盖真实原文逐字渲染、额外文本拒绝、ID 顺序与去重、未知证据拒绝、空拒答、不同 Top-3、证据字段白名单。仅使用模拟 HTTP 与只读测试数据，不使用真实密钥、不写库。
