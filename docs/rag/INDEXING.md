# V4.2.4 Knowledge Source V1 索引操作说明

V4.2 已完成真实环境验收。根据开发者于 2026-09-21 的确认：首次正式索引插入 21 条知识，第二次运行 21 条全部 skip。本次收尾未再次触发远程 Embedding 或写库。下文保留为新环境部署、后续维护和排错步骤；检索、Cosine、Top-K 和 RAG 问答均不在本阶段。

## 1. 唯一知识源和部署副本

人工只维护 `docs/rag/knowledge-source.json`。现有 21 条 V1 正文、审核标记和 `sourceVersion` 没有改动。

云对象部署包以 `cloudfunctions/rag/` 为范围，不能依赖仓库根目录 `docs/` 在云端存在。因此部署资源为：

- `rag/resources/knowledge-source.json`：脚本逐字节复制，禁止手工编辑。
- `rag/resources/knowledge-source.manifest.json`：自动生成源路径、文件 SHA-256 和条数；没有时间戳噪声。

在项目根目录运行：

```sh
pnpm run rag:sync-source
pnpm run rag:check-source
```

第一条只从人工源单向复制，校验全部知识已审核、字段完整、ID 唯一；第二条只检查、不改文件。不调用模型、数据库，不生成向量。

`pnpm run build:mp-weixin` 也先执行副本检查，本地索引测试同样检查两份文件一致。HBuilderX 上传不会自动执行 pnpm 脚本，**每次上传 rag 前仍须先同步并检查**。

云端 `loadSources()` 用 `__dirname` 读取部署资源，并核对 manifest hash 和条数。它能检测部署资源损坏，不能知道仓库里尚未同步/部署的新版本，因此同步检查不能省略。

## 2. 管理入口

`rag/index.obj.js` 保留 `testEmbedding()` / `testBatchEmbedding()`，增加 `buildKnowledgeIndex()`，正式逻辑位于 `rag/indexer.js`。

`buildKnowledgeIndex()` 不接收源知识、密钥或环境配置参数，只允许 uniCloud 平台上下文中的 `function` / `server` 来源。客户端、HTTP 和缺失来源拒绝；微信页面没有调用入口。

[官方运行说明](https://doc.dcloud.net.cn/uniCloud/rundebug.html)指出云对象不支持直接“上传并运行”。因此增加很薄的普通云函数 `rag-index-admin`：只接受平台 `context.SOURCE === 'server'`，再通过 `uniCloud.importObject('rag')` 调用索引方法。它不读取请求参数中的伪造来源、不配置 URL 化或定时任务、不保存密钥。所有 indexing 逻辑仍在 rag。

来源限制面向受信任的云端部署代码，不是 uni-id 管理员身份认证。以后新增云函数时不要向普通用户开放能任意转发到此方法的代理。

## 3. contentHash 和幂等判定

使用 Node 内置 `crypto`，对固定字段顺序的 JSON 计算 SHA-256：

```text
knowledgeId, scope, dishId, type, title, text, sourceType, sourceFields
```

`sourceFields` 每项固定为 `file, recordId, fields`，缺少 recordId 在 hash 中规范为 null；数组顺序保留。正文不 trim、不改标点、不改换行。写入数据库的 sourceFields 原样保留。

`sourceVersion`、模型、维度独立比较，不放进 contentHash。时间戳、向量、价格、售卖状态、销量不参与 hash。送入 Embedding 的只有 `text`；其他元数据变化也触发重建，以确保派生记录不会遗漏更新。

| 数据库记录 | 动作 |
| --- | --- |
| knowledgeId 不存在 | Embedding 后 insert |
| sourceVersion、contentHash、embeddingModel、embeddingDimension 均相同且 verified 为 true | skip，不调用模型、不改时间戳 |
| 任一上述值不同 | Embedding 后 update 原记录，保留 _id/createTime |

当前运行维度固定 512：历史记录标记为 256 会被重建为 512；环境变量设成 256 则预检失败，不写入本版索引。未来切换模型必须先确认接口能力和 schema 约定。

唯一 `knowledgeId` 索引必须先部署。新增记录另以 knowledgeId 的 SHA-256 前 32 位作为确定性 `_id`，防止并发插入重复知识。发现历史重复 ID 时整次预检失败，不擅自清理。

更新使用 `_id + knowledgeId + 原 updateTime` 条件，未确认恰好更新一条则计为失败，避免并发覆盖。请一次只手动运行一个索引任务；本版不是分布式任务调度系统。

## 4. 批处理与映射

仅将 insert/update 项加入待处理队列，每批最多 **10 条**。当前模型同步接口[官方单批上限为 20](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api/)，本版保守取 10。首次 21 条通常为 10 / 10 / 1 三次 HTTP 请求，后续只请求变化项。这里是同步 `/embeddings` 的多文本 input，不是另一个异步 Batch 作业接口。

响应不要求按数组位置排序。每个 `item.index` 必须是 batch 范围内的唯一整数；数量必须匹配、覆盖所有输入；每条向量必须为 512 项有限数字。按 `batch[item.index]` 对应知识，整批校验完成后才能开始写库。无自动 HTTP 重试。

预检还会确认 dish 级 ID 存在于 dishes，不按 status 过滤长期知识。只读 dishes，不改菜品、订单或售卖状态。

## 5. 失败、重跑与 orphan

每条记录以一次 add/update 写入完整内容及向量，成功确认后才增加 inserted/updated；不先写“已完成”标记。部分写失败保留已成功的记录，继续统计其他写入，最终 `errCode: INDEX_PARTIAL_FAILURE`、`failed > 0`，附失败 knowledgeId 和安全错误码。

上游响应异常时本批不写库，并停止后续请求；所有未处理项计为 failed。数据库响应丢失时也计失败，不能把未知状态当成功。重跑会重新读取数据库，已完成的记录 skip。

这不是跨 21 条记录的事务；若云平台硬超时或进程中断，可能根本收不到返回统计。此时不能认定成功或全部回滚，应核查数据库后重跑。rag 和管理函数配置 120 秒超时；索引器在约 85 秒后停止开始新的操作，为返回统计预留时间。单个数据库请求阻塞仍可能触发平台硬超时。

已有记录分页读取（每页 100），只投影比对元数据，不读取完整向量。数据库 knowledgeId 不在当前源集合中的记录是 orphan；只返回 `orphanCount`、`orphanKnowledgeIds`，绝不删除。`orphanScanComplete: false` 表示扫描未完成，此时不能把计数 0 当作没有孤儿。

索引器不记录密钥、请求头、原始上游错误、完整向量，也不返回向量 preview。管理函数会保留 SDK 异常中可用的失败统计；若 SDK/平台没有保留统计，则返回 `INDEX_ADMIN_CALL_FAILED`，明确运行状态未知。

## 6. HBuilderX 部署步骤（由你手动执行）

1. 打开当前 `wechat-ordering-uniapp` 项目，确认 `uniCloud-aliyun` 仍关联阿里云 `xlimao`。执行前面的同步与检查命令，看到“21 条，内容与人工源逐字节一致”。
2. 在 `uniCloud-aliyun/database/knowledge_chunks.schema.json` 上右键选择“上传 DB Schema”。只上传这一张表；若尚不存在，schema 上传会创建它。去 uniCloud 控制台 → xlimao → 云数据库 → knowledge_chunks，确认表结构包含 `contentHash`，新集合记录数为 0。
3. 部署 `knowledge_chunks.index.json` 中的唯一索引。HBuilderX 数据库初始化功能会读取 index/schema 文件，但也可能包含已有 init_data；**不要直接执行整个 database 目录的全量初始化**。若当前版本可选集合，只选择 knowledge_chunks 并核对预览无其他集合、无初始化数据。若无法单独选择，直接在控制台 knowledge_chunks → 索引 → 新建：名称 `knowledge_id_unique`、字段 `knowledgeId`、升序、唯一开启、稀疏关闭。确认索引已成功建成；不是只看到本地文件就算部署完成。
4. 右键 `cloudfunctions/rag` → “上传部署”，确认打包包含 `indexer.js` 和 `resources/` 两个 JSON。成功后确认远程 rag 超时设置为 120 秒。
5. 在 rag 的远程环境变量中确认下表四项，保存。管理函数无需配置这些密钥；不创建真实 .env 文件。
6. 右键 `cloudfunctions/rag-index-admin` → “上传部署”，确认超时 120 秒。此时只部署，尚未执行索引。不要添加 URL 化或定时触发器。
7. **你准备开始真实生成向量和写库时**，对 `rag-index-admin` 右键“配置运行测试参数”，参数使用空对象 `{}`；然后选择“上传并运行云函数”。不要对 rag 选择本地运行，也不要从微信页面执行。官方的 `server` 来源用于此管理执行；如果得到 `INDEX_FORBIDDEN`，核对实际运行方式，不要通过关闭来源检查绕过。
8. 第一次完整成功应看到 `errCode: 0, total: 21, inserted: 21, updated: 0, skipped: 0, failed: 0`。控制台 knowledge_chunks 有 21 个唯一 knowledgeId，记录含 contentHash、512 项 embedding、模型名和时间戳。
9. 再手动运行一次，应看到 `inserted: 0, updated: 0, skipped: 21, failed: 0`，记录数和时间戳不变。这次代码路径不会调用 Embedding API。

| rag 远程变量 | 值 |
| --- | --- |
| DASHSCOPE_API_KEY | 你现有的北京 Model Studio 密钥，只在远程变量设置 |
| LLM_BASE_URL | 已验证可用的北京 OpenAI-compatible 基础地址，末尾不含 /embeddings |
| EMBEDDING_MODEL | qwen3.7-text-embedding-flash |
| EMBEDDING_DIMENSION | 512 |

本流程不重新初始化 categories / dishes / orders，不修改 ai 推荐逻辑。部署副本不包含 embedding，不新增 init_data 向量文件。

## 7. 本地检查

```sh
pnpm run rag:check-source
node --test tests/rag-indexer.test.cjs tests/rag-batch-embedding.test.cjs
pnpm run build:mp-weixin
git diff --check
```

测试仅使用内存数据库、固定假密钥及模拟 HTTP 响应。它们验证代码逻辑；本阶段真实云端验收结果由开发者确认，记录在本文开头及 README 中。
