# 项目演示指南

本指南用于准备 GitHub 截图和 60～90 秒面试演示。只截取真实微信开发者工具与 uniCloud 结果，不制作或补写虚假数据。

## 演示前准备

- 使用已关联的 uniCloud 服务空间，并保持“连接云端云函数”。
- 确认菜单、RAG、Agent 与 orders 云对象是已验收版本。
- 准备一个干净购物车，便于展示柠檬茶 ×2。
- 截图前裁剪或打码 clientId、requestId、requestFingerprint、环境变量、请求头和调试信息。
- 不展示 API Key、Authorization、AppSecret、上传密钥或本地绑定配置。

## 8 张真实截图计划

### 1. 首页能力入口

展示首页的三个正式入口：

- AI 智能点餐
- 菜单问答
- 智能点餐 Agent

目的：让面试官先看到传统点餐、RAG 与 Agent 是同一项目中的独立能力。

### 2. RAG Grounded Answer

输入：

> 有什么比较清爽的？

截图包含回答与“依据”区域。真实验收内容应对应：

- 鲜蔬沙拉项目描述为“清爽”
- 拍黄瓜中的黄瓜项目描述为“爽脆”
- 柠檬茶项目描述为具有柠檬香气

页面不应展示 knowledgeId、embedding 或 similarity，也不应出现“解腻”“清爽的柠檬香气”等无依据扩写。

### 3. Agent 多步查询

输入：

> 有可乐吗？没有的话推荐点别的喝的。

截图展示最终自然语言结果。讲解时说明真实后台 Trace：

~~~text
search_menu({ query: "可乐" })
 → count = 0
 → Qwen observes Tool Result
 → list_available_drinks({})
 → dish-4 / 柠檬茶 / on_sale / ¥12
~~~

第二次调用是模型观察结果后的 re-planning，不是硬编码 fallback。

### 4. Cart Action Proposal

输入：

> 把柠檬茶加两杯到购物车

截图展示 Pending Action：

- 柠檬茶
- quantity = 2
- unitPrice = ¥12
- totalPrice = ¥24
- requiresConfirmation = true

### 5. Explicit Cart Confirmation

截图包含“确认加入购物车”操作和确认后的购物车结果。说明点击前不会修改 Pinia，点击时还会重新读取实时菜单。

### 6. Server Order Preview

从购物车进入确认订单页，展示：

- 柠檬茶 ×2
- 单价 ¥12
- 总价 ¥24
- 服务器已校价的 Order Proposal

说明这仍是预览，不是已创建订单。

### 7. Persisted Order Success

完成信息确认与最终下单确认后，截图展示成功状态及真实 orderNo。只有服务端确认成功后才清空购物车。

### 8. uniCloud Orders Record

在 uniCloud 数据库展示对应 orders 记录中的：

- items snapshot
- totalPrice
- totalCount
- status
- requestId 字段存在

裁剪或打码 clientId、完整 requestId、requestFingerprint 及其他不必要的内部字段。

## 60～90 秒 Demo Script

> 这个项目把模型的开放式决策和确定性交易边界分开。  
> 首先看菜单问答。我输入“有什么比较清爽的？”，RAG 用 21 条人工审核知识做 Top-3 检索，模型只选择 evidence，最终事实由服务器按可信原文渲染，所以页面还能展示依据。  
> 接着看多步 Agent。我问“有可乐吗？没有的话推荐点别的喝的。”，模型先调用菜单搜索，观察到可乐结果为空后，再自主调用在售饮料工具，返回实时在售的柠檬茶；第二步不是代码写死。  
> 然后我说“把柠檬茶加两杯到购物车”。Agent 只生成 24 元的 Pending Action，不直接改购物车。必须由用户确认，并再次检查实时菜单，Pinia 才发生修改。  
> Checkout 同样不交给模型。服务器先生成 24 元 Preview，最终确认时再次校价并比较预期，再持久化订单。  
> 如果服务端已写入但响应丢失，前端会用同一个 requestId 和冻结 payload 重试；服务端通过 SHA-256 fingerprint 与数据库唯一索引返回同一订单，避免重复创建。

## 演示重点

- 模型负责：语义理解、evidence 选择、Tool 选择和多步 re-planning。
- 服务器负责：真实菜单、状态、价格、参数校验、证据渲染、订单确认和幂等。
- 用户负责：确认会产生副作用的购物车与订单动作。

不需要逐页展示完整小程序。用 RAG → Agent → Cart Confirmation → Order Preview → Persisted Order → Idempotency 讲清工程边界即可。
