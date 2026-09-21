// 唯一人工源是 docs/rag/knowledge-source.json；本脚本只生成/检查部署资源。
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const { validateSources } = require('../uniCloud-aliyun/cloudfunctions/rag/indexer')

const root = path.resolve(__dirname, '..')
const sourcePath = 'docs/rag/knowledge-source.json'
const raw = fs.readFileSync(path.join(root, sourcePath))
const sources = JSON.parse(raw.toString('utf8'))
validateSources(sources)
const folder = path.join(root, 'uniCloud-aliyun/cloudfunctions/rag/resources')
const manifest = Buffer.from(JSON.stringify({
  generated: true,
  sourcePath,
  sha256: crypto.createHash('sha256').update(raw).digest('hex'),
  count: sources.length
}, null, 2) + '\n')

const files = [['knowledge-source.json', raw], ['knowledge-source.manifest.json', manifest]]
if (process.argv.includes('--check')) {
  for (const [name, expected] of files) {
    const target = path.join(folder, name)
    if (!fs.existsSync(target) || !fs.readFileSync(target).equals(expected)) {
      console.error('RAG 部署副本未同步，请执行 pnpm run rag:sync-source 后重新检查。')
      process.exit(1)
    }
  }
  console.log(`RAG 部署副本校验通过：${sources.length} 条，内容与人工源逐字节一致。`)
} else {
  fs.mkdirSync(folder, { recursive: true })
  for (const [name, data] of files) fs.writeFileSync(path.join(folder, name), data)
  console.log(`已同步 ${sources.length} 条知识到 rag/resources；未修改源文件，未调用 API。`)
}
