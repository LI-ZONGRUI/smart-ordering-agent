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

const ERROR_MAP = {
  RETRIEVAL_CONFIG_INVALID: ['QUERY_EMBEDDING', 'CONFIG_INVALID'],
  RETRIEVAL_QUERY_REQUEST_FAILED: ['QUERY_EMBEDDING', 'REQUEST_FAILED'],
  RETRIEVAL_QUERY_HTTP_ERROR: ['QUERY_EMBEDDING', 'HTTP_ERROR'],
  RETRIEVAL_QUERY_RESPONSE_INVALID: ['QUERY_EMBEDDING', 'RESPONSE_INVALID'],
  RETRIEVAL_DATABASE_FAILED: ['RETRIEVAL', 'DATA_INVALID'],
  RETRIEVAL_DATA_INVALID: ['RETRIEVAL', 'DATA_INVALID'],
  RETRIEVAL_EMPTY: ['RETRIEVAL', 'DATA_INVALID'],
  RAG_GENERATION_CONFIG_MISSING: ['GENERATION_REQUEST', 'CONFIG_INVALID'],
  RAG_GENERATION_CONFIG_INVALID: ['GENERATION_REQUEST', 'CONFIG_INVALID'],
  RAG_GENERATION_REQUEST_FAILED: ['GENERATION_REQUEST', 'REQUEST_FAILED'],
  RAG_GENERATION_HTTP_ERROR: ['GENERATION_REQUEST', 'HTTP_ERROR'],
  RAG_GENERATION_RESPONSE_INVALID: ['GENERATION_VALIDATION', 'RESPONSE_INVALID'],
  RAG_GENERATION_IDS_INVALID: ['GENERATION_VALIDATION', 'IDS_INVALID'],
  RAG_LIVE_FACTS_CHANGED: ['GENERATION_VALIDATION', 'LIVE_FACTS_CHANGED'],
  // 此错误既可能发生在请求前，也可能在生成后复核，不能推测具体位置。
  RAG_LIVE_DISH_FAILED: ['UNKNOWN', 'LIVE_FACTS_INVALID']
}
function durationBucket(ms) {
  return ms < 1000 ? 'LT_1S' : ms < 5000 ? '1_TO_5S' : ms < 15000 ? '5_TO_15S'
    : ms < 40000 ? '15_TO_40S' : ms < 100000 ? '40_TO_100S' : 'GE_100S'
}
function safeRanks(result) {
  return result.results.map((r, i) => ({ rank: i + 1,
    knowledgeId: r.knowledgeId, similarity: r.similarity }))
}

async function execute(input, { confirmed = false, httpclient, env = process.env,
  onRetrieval = () => {} } = {}) {
  if (input.operation === 'validate') {
    // Pure offline contract test; no embeddings, no API calls, no expected labels used.
    try { return { status: 'ok', generation: validateAnswer(JSON.stringify(input.selection), input.knowledge, input.dishes) } }
    catch { return { status: 'error', errorCode: 'GENERATION_CONTRACT_REJECTED' } }
  }
  if (!confirmed || !['live-retrieval', 'live-generation'].includes(input.operation)) {
    return { status: 'error', errorCode: 'LIVE_CONFIRMATION_REQUIRED' }
  }
  const started = Date.now()
  let retrieval, generationRequested = false, timedOutOperation
  let embeddingResponse, embeddingRequest
  // 仅在本次 case 内存中保存真实 HTTP 响应，供 answerQuery 的内部检索复用。
  // 不增加第二次 Embedding 请求，也不替换生产计算/Prompt/Generation；结束后不持久化。
  const transport = httpclient || liveHttpClient(confirmed)
  const observedHttp = { async request(url, options) {
    const isEmbedding = url.endsWith('/embeddings')
    if (isEmbedding && embeddingResponse !== undefined) {
      if (embeddingRequest !== JSON.stringify(options.data)) throw new Error('REPLAY_INPUT_CHANGED')
      return embeddingResponse
    }
    if (!isEmbedding) generationRequested = true
    try {
      const response = await transport.request(url, options)
      if (isEmbedding) {
        embeddingResponse = response
        embeddingRequest = JSON.stringify(options.data)
      }
      return response
    } catch (error) {
      // fetch 的固定超时类型才可确认为 HTTP timeout；任意异常文案不作分类依据。
      if (error?.name === 'TimeoutError') {
        timedOutOperation = isEmbedding ? 'QUERY_EMBEDDING' : 'GENERATION_REQUEST'
      }
      throw error
    }
  } }
  function finish(status, result, errorCode) {
    const [stage, category] = Object.hasOwn(ERROR_MAP, errorCode)
      ? ERROR_MAP[errorCode] : ['UNKNOWN', 'UNKNOWN']
    const diagnostics = {
      failureStage: status === 'ok' ? 'NONE' : timedOutOperation ? 'TIMEOUT' : stage,
      errorCategory: status === 'ok' ? 'NONE' : timedOutOperation ? 'TIMEOUT' : category,
      timeoutScope: timedOutOperation ? 'HTTP_REQUEST' : 'NONE',
      failedOperation: timedOutOperation || 'NONE',
      retrievalCompleted: Boolean(retrieval),
      generationState: result?.generation ? 'COMPLETED'
        : generationRequested ? 'NOT_OBSERVED' : 'NOT_STARTED',
      durationBucket: durationBucket(Date.now() - started)
    }
    return { status, ...(status === 'error' ? { errorCode: 'PRODUCTION_RAG_REQUEST_FAILED' } : {}),
      ...(retrieval ? { retrieval } : {}),
      ...(result?.generation ? { generation: result.generation } : {}), diagnostics }
  }
  try {
    const options = { db: readonlyDatabase(input.records, input.dishes), httpclient: observedHttp, env }
    // 先通过未修改的 production retrieveQuery 确认真实检索完成，再发安全 checkpoint。
    const query = input.operation === 'live-generation' && typeof input.query === 'string'
      ? input.query.trim() : input.query
    const retrieved = await retrieveQuery(query, options)
    if (retrieved.errCode !== 0) return finish('error', null, retrieved.errCode)
    retrieval = safeRanks(retrieved)
    onRetrieval(retrieval)
    if (input.operation === 'live-retrieval') return finish('ok', null)
    // answerQuery 仍走完整生产路径；仅对同一输入复用刚成功的真实 Embedding 响应。
    const result = await answerQuery(input.query, options)
    if (result.errCode !== 0) return finish('error', null, result.errCode)
    const { answerable, answer, dishIds, usedKnowledgeIds, evidence } = result.generation
    return finish('ok', { generation: { answerable, answer, dishIds, usedKnowledgeIds, evidence } })
  } catch {
    return finish('error', null) // 不返回异常 message、stack、HTTP headers 或响应正文。
  }
}

if (require.main === module) {
  let data = ''
  process.stdin.on('data', chunk => { data += chunk })
  process.stdin.on('end', async () => {
    let result
    try { result = await execute(JSON.parse(data), {
      confirmed: process.argv.includes('--confirm-live'),
      // 单行白名单 checkpoint，让父进程超时/非零退出时仍可保留已完成检索。
      onRetrieval: retrieval => process.stdout.write(JSON.stringify({
        kind: 'retrieval_checkpoint', retrieval
      }) + '\n')
    }) }
    catch { result = { status: 'error', errorCode: 'BENCHMARK_BRIDGE_FAILED' } }
    process.stdout.write(JSON.stringify(result))
  })
}
module.exports = { execute, readonlyDatabase, durationBucket }
