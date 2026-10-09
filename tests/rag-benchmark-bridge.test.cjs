const { test } = require('node:test')
const assert = require('node:assert/strict')
const { execute, readonlyDatabase } = require('../services/framework-agent/evals/rag_benchmark/bridge.cjs')
const source = require('../services/framework-agent/evals/rag_benchmark/fixtures/knowledge.json')
const dishes = require('../services/framework-agent/evals/rag_benchmark/fixtures/dishes.json')

// Tiny synthetic vectors exercise wiring only; they never produce a benchmark accuracy report.
const rows = source.map((s, i) => ({ ...s, _id: String(i),
  embedding: [i === 0 ? 1 : 0, i === 0 ? 0 : 1, ...Array(510).fill(0)],
  embeddingModel: 'qwen3.7-text-embedding-flash', embeddingDimension: 512 }))
const env = { DASHSCOPE_API_KEY: 'unit-test-not-a-real-credential',
  LLM_BASE_URL: 'https://example.invalid/compatible-mode/v1',
  EMBEDDING_MODEL: 'qwen3.7-text-embedding-flash', EMBEDDING_DIMENSION: '512',
  RAG_LLM_MODEL: 'qwen3.8-flash' }

function fakeHttp(selection) {
  const requests = []
  return { requests, async request(url, options) {
    requests.push({ url, body: options.data })
    if (url.endsWith('/embeddings')) return { status: 200, data: JSON.stringify({ data: [
      { index: 0, embedding: rows[0].embedding }
    ] }) }
    return { status: 200, data: JSON.stringify({ choices: [{ finish_reason: 'stop',
      message: { content: JSON.stringify(selection) } }] }) }
  } }
}

test('live path refuses confirmation omission, even with an injected client', async () => {
  const httpclient = { request() { throw new Error('must not execute') } }
  assert.equal((await execute({ operation: 'live-generation' }, { httpclient })).errorCode,
    'LIVE_CONFIRMATION_REQUIRED')
})

test('retrieval reuses production exact search and returns no vectors', async () => {
  const httpclient = fakeHttp()
  const result = await execute({ operation: 'live-retrieval', query: 'unit-test-query',
    records: rows, dishes }, { confirmed: true, httpclient, env })
  assert.equal(result.status, 'ok')
  assert.equal(result.retrieval.length, 3)
  assert.equal(result.retrieval[0].knowledgeId, rows[0].knowledgeId)
  assert.equal(result.retrieval[0].similarity, 1)
  assert.equal(httpclient.requests.length, 1)
  assert.equal(httpclient.requests[0].body.input, 'unit-test-query')
  assert.equal(JSON.stringify(result).includes('embedding'), false)
})

test('generation calls production renderer; labels and vectors never enter model messages', async () => {
  const selected = { answerable: true, dishIds: ['dish-1'], usedKnowledgeIds: [rows[0].knowledgeId] }
  const httpclient = fakeHttp(selected)
  const result = await execute({ operation: 'live-generation', query: 'unit-test-query',
    records: rows, dishes, expected: 'this label must not enter execution' },
  { confirmed: true, httpclient, env })
  assert.equal(result.generation.answer, rows[0].text)
  assert.deepEqual(Object.keys(result.generation), ['answerable', 'answer', 'dishIds', 'usedKnowledgeIds', 'evidence'])
  assert.equal(httpclient.requests.length, 2)
  const messages = JSON.stringify(httpclient.requests[1].body.messages)
  assert.equal(messages.includes('this label must not'), false)
  assert.equal(messages.includes('"embedding"'), false)
  assert.equal(messages.includes('"similarity"'), false)
  assert.equal(JSON.stringify(result).includes('embedding'), false)
})

test('upstream error is sanitized, not raw provider metadata', async () => {
  const httpclient = { async request() { throw new Error('private-provider-error') } }
  const result = await execute({ operation: 'live-generation', query: 'unit-test-query', records: rows, dishes },
    { confirmed: true, httpclient, env })
  assert.equal(result.status, 'error')
  assert.equal(result.errorCode, 'PRODUCTION_RAG_REQUEST_FAILED')
  assert.equal(result.diagnostics.failureStage, 'QUERY_EMBEDDING')
  assert.equal(result.diagnostics.retrievalCompleted, false)
  assert.equal(JSON.stringify(result).includes('private-provider-error'), false)
})

test('unknown/free text selection is rejected by unchanged production contract', async () => {
  const result = await execute({ operation: 'validate', selection: {
    answerable: true, dishIds: ['dish-4'], usedKnowledgeIds: ['dish-4-taste'], answer: '解腻'
  }, knowledge: source, dishes: dishes.map(d => ({ ...d, dishId: d._id })) })
  assert.equal(result.status, 'error')
})

test('local database adapter offers no mutation methods', () => {
  const collection = readonlyDatabase(rows, dishes).collection('dishes')
  for (const name of ['add', 'update', 'remove', 'set']) assert.equal(collection[name], undefined)
  assert.throws(() => readonlyDatabase(rows, dishes).collection('orders'))
})

// All HTTP responses below are offline test fixtures; never invoke a live provider.
async function failedAt(stage, { timeout = false } = {}) {
  const client = fakeHttp({ answerable: true, dishIds: ['dish-1'], usedKnowledgeIds: [rows[0].knowledgeId] })
  const original = client.request.bind(client)
  client.request = async (url, options) => {
    if ((stage === 'embedding' && url.endsWith('/embeddings')) ||
        (stage === 'generation' && url.endsWith('/chat/completions'))) {
      const error = new Error('private-provider-body secret-key internal-path')
      if (timeout) error.name = 'TimeoutError'
      throw error
    }
    return original(url, options)
  }
  const checkpoints = []
  const result = await execute({ operation: 'live-generation', query: 'offline', records: rows, dishes },
    { confirmed: true, httpclient: client, env, onRetrieval: r => checkpoints.push(r) })
  return { result, checkpoints }
}

test('generation request failure retains observed Top-3 and publishes checkpoint', async () => {
  const { result, checkpoints } = await failedAt('generation')
  assert.equal(result.status, 'error')
  assert.equal(result.diagnostics.failureStage, 'GENERATION_REQUEST')
  assert.equal(result.diagnostics.generationState, 'NOT_OBSERVED')
  assert.equal(result.diagnostics.retrievalCompleted, true)
  assert.deepEqual(result.retrieval, checkpoints[0])
  assert.equal(result.retrieval.length, 3)
  assert.equal('generation' in result, false)
  assert.equal(JSON.stringify(result).includes('private-provider'), false)
})

test('embedding failure does not invent a completed retrieval', async () => {
  const { result, checkpoints } = await failedAt('embedding')
  assert.equal(result.diagnostics.failureStage, 'QUERY_EMBEDDING')
  assert.equal(result.diagnostics.retrievalCompleted, false)
  assert.equal(checkpoints.length, 0)
  assert.equal('retrieval' in result, false)
  assert.equal('generation' in result, false)
})

for (const stage of ['embedding', 'generation']) {
  test(`${stage} timeout classified by actual TimeoutError, not exception wording`, async () => {
    const { result } = await failedAt(stage, { timeout: true })
    assert.equal(result.diagnostics.failureStage, 'TIMEOUT')
    assert.equal(result.diagnostics.timeoutScope, 'HTTP_REQUEST')
    assert.equal(result.diagnostics.failedOperation,
      stage === 'embedding' ? 'QUERY_EMBEDDING' : 'GENERATION_REQUEST')
  })
}

test('invalid candidate vector is a retrieval error, not an embedding failure', async () => {
  const invalid = structuredClone(rows)
  invalid[0].embedding = [1]
  const checkpoints = []
  const result = await execute({ operation: 'live-generation', query: 'offline', records: invalid, dishes },
    { confirmed: true, httpclient: fakeHttp(), env, onRetrieval: r => checkpoints.push(r) })
  assert.equal(result.diagnostics.failureStage, 'RETRIEVAL')
  assert.equal(result.diagnostics.errorCategory, 'DATA_INVALID')
  assert.equal(checkpoints.length, 0)
  assert.equal('retrieval' in result, false)
})

for (const selection of [{ answerable: 'invalid' },
  { answerable: true, dishIds: ['dish-1'], usedKnowledgeIds: ['unknown'] }]) {
  test('invalid generation JSON/IDs preserves retrieval without fabricating generation', async () => {
    const result = await execute({ operation: 'live-generation', query: 'offline', records: rows, dishes },
      { confirmed: true, httpclient: fakeHttp(selection), env })
    assert.equal(result.diagnostics.failureStage, 'GENERATION_VALIDATION')
    assert.equal(result.diagnostics.retrievalCompleted, true)
    assert.equal(result.retrieval.length, 3)
    assert.equal('generation' in result, false)
  })
}

test('unknown runtime failure is UNKNOWN and never leaks arbitrary error text', async () => {
  const result = await execute({ operation: 'live-generation', query: 'offline', records: rows, dishes },
    { confirmed: true, httpclient: fakeHttp(), env, onRetrieval() { throw new Error('private-path') } })
  assert.equal(result.diagnostics.failureStage, 'UNKNOWN')
  assert.equal(JSON.stringify(result).includes('private-path'), false)
  assert.equal(result.diagnostics.retrievalCompleted, true)
})

test('generation keeps one real embedding request and one generation request per case', async () => {
  const client = fakeHttp({ answerable: false, dishIds: [], usedKnowledgeIds: [] })
  const result = await execute({ operation: 'live-generation', query: '  offline  ', records: rows, dishes },
    { confirmed: true, httpclient: client, env })
  assert.equal(result.status, 'ok')
  assert.deepEqual(client.requests.map(r => new URL(r.url).pathname.split('/').pop()),
    ['embeddings', 'completions'])
  assert.equal(result.diagnostics.generationState, 'COMPLETED')
})

for (const stage of ['embedding', 'generation']) {
  test(`${stage} HTTP error reports only fixed safe category`, async () => {
    const client = fakeHttp()
    const original = client.request.bind(client)
    client.request = async (url, options) => {
      if (url.endsWith(stage === 'embedding' ? '/embeddings' : '/chat/completions')) {
        return { status: 503, data: 'raw-provider-message private-key' }
      }
      return original(url, options)
    }
    const result = await execute({ operation: 'live-generation', query: 'offline', records: rows, dishes },
      { confirmed: true, httpclient: client, env })
    assert.equal(result.diagnostics.failureStage,
      stage === 'embedding' ? 'QUERY_EMBEDDING' : 'GENERATION_REQUEST')
    assert.equal(result.diagnostics.errorCategory, 'HTTP_ERROR')
    assert.equal(JSON.stringify(result).includes('raw-provider-message'), false)
  })
}

test('invalid provider generation envelope preserves retrieval', async () => {
  const client = fakeHttp()
  const original = client.request.bind(client)
  client.request = async (url, options) => url.endsWith('/chat/completions')
    ? { status: 200, data: 'not valid JSON private-provider' } : original(url, options)
  const result = await execute({ operation: 'live-generation', query: 'offline', records: rows, dishes },
    { confirmed: true, httpclient: client, env })
  assert.equal(result.diagnostics.failureStage, 'GENERATION_VALIDATION')
  assert.equal(result.diagnostics.errorCategory, 'RESPONSE_INVALID')
  assert.equal('generation' in result, false)
  assert.equal(result.retrieval.length, 3)
  assert.equal(JSON.stringify(result).includes('private-provider'), false)
})

test('live fact error before generation still retains successful retrieval; phase is UNKNOWN', async () => {
  const invalid = structuredClone(dishes)
  invalid[0].price = 'invalid'
  const result = await execute({ operation: 'live-generation', query: 'offline', records: rows, dishes: invalid },
    { confirmed: true, httpclient: fakeHttp(), env })
  assert.equal(result.diagnostics.failureStage, 'UNKNOWN')
  assert.equal(result.diagnostics.errorCategory, 'LIVE_FACTS_INVALID')
  assert.equal(result.diagnostics.retrievalCompleted, true)
  assert.equal(result.diagnostics.generationState, 'NOT_STARTED')
})
