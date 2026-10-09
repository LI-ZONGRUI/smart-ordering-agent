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
  assert.deepEqual(result, { status: 'error', errorCode: 'PRODUCTION_RAG_REQUEST_FAILED' })
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
