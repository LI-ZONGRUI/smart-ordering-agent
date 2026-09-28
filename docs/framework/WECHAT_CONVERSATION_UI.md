# V7.3C WeChat Conversation UI

V7.3C 在微信小程序中实现了一个单会话的“AI 点餐助手”页面。前端只管理输入、展示、当前
conversation capability、安全历史恢复和待确认动作 UI；LangGraph 路由、Contextualizer、RAG、
Native Agent 和 Tool 调用仍由既有后端负责。

**V7.3C WeChat conversation UI has completed real acceptance in WeChat DevTools.**

## 配置

Base URL 通过 `VITE_FRAMEWORK_AGENT_BASE_URL` 注入，不写入源码。开发环境可以在被 Git 忽略的
`.env.development.local` 中配置 `http://127.0.0.1:8000`。微信开发者工具本地验收时需要临时开启
“不校验合法域名、web-view、TLS 版本以及 HTTPS 证书”。该设置只适用于开发；正式部署必须使用
HTTPS，并在微信公众平台配置合法 request domain。

service 层统一提供：

- `createConversation()`
- `runFrameworkAgent(query, threadId, conversationToken)`
- `getConversationMessages(threadId, conversationToken)`

`conversationToken` 只进入 `X-Conversation-Token` Header 和本机 storage，不进入 URL、页面消息或
日志。前端不保存 Model Studio Key、Gateway Secret 或 HMAC Key。

## 会话与历史

首次进入且没有本地 capability 时创建 durable conversation，并保存当前单一
`threadId + conversationToken`。再次进入时调用安全 History API，只恢复 `role/content`。访问被
拒绝时不循环重试，页面提示新建对话。新建对话只更换当前 capability，不删除旧 SQLite 会话；
当前没有 conversation list、rename、search 或 delete API。

History API 不返回 `pendingAction`，因此重新进入页面后只恢复文字。旧动作卡是页面会话期间的
UI 状态，前端不会从 assistant 文本反向解析动作。

## 动作确认边界

合法 `pendingAction` 显示为待确认卡片。点击确认复用既有
`executePendingCartAction → getDishes → Pinia addDish` 路径：先重读实时菜品与价格，再执行本地
Cart mutation。取消只更新本地卡片。用户在输入框键入“确认”仍作为普通 Query 发给后端，不会
触发 Cart、订单或支付。页面不包含订单创建和支付能力。

当前 UI 使用纯文本插值，不使用 `v-html`、rich-text 或未清洗 HTML。一次只允许一个 Agent
请求进行，客户端超时为 45 秒。Markdown-like 内容按安全文本展示，可能保留 `**` 等标记。

## 真实微信验收

在微信开发者工具中，同一 durable conversation 连续完成了以下流程：

1. “有柠檬茶吗？”进入实时菜单分支，返回当前 12 元、在售。
2. “多少钱？”通过上下文识别柠檬茶，同时重新查询实时菜单事实。
3. “它是什么味道？”进入知识分支，复用现有 RAG 返回柠檬香气、红茶和柠檬等已有事实。
4. “那来两杯。”进入动作分支，返回经过校验的柠檬茶 ×2 `pendingAction`。

动作卡真实显示单价 ¥12.00、合计 ¥24.00。点击 UI 的“确认加入购物车”后，前端重新读取
uniCloud 菜单并校验状态与价格，再调用既有 Pinia `addDish`；购物车最终为柠檬茶 ×2、合计
¥24。本次操作没有创建订单或支付。随后在输入框发送文字“确认”，系统只返回只读安全说明，
购物车仍为 ×2，证明文本消息不具备动作执行权限。

动作卡与消息区域没有展示 dishId、route、Tool 名称、raw JSON、reasoning、conversationToken 或
checkpoint 内部字段。验收当天为 2026-09-28；订单页最新可见订单仍为 2026-09-26 16:20 的历史
订单，进一步确认本次 UI 加购没有创建新订单。

首次确认使用 CLI 开发产物时，因为该运行方式没有 HBuilderX 已关联的 uniCloud 运行环境，实时
菜单复核失败并显示“暂时无法确认菜品状态，请重试。”，系统没有信任旧提案或写入购物车。改用
HBuilderX 连接阿里云服务空间运行后，复核与加购成功。这是预期的 fail-closed 行为。

退出页面再进入后，History API 恢复了 user/assistant 文字。完全停止并重启 FastAPI 后，使用同一
持久 SQLite 文件以及微信本地保存的 `threadId + conversationToken` 仍能恢复历史。该结果只证明
同一持久文件系统上的 process-restart recovery，不代表分布式、多实例或跨设备账户同步。

点击“新对话”会创建新的 threadId/token 并清空当前 UI，旧 SQLite conversation 不会删除。History
API 不返回动作提案，因此旧 `pendingAction` 卡片重进页面后不会恢复，也不会从文本反向解析。
