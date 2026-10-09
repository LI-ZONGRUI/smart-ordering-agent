# RAG Benchmark v1：真实知识索引准备

本阶段仅审计与本地整理。不连接远程数据库，不调用模型，不修改生产代码、知识或 Benchmark dataset。

## 1. 审计结论与可确认边界

| 项目 | 源码/本地事实 |
| --- | --- |
| 人工源 | docs/rag/knowledge-source.json |
| 部署副本 | uniCloud-aliyun/cloudfunctions/rag/resources/knowledge-source.json |
| Benchmark 快照 | services/framework-agent/evals/rag_benchmark/fixtures/knowledge.json |
| 生产存储 | 阿里云 uniCloud 的 knowledge_chunks collection；此前项目验收使用 xlimao |
| 向量位置 | 每条 knowledge_chunks 文档的 embedding 字段，与正文和 knowledgeId 在同一文档 |
| 分类字段 | **type**，不是 category；schema 没有 category 字段 |
| 知识模型约束 | qwen3.7-text-embedding-flash |
| 维度约束 | embeddingDimension=512，embedding 为 512 个数字的数组 |
| 身份 | knowledgeId；本地定义了唯一索引 knowledge_id_unique |
| 源版本 | 21 条 sourceVersion 都是整数 1，verified 都是 true |

三份知识文件逐字节 SHA-256 相同：

```text
f341c287c97056b4766fd514532de31fc8a2b5cd0a3e76641283192fcd04f0a6
```

description=6、taste=7、ingredients=8；dish=20、restaurant=1。

知识身份如下（不是 Benchmark case 或 Holdout 标签）：

| dishId | knowledgeIds |
| --- | --- |
| dish-1 | dish-1-description、dish-1-taste、dish-1-ingredients |
| dish-2 | dish-2-description、dish-2-taste、dish-2-ingredients |
| dish-3 | dish-3-description、dish-3-taste、dish-3-ingredients |
| dish-4 | dish-4-taste、dish-4-ingredients |
| dish-5 | dish-5-description、dish-5-ingredients |
| dish-6 | dish-6-description、dish-6-ingredients |
| dish-7 | dish-7-description、dish-7-taste、dish-7-ingredients |
| dish-8 | dish-8-taste、dish-8-ingredients |
| null（restaurant） | restaurant-spicy-level-definitions |

所有 dishId 与冻结 dishes 快照中的真实 ID 匹配。菜品的 categoryId 属于菜单分类，不是 knowledge_chunks 的分类字段。
知识内容不包含实时价格、销量或状态。

**云端当前记录数、唯一索引实际状态、是否存在旧模型/重复/失效向量，本轮不能确认。**
项目此前记录首次 inserted=21、二次 skipped=21，这不是本轮对云数据库的重新读取。
当前没有取得真实导出，不以本地结构/数量或过去 skip 统计替代真实向量检查。

## 2. 当前 Indexer 与已有导出能力

- Indexer 按 knowledgeId 读取现有记录；比较 sourceVersion/contentHash/model/dimension/verified 决定 skip 或重建。
- contentHash 是生产 indexer.sourceContent 的固定字段 JSON SHA-256：包括 ID、scope、dishId、type、title、text、sourceType、归一化 sourceFields。
  sourceVersion 单独比较；真实 Embedding 请求仅发送 text。
- Batch 响应依据 item.index 回到对应源记录，然后正文/元数据/向量一起写入；更新保留原记录身份。
- orphan 只报告，不删除；历史重复 ID 会触发预检失败。
- **skip 不读取并校验向量正文**，因此不能用 skip=21 证明所有向量目前仍完整。
- Retriever 只读 verified 记录，再验证模型、维度、finite number、非零范数与重复 ID；不修复损坏记录。

现有 testEmbedding / testBatchEmbedding 只返回短 preview；testRetrieval 返回 Top-3，且会调用 Query Embedding。
rag-index-admin 调用 Indexer，可能发起 Embedding 或写库；它不是导出工具。
源码中没有可直接获取 21 条完整向量的导出 endpoint，本轮不增加或部署云函数。

## 3. 你需要做的最小远程操作

由你本人登录当前 uniCloud 控制台，进入正确阿里云服务空间的 **云数据库 → knowledge_chunks**：

导出前先按下一节建立权限为 0700 的 `.local` 目录。保存/解压时选择该目录；不要让下载文件落到公开同步目录。

1. 只查看这一张 collection，核对显示的记录数量；不要打开 orders 或导出整个数据库。
2. 如果当前控制台版本提供记录导出功能，使用现有功能导出 **全部文档的完整 JSON / JSONL**，不能只导出列表预览。
   若得到压缩包，由你在本地解压并选择 knowledge_chunks 的数据文件。
3. 若没有可用导出功能，但文档详情可显示完整 JSON，可只读复制 21 条文档并组成 JSON 数组。
   不点击保存、编辑提交、删除、初始化或重建索引。必须保留每条完整 512 项 embedding，不能复制省略号或短 preview。
4. 如果控制台不能提供完整向量，停止并反馈实际可用导出格式/界面。当前源码没有另一条已验证的完整导出途径，不能绕过权限或假设 endpoint。
5. 将结果仅保存在下面的私有目录；不要将完整 JSON 粘贴到公共聊天、日志或 GitHub。

本项目中没有账号凭证或已授权的本地数据库连接。因此 Codex 本轮不执行上述操作；不假装已从控制台导出成功。
无需重新部署云函数，无需新增数据库权限或运行 Indexer。

## 4. 本地准备命令

在 services/framework-agent 目录执行：

```bash
mkdir -p evals/rag_benchmark/.local
chmod 700 evals/rag_benchmark/.local
```

将实际导出保存为：

```text
evals/rag_benchmark/.local/knowledge-chunks-export.json
```

接受一个 JSON 数组或每行一个完整对象的 JSONL，不接受 CSV、data 包装对象、Mongo shell 表达式或被截断的向量。
JSON 原文不允许 NaN/Infinity 或重复 object key。数据库 _id、createTime、updateTime 可存在，但不会带入规范化索引。
其他非知识字段直接拒绝，不能夹带订单/客户数据。

只检查源知识，无需真实导出：

```bash
PYTHONPATH=. .venv/bin/python -m evals.rag_benchmark.prepare_index audit-source
```

收到真实文件后，声明它来自你确认的 knowledge_chunks 导出：

```bash
PYTHONPATH=. .venv/bin/python -m evals.rag_benchmark.prepare_index prepare \
  --input evals/rag_benchmark/.local/knowledge-chunks-export.json \
  --source-space xlimao \
  --confirm-source
```

`--source-space` 必须填你实际导出的空间名；不会自动推断。`--confirm-source` 是人工来源声明，不是权限认证或签名。
没有声明、没有真实文件或校验失败，不生成正式索引/manifest。

成功后：

```bash
PYTHONPATH=. .venv/bin/python -m evals.rag_benchmark.prepare_index check
```

检查输出只显示数量、模型、维度、版本、哈希和 runnerLoadPassed，不打印知识原文、完整向量或配置秘密。
成功意味着本地结构、对应关系与原文件一致；不表示执行过 Dev live。

## 5. 校验与最终文件

工具只使用本地文件和 Node 的纯 source/hash 函数，**不调用 buildIndex、HTTP、Gateway 或数据库**。

校验：

- 恰好 21 条、所有 source IDs 完全覆盖且唯一。
- 所有源字段逐项与冻结知识相同，包含正文/标题/来源定位/版本/verified。
- contentHash 必须匹配生产的真实 canonical 算法；不自动补 hash 或改正文。
- embeddingModel 逐条一致，embeddingDimension 为整数 512，数组严格 512 项。
- 每项为有限数字，排除 bool、null、NaN、Infinity、零向量。
- 依据 knowledgeId 映射向量；导出顺序不同不会把向量配错知识。
- 不过滤 orphan/unverified/旧模型，也不从多条重复记录中随意挑一条；出现这些情况即拒绝，交由人工判断。
- 生成前调用现有 schema.load_index，确认现有 runner 可以原样读取。

全部通过后仅生成：

```text
.local/knowledge-index.json
.local/knowledge-index-manifest.json
```

索引只包含源知识字段、contentHash、embedding 和模型/维度。

manifest 兼容原 runner 的五个必需字段，并增加：

- recordCount、按源顺序的 knowledgeIds、sourceVersion。
- provenance.collection/sourceSpace：用户声明的实际导出位置。
- sourceExportFile/sourceExportSha256/sourceExportFormat：原导出文件的本地追溯。
- preparedAt：**本地整理时间**，不冒充未知的云端导出时间或索引生成时间。
- sourceAttestation：人工确认来源，明确不是 provider proof。

最终文件、原导出文件 SHA-256 和知识快照 SHA-256 分别校验。
manifest 元数据也会核对 count/IDs/version/原导出对应关系。
源字段 hash、记录 metadata 和来源声明能检查数据漂移，但不数学证明某条向量确实由该模型、该文本生成。
在不重新 Embedding 的约束下，生成过程的真实性依赖你从已经验收的真实索引取得导出。

目录权限 0700；原导出及最终文件为 0600。既有结果不覆盖；两文件安装发生异常时清理本次已安装文件，避免半成品冒充完整结果。
原始导出需要保留，用于之后 check 的追溯校验；全部文件均 Git ignored，不进入 GitHub。

## 6. 当前状态与回归边界

本轮源知识三份快照校验通过，但尚未取得真实导出，因此尚无正式 index checksum、无真实 manifest，不能执行 Dev live。
不会创建空索引/占位 manifest，不用单元测试向量代替真实导出。

单元测试可以使用明确标识的确定性向量测试格式，只写入隔离的临时目录，不写入真实 .local、不宣称检索准确率。

本轮测试命令应排除会读取 Holdout 的完整性测试：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python -B -m pytest \
  -p no:cacheprovider tests/test_rag_index_preparation.py tests/test_rag_benchmark.py \
  -k 'not frozen_integrity_counts_only' -q
node --test ../../tests/rag-*.test.cjs
.venv/bin/ruff check .
.venv/bin/ruff format --check .
uv lock --check --offline
```

该命令不运行模型或 Holdout；不会调用 verify_frozen() 读取冻结 RAG Holdout。

### 本轮验证结果

- 准备工具离线测试：43 项通过。
- 加上既有 Benchmark 的非 Holdout 测试：102 项通过；明确排除 1 项会读取冻结 Holdout 的完整性测试。
- JS bridge / 现有 RAG / Evidence-first：395 项通过。
- Ruff check、format check、uv offline lock check、git diff --check 通过。
- 25 个受保护生产/知识/既有 Benchmark 文件哈希不变；本轮未读取任何 Holdout case 内容。
- 源知识 SHA 与部署副本/Benchmark 快照一致；真实 index SHA 尚不可计算。
- `.local` 当前为空且权限为 0700，三个导出/索引文件名均被 Git 忽略。
- 没有远程调用、真实向量获取、Embedding 重算、数据库写入或部署。
