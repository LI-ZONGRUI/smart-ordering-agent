# knowledge_chunks 结构设计（更新至 V4.2.4）

V4.2.2 已定义 schema / index；V4.2.4 新增 `contentHash` 和可重复运行的索引代码。开发者已确认真实环境首次插入 21 条、二次全部 skip，V4.2 已完成；没有检索实现。本次收尾未再次执行远程索引。部署与运行步骤见 [INDEXING.md](./INDEXING.md)。

## 源知识与派生数据

`knowledge-source.json → 自动同步部署副本 → Embedding / Indexing → knowledge_chunks`

- `docs/rag/knowledge-source.json` 是人工维护的源知识。当前冻结的 V1 有 21 条，全部 `verified: true`，`sourceVersion: 1`。
- `knowledge_chunks` 保存源知识的已审核内容、来源信息及其向量，是可重新生成的派生索引。
- 以后更改知识，先修改源文件、重新审核并更新对应 `sourceVersion`，再重新索引。不要直接修改集合正文后反向当作源知识。
- 本阶段未改动冻结的知识源及其审核说明。实时价格、售卖状态、销量继续由 dishes 提供，不加入知识正文。

## 字段约定

| 字段 | 类型 / 约束 | 用途 |
| --- | --- | --- |
| `_id` | 字符串，新记录使用 knowledgeId 的 SHA-256 前 32 位 | 数据库记录 ID，更新保留原值 |
| `knowledgeId` | 非空字符串、唯一 | 与源知识一一对应 |
| `scope` | `dish` / `restaurant` | 知识范围 |
| `dishId` | 非空字符串或空值 | dish 级必须有真实菜品 ID；restaurant 级原样保留源文件中的 `null` |
| `type` | `description` / `taste` / `ingredients` | 知识类型 |
| `title`、`text` | 非空字符串 | 原样保留源标题与正文 |
| `sourceType` | `project-data` | 来源类型 |
| `sourceFields` | 非空对象数组 | 原样保留 `file`、`fields` 和可选 `recordId`，不是字符串数组 |
| `sourceVersion` | 正整数，当前为 1 | 识别源知识版本 |
| `verified` | 必须是布尔值 `true` | 仅接受人工审核通过的知识，不设置自动通过的默认值 |
| `contentHash` | 64 位小写十六进制 SHA-256 | 固定顺序内容 JSON 的 hash，规则见 INDEXING.md |
| `embedding` | 数字数组，长度严格为 512 | 模型返回并通过校验的向量 |
| `embeddingModel` | `qwen3.7-text-embedding-flash` | 固定本版索引模型 |
| `embeddingDimension` | 整数 512 | 固定本版索引维度 |
| `createTime`、`updateTime` | timestamp，毫秒时间戳 | 索引流程设置；update 保留 createTime，skip 两者都不改 |

## 校验边界

按 [uniCloud DB Schema 官方说明](https://doc.dcloud.net.cn/uniCloud/schema.html)，数组长度使用 `minLength` / `maxLength`。本版都设为 512，`arrayType: double` 表达数字元素。

`dishId` 不列入全局 `required`，以允许 restaurant 级的空值；`fieldRules` 对 dish 级执行条件必填检查，非空值按字符串规则校验。`foreignKey` 声明与 `dishes._id` 的关系，不代表数据库会自动检查菜品是否存在。

DB Schema 校验只在 JQL 数据操作中生效，普通 `uniCloud.database()` 写入及控制台直接编辑不能依赖这些约束。当前索引器在写入前校验审核状态、字段结构、真实 dishId、配置维度和所有向量元素的有限性。模型名读取环境变量；当前部署应保持 `qwen3.7-text-embedding-flash`，未来更换模型需同步审核 schema 的枚举约定。本次未进行云端 schema 校验测试。

客户端普通用户的直接读、写、删除、计数权限均关闭，后续访问通过云端受控逻辑完成。

## 索引

仅声明 `knowledge_id_unique`：对 `knowledgeId` 建非稀疏唯一升序索引，防止同一知识重复入库，方便未来按知识 ID 更新。数据库还自带 `_id` 索引。暂不额外声明 `dishId` / `type` 索引，等实际查询需求确定后再考虑。

`embedding` 不建普通索引：普通字段索引不能完成向量相似度查询，对 512 个数建立普通数组索引会增加存储和写入成本。本阶段没有向量索引或检索实现。

在新服务空间中仍需通过 HBuilderX / 控制台部署 schema 和索引；前端构建不会自动部署数据库。本项目的真实索引验收结果见 [INDEXING.md](./INDEXING.md)。
