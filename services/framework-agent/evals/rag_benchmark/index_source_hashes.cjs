// 纯本地只读：复用生产 canonical contentHash，不调用 buildIndex / HTTP / 云数据库。
const path = require('node:path')
const root = path.resolve(__dirname, '../../../..')
const { loadSources, contentHash } = require(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag/indexer'))
try {
  const sources = loadSources()
  process.stdout.write(JSON.stringify(Object.fromEntries(
    sources.map(source => [source.knowledgeId, contentHash(source)])
  )))
} catch {
  // 不输出原始异常、路径、知识正文或向量。
  process.stdout.write(JSON.stringify({ errCode: 'INDEX_SOURCE_AUDIT_FAILED' }))
  process.exitCode = 1
}
