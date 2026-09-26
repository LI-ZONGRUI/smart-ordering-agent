# V7.1 LangChain Foundation 可行性结论

## Status

**Blocked by deployment constraints.**

V7.1 在正式代码创建前触发 Deployment Gate，因此本阶段没有创建 framework-agent、没有安装仓库依赖、没有修改 Native Agent，也没有部署或调用真实 Qwen / uniCloud。

阻塞原因有三项：

1. 按 DCloud 官方限制，uniCloud 单个云函数包含 node_modules 的体积上限为 10 MB；实际 LangChain 生产依赖远超该限制。
2. 当前 LangChain 正式 createAgent() API 会传递安装 @langchain/langgraph，与 V7.1 “不加入 LangGraph”的阶段边界冲突。
3. 现有只读 Tool domain logic 位于冻结的 agent 云对象内部。新云对象无法在部署包中直接 require 兄弟云对象源码；调用 admin/testTool 也不适合作为生产依赖。在不修改冻结 Native Agent 的条件下，无法形成可靠的共享实现。

因此没有通过删除第三方文件、裁剪 node_modules 或复制菜单查询规则来规避 Gate。

## Feasibility Check

### Existing project

- 根项目使用 pnpm lockfile v9，没有把 cloudfunctions 声明为 pnpm workspace packages。
- 现有 uniCloud 云对象使用 CommonJS 与 index.obj.js。
- 当前开发机 Node.js 为 24.21.0；uniCloud 阿里云支持的最高运行时为 Nodejs20。
- Native Agent 的 Registry、Executor、Runner 和 read-only Tool 已完成真实验收并保持冻结。
- 只读 domain logic 位于 agent/tools/menu-tools.js；Executor 通过静态映射调用。
- 云对象 package.json 独立管理依赖。

### Version selection

2026-09-26 查询并实测的兼容组合：

| Package | Version | Runtime note |
| --- | ---: | --- |
| langchain | 1.5.12 | Node >=20；提供 createAgent() / tool() |
| @langchain/core | 1.2.12 | Node >=20 |
| @langchain/openai | 1.4.0 | Node >=20 |
| zod | 4.6.5 | Schema dependency |

当时最新 @langchain/openai 1.5.13 要求 Node >=22，不适用于 uniCloud 阿里云最高 Nodejs20，因此没有选择最新版本。

langchain 1.5.12 的真实依赖树包含：

~~~text
langchain@1.5.12
 ├─ @langchain/core@1.2.12
 ├─ @langchain/langgraph@1.4.18
 ├─ @langchain/langgraph-checkpoint@1.1.5
 └─ langsmith@0.10.5
~~~

这意味着当前推荐 createAgent() 并不是不含 LangGraph 依赖的独立包。V7.1 禁止加入 @langchain/langgraph，因此不能在本阶段落库这组依赖。

## CommonJS / ESM Compatibility

在隔离临时目录中完成了不发网络请求的 module-load smoke test：

- Node 24：CommonJS require 通过。
- Node 24：dynamic import 通过。
- Node 20.20.2：CommonJS require 通过。
- Node 20.20.2：dynamic import 通过。
- ChatOpenAI 可以使用占位 API Key 和无效测试地址构造，不触发请求。
- createAgent({ model, tools, systemPrompt }) 可以实例化。
- 依赖树没有发现 .node、.so 或 .dylib 原生模块。

因此模块形式本身可兼容 CommonJS 云对象；部署阻塞来自包体积、LangGraph 阶段边界及 Tool 共享边界。

如果未来改用其他部署目标，推荐 Node.js 20，并把 dynamic import 封装在 Framework Adapter 内；无需把根 package.json 改成 type=module。

## Package-size Gate

使用 npm production install、未安装 dev dependencies、未运行第三方安装脚本，并且没有删除依赖内部文件。

### Full createAgent dependency set

直接依赖：

- langchain 1.5.12
- @langchain/core 1.2.12
- @langchain/openai 1.4.0
- zod 4.6.5

实测：

| Measurement | Size |
| --- | ---: |
| node_modules | 92,114,944 bytes（约 88 MB） |
| package directory before diagnostic ZIP | 92,139,520 bytes（约 88 MB） |
| diagnostic ZIP | 24,187,199 bytes（约 23 MB） |
| installed files | 8,725 |

DCloud 文档说明 uniCloud 单个云函数上限为 10 MB，包含 node_modules；阿里云采用全量上传。这组依赖显著超过限制。

### Adapter-only comparison

即使移除 langchain，只保留 ChatOpenAI Adapter 所需的：

- @langchain/core 1.2.12
- @langchain/openai 1.4.0
- zod 4.6.5

实测仍为：

| Measurement | Size |
| --- | ---: |
| node_modules | 73,646,080 bytes（约 70 MB） |
| diagnostic ZIP | 19,685,764 bytes（约 19 MB） |

因此仅去掉 createAgent 也不能使当前官方 Adapter 进入 10 MB Gate。手工删除包内文件不属于可靠部署方案。

## Intended Architecture if the Gate is resolved

这部分是后续方案，不是当前已实现能力：

~~~text
User Query
 → independent Framework Agent
 → ChatOpenAI / Qwen OpenAI-compatible endpoint
 → LangChain createAgent()
 → three read-only Structured Tools
 → shared menu domain logic
 → final answer
~~~

只允许：

- search_menu
- list_available_drinks
- get_dish_detail

不允许 Cart、Order、Payment、RAG Tool 或其他写操作。

环境变量计划仍为 DASHSCOPE_API_KEY、LLM_BASE_URL 和独立的 FRAMEWORK_AGENT_LLM_MODEL；密钥只在服务端配置。

## Tool Contract Reuse Boundary

生产 Framework Agent 不应：

- 复制 dishes 查询、饮料分类和状态过滤逻辑。
- 调用 agent.run() 包装成 LangChain Agent。
- 调用 agent-tool-admin 或其他管理入口。
- 通过相对路径依赖另一个云对象的部署目录。

要共享 domain logic，后续需要一次独立、明确的 shared-tool extraction：

1. 把三个 read-only menu handlers 与纯合同抽成 uniCloud 公共模块或独立版本化包。
2. Native Agent 与 Framework Agent 同时依赖该公共模块。
3. 用 contract tests 冻结 Tool 名称、参数与基本结果字段。
4. 重新完成 Native Agent 回归和真实云端验收。

这会修改当前冻结的 Native Agent 依赖边界，所以没有在 V7.1 Gate 失败后擅自执行。

## Minimal Alternatives

### Recommended now

继续使用已经稳定验收的 Native Function Calling Agent。它没有新增包体积问题，并已具备多步 Tool Loop、allowlist、Schema、执行上限和安全 Trace。

### If LangChain remains a portfolio requirement

将 Framework Agent 放到独立 Node.js 20 服务或允许更大部署包的运行环境：

- 使用容器或独立函数服务，不受 uniCloud 10 MB 限制。
- 与现有 uniCloud 业务通过受认证的服务端接口交互。
- 先完成 shared read-only Tool extraction，不调用 admin 接口。
- LangChain 与 LangGraph 的阶段边界需要重新确认，因为当前 createAgent() 会传递依赖 LangGraph。
- 保持微信前端与 Native Agent 主链不变，Framework Agent 作为并列实验能力。

## Deployment Decision

当前结论：

> LangChain uniCloud deployment blocked by package-size constraint.

同时还有 createAgent 的 LangGraph 传递依赖和共享 Tool 边界未满足。因此：

- 不创建 framework-agent 云对象。
- 不创建 framework-agent-admin。
- 不修改 README 或 ARCHITECTURE 宣称已实现。
- 不配置环境变量。
- 不在 HBuilderX 创建远程函数。
- 不执行真实 Qwen 或 uniCloud 验收。

## Official references

- DCloud uniCloud 云函数与运行时、10 MB 包限制：<https://doc.dcloud.net.cn/uniCloud/cf-functions>
- LangChain JavaScript createAgent reference：<https://reference.langchain.com/javascript/langchain/index/createAgent>
- LangChain OpenAI integration reference：<https://reference.langchain.com/javascript/langchain-openai>
