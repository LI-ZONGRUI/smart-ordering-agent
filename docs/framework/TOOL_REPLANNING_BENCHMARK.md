# Tool Selection + Sequential Replanning Benchmark v1

## 目的与边界

这套独立 Benchmark 只评估请求已经进入只读 Menu Agent 之后的行为：模型是否选择正确
Tool、参数是否正确、是否真正观察 Tool Result 后再规划下一步，以及最终回答是否与已观察
结果一致。它不评估业务 Router，也不评估多轮 Contextualizer：

- Router Benchmark：决定请求进入哪个业务 route。
- Contextualizer Benchmark：把 history + 当前省略问题改写为 standalone query。
- Tool Selection Benchmark：进入 Menu Agent 后选择哪个 Tool 和参数。
- Sequential Replanning Benchmark：看到 Tool Result 后，是否在后续模型决策中选择下一 Tool。

本阶段没有修改 LangChain Agent、LangGraph、Router、Contextualizer、Gateway、RAG、生产 Prompt
或 Function Calling 合同。默认 Runner 不构造 Qwen，也不访问 Gateway、uniCloud 或数据库。

## 当前只读 Tool 合同

| Tool | 参数 | 安全结果摘要 | 职责 |
| --- | --- | --- | --- |
| `search_menu` | `{query: string}` | `{count, items[]}` | 用短关键词搜索当前菜单 |
| `list_available_drinks` | `{}` | `{count, items[]}` | 列出当前在售饮料 |
| `get_dish_detail` | `{dish_id: string}` | `{found, item}` | 按已解析的内部菜品标识读取详情 |

所有 Tool 都是只读的。Benchmark 禁止购物车、订单、支付、退款等副作用 Tool；trace 中出现
任何非上述三项 Tool 的调用都会计入 `Unauthorized Tool Call Rate`。

生产 `FrameworkAgent` 使用 LangChain `create_agent()`：模型产生 Tool Call，Tool 返回
`ToolMessage`，模型再基于新消息继续决策或生成最终回答。当前没有另一套独立的业务层 Tool
call 数量配置；内部图递归上限为 13，用于有限地约束模型/Tool 循环。LangChain 可让同一
AIMessage 产生多个 Tool Call，因此 Benchmark 必须区分并行调用和基于结果的后续重规划。

Qwen 的 OpenAI-compatible 响应由现有 `ChatOpenAI` 解析：provider `tool_calls` 转为
`AIMessage.tool_calls`，参数解析失败进入 `invalid_tool_calls`。Benchmark 不替换该 parser。

## 40 条固定数据

| Category | Count |
| --- | ---: |
| `single_tool_selection` | 12 |
| `tool_argument_accuracy` | 8 |
| `no_tool_needed` | 5 |
| `sequential_replanning` | 8 |
| `no_premature_parallelism` | 4 |
| `tool_empty_or_failure` | 3 |
| **Total** | **40** |

Dev 30 条用于开发和失败分析；Holdout 10 条在优化前已冻结。Holdout 文件及 Dev 文件的
SHA-256 写入 `manifest-v1.json`。创建后不再人工打开、运行或用于调参；第一次正式运行必须
显式传入 `--confirm-holdout`。

`no_tool_needed` 按现有合同覆盖问候、致谢、能力说明和写操作拒绝。菜单事实仍必须查实时
Tool；这些用例没有凭空引入“菜单事实可以不查 Tool”的例外。

## Case 合同

每条 case 包含：

- `id / category / split / query / context`
- `initialTool / allowedInitialTools / forbiddenInitialTools`
- `expectedArguments`：按 Tool 与出现序号检查，字符串经 NFKC、大小写、空白和标点归一化，
  不做脆弱的字符级原样比较。`dish_id` 是不透明标识，只去首尾空格，不移除连字符或改变大小写。
- `requiresTool / requiresSequentialReplanning`
- `requiredTraceOrder / forbiddenPrematureCalls`
- `replanningCondition`：明确 call A、result A 的条件和 later call B。
- `expectedResultUsage / allowedFinalMeaning`

标签不通过关键词来判定“模型是否选对 Tool”；validator 直接检查真实安全 trace。

## 安全 Trace 合同

统一事件只有三类：

```text
assistant_tool_call(step, toolName, normalized safe arguments)
tool_result(step, toolName, resultClass, minimal summary)
assistant_final(step, answer, completed)
```

`resultClass` 只使用 `success / empty / missing / safe_error / invalid`。摘要只允许测试所需的
count、found 和明确列出的安全菜单字段，详情可保留 description/ingredients 以检查配料答案。
递归检查摘要字段、数字价格、count/items 与 resultClass 的一致性。不保存 API Key、Gateway Secret、会话 token、System
Prompt、模型 reasoning、Tool call ID、provider metadata 或完整原始响应。

真实模型评测通过 Benchmark 自己的 `ToolTraceObserver` callback 观察现有 FrameworkAgent：
每个 AIMessage 对应一个真实 decision step；callback 只保留允许的安全字段。生产 trace 会
过滤未知 Tool，因此评测不依赖它来计算越权率；observer 保留未知 Tool 的名字并丢弃其参数。
执行关联 UUID 只短暂留在内存中，不进入 observation 或报告。Tools 仍由原 create_agent 图执行。

现有 Agent trace 保持 LangChain messages 的真实顺序。同一 AIMessage 的两个 Tool Call 会表现为：

```text
call A(step=1) → call B(step=1) → result A(step=1) → result B(step=1)
```

这不是 Sequential Replanning。真正的顺序重规划必须满足：

```text
call A(step=1)
< result A(step=1)
< later call B(step=2)
< result B(step=2)
```

而且 B 的必要性由 `replanningCondition` 中的 A 结果条件决定。若 A 的结果已足够却额外调用
Tool，会计为 `UNNECESSARY_TOOL_CALL`。

冻结的真实能力合同包括：

```text
“有可乐吗？没有的话推荐点别的喝的。”
→ search_menu({query: "可乐"})
→ empty Tool Result
→ 后续模型决策 list_available_drinks({})
→ 使用该 Tool 的真实结果回答
```

第二个调用必须来自模型观察结果后的 replanning，不能由 Python `if count == 0` fallback 代替。

## Deterministic Validators 与 Metrics

Validator 检查事件顺序、planning step、Tool allowlist、归一化参数、结果类别、最终回答是否使用
已观察到的 item，以及空搜索是否被错误描述为确定存在。它不调用第二个 LLM Judge。

同一初始 decision 的所有 Tool 都必须满足初始 allowlist；Required Tool Call Accuracy 要求
全部必需调用实际出现。重复 result、孤立 result、step 倒退、final 后继续调用会使 trace 不通过。
即使其他字段不合法，仍统计可观察到的越权 Tool 尝试。菜品状态和明确单价在所属分句内比较，
避免把“柠檬茶在售、酸梅汤已售罄”的两个状态混在一起。

分别报告：

- Tool Selection Accuracy
- Tool Argument Accuracy
- Required Tool Call Accuracy
- Unnecessary Tool Call Rate
- Sequential Replanning Accuracy
- Premature Parallel Call Rate
- Tool Result Utilization Accuracy
- Final Answer Consistency
- Unauthorized Tool Call Rate
- Trace Contract Accuracy

不适用于某 case 的指标为 `N/A`，不计为 pass，也不进入该指标分母。

Failure taxonomy：`WRONG_TOOL`、`MISSING_TOOL_CALL`、`UNNECESSARY_TOOL_CALL`、
`WRONG_TOOL_ARGUMENT`、`PREMATURE_PARALLEL_CALL`、`REPLANNING_MISSED`、
`WRONG_SECOND_TOOL`、`TOOL_RESULT_IGNORED`、`FINAL_ANSWER_CONTRADICTS_TOOL`、
`UNAUTHORIZED_TOOL_CALL`、`TRACE_ORDER_ERROR`、`MODEL_OUTPUT_INVALID`。

## 运行方式

在 `services/framework-agent` 下：

```bash
# 默认只验证 Dev 数据、冻结 hash 与报告结构；完全离线，模型指标为 N/A
PYTHONPATH=. .venv/bin/python -m evals.tool_replanning.runner

# 使用此前捕获的安全 observation；仍不访问网络
PYTHONPATH=. .venv/bin/python -m evals.tool_replanning.runner \
  --observations /path/to/safe-observations.jsonl

# Dev 显式真实模型评测：Qwen + 生产 LangChain loop + 本地固定 Gateway fixture
PYTHONPATH=. .venv/bin/python -m evals.tool_replanning.runner \
  --live-model --confirm-live

# Holdout 第一次正式运行需要独立确认；若同时使用 Qwen，两组确认都必须存在
PYTHONPATH=. .venv/bin/python -m evals.tool_replanning.runner \
  --split holdout --confirm-holdout \
  --live-model --confirm-live \
  --report evals/tool_replanning/reports/holdout-live-v1.md
```

Live 模式只使用本地 `InMemoryMenuGateway` 固定数据，不访问远程 Gateway、uniCloud 或数据库。
本阶段没有执行 Dev live，也没有执行 Holdout。

`context.simulatedResultClass` 仅控制 Benchmark 本地 fixture 的故障响应；不会注入 expected
标签或调用后续 Tool。safe_error 使用现有 Tool 的固定安全错误，invalid 使用无效响应，missing
使用查不到的本地 ID。生产 Agent 遇到安全 Tool exception 会直接终止，observer 保留已发生的
call/result 并标记 `termination=safe_tool_error`，不伪造 assistant_final；这种故障用例的
Final Answer Consistency 与模型 Tool Result Utilization 为 N/A，trace 和调用指标仍可检查。
报告必须写入新的 `.md` 路径；不会覆盖既有报告、代码或冻结数据。

## 局限

- 40 条数据只能形成小型行为基线，不代表生产准确率。
- Final Answer 检查使用确定性字符串与 Tool Result 一致性规则，无法证明完整语义蕴含。
- 高级转述、隐含指代或未列出的幻觉不保证被字符串检查捕获；指标通过不能当作完整语义证明。
- ID 详情用例是已解析实体后的 Tool 层测试，query 中包含本地 fixture ID；不宣称覆盖自然语言实体解析。
- V1 包含相近措辞与共享本地 fixture，Dev/Holdout 是用例拆分而非跨领域分布拆分；不能夸大泛化结论。
- 本地 fixture 只覆盖少量菜单状态；实时菜单变化不属于该离线 Benchmark。
- Holdout 一旦用于失败分析，就不能继续视为完全未见测试集；后续需要新 Holdout 才能再次评估泛化。
