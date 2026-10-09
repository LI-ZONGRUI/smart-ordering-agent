// Evaluation-only adapter. Production retrieval / selection / rendering remain unchanged.
const path = require('node:path')
const root = path.resolve(__dirname, '../../../..')
const { retrieveQuery } = require(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag/query-retrieval'))
const { answerQuery, validateAnswer } = require(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag/generator'))

function readonlyDatabase(records, dishes) {
  return {
    command: { in: values => ({ $in: values }) },
    collection(name) {
      if (!['knowledge_chunks', 'dishes'].includes(name)) throw new Error('READ_ONLY_SCOPE')
      let rows = name === 'knowledge_chunks' ? records : dishes
      let offset = 0, limit = Infinity, fields
      const query = {
        where(filter) {
          rows = rows.filter(row => Object.entries(filter).every(([key, value]) =>
            value?.$in ? value.$in.includes(row[key]) : row[key] === value))
          return query
        },
        orderBy() { return query },
        skip(value) { offset = value; return query },
        limit(value) { limit = value; return query },
        field(value) { fields = value; return query },
        async get() {
          return { data: rows.slice(offset, offset + limit).map(row => fields
            ? Object.fromEntries(Object.keys(fields).filter(k => fields[k]).map(k => [k, row[k]]))
            : structuredClone(row)) }
        }
      }
      return query
    }
  }
}

function liveHttpClient(confirmed) {
  if (!confirmed) throw new Error('LIVE_CONFIRMATION_REQUIRED')
  return { async request(url, options) {
    const endpoint = new URL(url)
    const base = new URL(process.env.LLM_BASE_URL)
    if (endpoint.protocol !== 'https:' || endpoint.origin !== base.origin ||
        options.method !== 'POST' || !['/embeddings', '/chat/completions'].some(p => endpoint.pathname.endsWith(p))) {
      throw new Error('HTTP_SCOPE_INVALID')
    }
    const response = await fetch(endpoint, {
      method: 'POST', headers: { ...options.headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(options.data), redirect: 'error', signal: AbortSignal.timeout(40000)
    })
    return { status: response.status, data: await response.text() }
  } }
}

async function execute(input, { confirmed = false, httpclient, env = process.env } = {}) {
  if (input.operation === 'validate') {
    // Pure offline contract test; no embeddings, no API calls, no expected labels used.
    try { return { status: 'ok', generation: validateAnswer(JSON.stringify(input.selection), input.knowledge, input.dishes) } }
    catch { return { status: 'error', errorCode: 'GENERATION_CONTRACT_REJECTED' } }
  }
  if (!confirmed || !['live-retrieval', 'live-generation'].includes(input.operation)) {
    return { status: 'error', errorCode: 'LIVE_CONFIRMATION_REQUIRED' }
  }
  const options = { db: readonlyDatabase(input.records, input.dishes),
    httpclient: httpclient || liveHttpClient(confirmed), env }
  const result = input.operation === 'live-generation'
    ? await answerQuery(input.query, options) : await retrieveQuery(input.query, options)
  if (result.errCode !== 0) return { status: 'error', errorCode: 'PRODUCTION_RAG_REQUEST_FAILED' }
  const rows = result.retrieval?.results || result.results
  const safe = { status: 'ok', retrieval: rows.map((r, i) => ({
    rank: i + 1, knowledgeId: r.knowledgeId, similarity: r.similarity
  })) }
  if (result.generation) {
    const { answerable, answer, dishIds, usedKnowledgeIds, evidence } = result.generation
    safe.generation = { answerable, answer, dishIds, usedKnowledgeIds, evidence }
  }
  return safe // Answer stays only in the parent process memory; report excludes it.
}

if (require.main === module) {
  let data = ''
  process.stdin.on('data', chunk => { data += chunk })
  process.stdin.on('end', async () => {
    let result
    try { result = await execute(JSON.parse(data), { confirmed: process.argv.includes('--confirm-live') }) }
    catch { result = { status: 'error', errorCode: 'BENCHMARK_BRIDGE_FAILED' } }
    process.stdout.write(JSON.stringify(result))
  })
}
module.exports = { execute, readonlyDatabase }
