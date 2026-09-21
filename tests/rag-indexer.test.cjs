const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { buildIndex, contentHash, loadSources, BATCH_SIZE } = require('../uniCloud-aliyun/cloudfunctions/rag/indexer')
const sources = require('../docs/rag/knowledge-source.json')
const clone = value => structuredClone(value)
const env = { DASHSCOPE_API_KEY: 'test-only-secret', LLM_BASE_URL: 'https://example.invalid/v1',
  EMBEDDING_MODEL: 'qwen3.7-text-embedding-flash', EMBEDDING_DIMENSION: '512' }
const fingerprint = text => [...text].reduce((sum, char) => sum + char.codePointAt(0), 0) / 1000000

// 全部测试使用内存数据库和模拟 HTTP，不读取真实密钥，不调用远程服务。
function setup() {
  const app = { rows: [], requests: [], failIds: new Set(), uncertainIds: new Set(),
    dishes: new Set(sources.filter(x => x.dishId).map(x => x.dishId)), time: 1000 }
  const matches = (row, filter) => Object.entries(filter).every(([key, value]) => {
    if (value && typeof value === 'object' && 'exists' in value) return (row[key] !== undefined) === value.exists
    return row[key] === value
  })
  const db = {
    command: { in: values => ({ in: values }), exists: value => ({ exists: value }) },
    collection(name) {
      if (!['knowledge_chunks', 'dishes'].includes(name)) assert.fail('不应访问其他 collection')
      function query(filter = {}, offset = 0, limit = 100) {
        return {
          where: value => query(value, offset, limit),
          orderBy: () => query(filter, offset, limit),
          skip: value => query(filter, value, limit),
          limit: value => query(filter, offset, value),
          field() { return this },
          async get() {
            if (app.readFails) throw new Error('Authorization test-only-secret')
            if (name === 'dishes') return { data: filter._id.in.filter(id => app.dishes.has(id)).map(_id => ({ _id })) }
            return { data: clone(app.rows.filter(row => matches(row, filter)).sort((a,b) => a._id.localeCompare(b._id)).slice(offset, offset + limit)) }
          },
          async add(record) {
            if (app.failIds.has(record.knowledgeId)) throw new Error('Authorization test-only-secret')
            if (app.rows.some(row => row._id === record._id || row.knowledgeId === record.knowledgeId)) throw new Error('duplicate')
            app.rows.push(clone(record))
            if (app.uncertainIds.has(record.knowledgeId)) throw new Error('ack lost test-only-secret')
            return { id: record._id }
          },
          async update(record) {
            if (app.failIds.has(record.knowledgeId)) throw new Error('test-only-secret')
            const row = app.rows.find(item => matches(item, filter))
            if (!row) return { updated: 0 }
            Object.assign(row, clone(record))
            return { updated: 1 }
          },
          remove() { assert.fail('禁止删除 orphan 或其他记录') }
        }
      }
      return query()
    }
  }
  const httpclient = { async request(url, config) {
    app.requests.push({ url, config })
    if (app.networkFails) throw new Error('Authorization test-only-secret')
    if (app.response) return app.response
    const data = config.data.input.map((text, index) => ({ index, embedding: Array(512).fill(fingerprint(text)) }))
    if (app.mutate) app.mutate(data)
    let raw = JSON.stringify({ data })
    if (app.rawMutate) raw = app.rawMutate(raw)
    return { status: 200, data: raw }
  } }
  app.run = async (overrides = {}) => {
    const result = await buildIndex({ db, httpclient, env, sources: clone(sources), now: () => ++app.time, ...overrides })
    assert.ok(!JSON.stringify(result).includes('test-only-secret'))
    assert.ok(!JSON.stringify(result).includes('Authorization'))
    assert.ok(!JSON.stringify(result).includes('"embedding":'))
    assert.equal(result.inserted + result.updated + result.skipped + result.failed, result.total)
    return result
  }
  return app
}

test('部署副本逐字节匹配冻结源，manifest 校验通过', () => {
  const root = path.join(__dirname, '..')
  const original = fs.readFileSync(path.join(root, 'docs/rag/knowledge-source.json'))
  const copy = fs.readFileSync(path.join(root, 'uniCloud-aliyun/cloudfunctions/rag/resources/knowledge-source.json'))
  assert.ok(original.equals(copy))
  assert.deepEqual(loadSources(), sources)
  assert.equal(sources.length, 21)
})

test('canonical hash 忽略对象键顺序，识别 text/title/type/sourceFields 变化', () => {
  const original = sources[0]
  const reverse = Object.fromEntries(Object.entries(original).reverse())
  assert.equal(contentHash(reverse), contentHash(original))
  for (const key of ['text', 'title', 'type']) assert.notEqual(contentHash({ ...original, [key]: original[key] + ' ' }), contentHash(original))
  const changed = clone(original)
  changed.sourceFields[0].fields.push('new-field')
  assert.notEqual(contentHash(changed), contentHash(original))
})

test('21 条全新：分 10/10/1 三批，全 insert，字段完整且映射准确', async () => {
  const app = setup()
  const result = await app.run()
  assert.equal(result.errCode, 0)
  assert.equal(result.inserted, 21)
  assert.equal(BATCH_SIZE, 10)
  assert.deepEqual(app.requests.map(x => x.config.data.input.length), [10, 10, 1])
  for (const { url, config } of app.requests) {
    assert.equal(url, 'https://example.invalid/v1/embeddings')
    assert.equal(config.method, 'POST')
    assert.equal(config.data.dimensions, 512)
    assert.equal(config.data.encoding_format, 'float')
  }
  for (const record of app.rows) {
    const source = sources.find(x => x.knowledgeId === record.knowledgeId)
    for (const key of Object.keys(source)) assert.deepEqual(record[key], source[key])
    assert.equal(record.contentHash, contentHash(source))
    assert.equal(record.embedding.length, 512)
    assert.equal(record.embedding[0], fingerprint(source.text))
    assert.equal(record.createTime, record.updateTime)
  }
})

test('第二次运行 21 条 skip，零 Embedding 请求、时间戳不变', async () => {
  const app = setup()
  await app.run()
  const before = clone(app.rows)
  app.requests.length = 0
  const result = await app.run()
  assert.equal(result.skipped, 21)
  assert.equal(app.requests.length, 0)
  assert.deepEqual(app.rows, before)
})

for (const field of ['text', 'sourceVersion', 'embeddingModel', 'embeddingDimension']) {
  test(`${field} 改变：只重建一条、保留 _id 和 createTime`, async () => {
    const app = setup()
    await app.run()
    const changed = clone(sources)
    const old = clone(app.rows[0])
    if (field === 'text') changed[0].text += '（本地测试）'
    else if (field === 'sourceVersion') changed[0].sourceVersion++
    else if (field === 'embeddingModel') app.rows[0].embeddingModel = 'previous-model'
    else app.rows[0].embeddingDimension = 256
    app.requests.length = 0
    const result = await app.run({ sources: changed })
    assert.equal(result.updated, 1)
    assert.equal(result.skipped, 20)
    assert.equal(app.requests[0].config.data.input.length, 1)
    assert.equal(app.rows[0]._id, old._id)
    assert.equal(app.rows[0].createTime, old.createTime)
    assert.ok(app.rows[0].updateTime > old.updateTime)
    assert.equal(app.rows[0].embeddingDimension, 512)
  })
}

test('配置模型变化：以环境变量为准重建', async () => {
  const app = setup()
  await app.run()
  app.requests.length = 0
  const result = await app.run({ env: { ...env, EMBEDDING_MODEL: 'test-new-model' } })
  assert.equal(result.updated, 21)
  assert.ok(app.requests.every(r => r.config.data.model === 'test-new-model'))
})

test('当前配置非 512 维拒绝；不把任意维度写进本版索引', async () => {
  const app = setup()
  const result = await app.run({ env: { ...env, EMBEDDING_DIMENSION: '256' } })
  assert.equal(result.errCode, 'INDEX_CONFIG_INVALID')
  assert.equal(app.requests.length, 0)
})

test('一部分新增、一部分更新、一部分 skip', async () => {
  const app = setup()
  await app.run()
  app.rows.splice(0, 2)
  app.rows[0].contentHash = 'outdated'
  app.requests.length = 0
  const result = await app.run()
  assert.equal(result.inserted, 2)
  assert.equal(result.updated, 1)
  assert.equal(result.skipped, 18)
  assert.equal(app.requests[0].config.data.input.length, 3)
})

test('响应乱序但 index 正确：所有向量绑定到正确 knowledgeId', async () => {
  const app = setup()
  app.mutate = data => data.reverse()
  assert.equal((await app.run()).inserted, 21)
  for (const row of app.rows) assert.equal(row.embedding[0], fingerprint(row.text))
})

for (const [name, mutate, code] of [
  ['index 重复', data => { data[1].index = 0 }, 'INDEX_EMBEDDING_INDEX_INVALID'],
  ['index 缺失', data => { delete data[1].index }, 'INDEX_EMBEDDING_INDEX_INVALID'],
  ['index 非整数', data => { data[1].index = 0.5 }, 'INDEX_EMBEDDING_INDEX_INVALID'],
  ['index 负数', data => { data[1].index = -1 }, 'INDEX_EMBEDDING_INDEX_INVALID'],
  ['index 越界', data => { data[1].index = data.length }, 'INDEX_EMBEDDING_INDEX_INVALID'],
  ['数量不足', data => data.pop(), 'INDEX_EMBEDDING_RESPONSE_INVALID'],
  ['embedding 非数组', data => { data[1].embedding = null }, 'INDEX_EMBEDDING_VECTOR_INVALID'],
  ['embedding 非512维', data => data[1].embedding.pop(), 'INDEX_EMBEDDING_VECTOR_INVALID'],
  ['embedding 非数字', data => { data[1].embedding[511] = '0.1' }, 'INDEX_EMBEDDING_VECTOR_INVALID']
]) {
  test(`${name}：整批拒绝、未写入、返回 failed`, async () => {
    const app = setup()
    app.mutate = mutate
    const result = await app.run()
    assert.equal(result.errCode, 'INDEX_PARTIAL_FAILURE')
    assert.equal(result.failed, 21)
    assert.equal(result.failures[0].code, code)
    assert.equal(app.rows.length, 0)
    assert.equal(app.requests.length, 1)
  })
}

test('非有限数字拒绝', async () => {
  const app = setup()
  app.mutate = data => { data[1].embedding[511] = 'overflow' }
  app.rawMutate = raw => raw.replace('"overflow"', '1e400')
  const result = await app.run()
  assert.equal(result.failures[0].code, 'INDEX_EMBEDDING_VECTOR_INVALID')
})

test('数据库部分写失败：明确 failed，重跑只补失败项', async () => {
  const app = setup()
  app.failIds.add(sources[2].knowledgeId)
  const first = await app.run()
  assert.equal(first.errCode, 'INDEX_PARTIAL_FAILURE')
  assert.equal(first.inserted, 20)
  assert.equal(first.failed, 1)
  assert.equal(first.failures[0].knowledgeId, sources[2].knowledgeId)
  app.failIds.clear()
  app.requests.length = 0
  const second = await app.run()
  assert.equal(second.errCode, 0)
  assert.equal(second.inserted, 1)
  assert.equal(second.skipped, 20)
  assert.equal(app.requests[0].config.data.input.length, 1)
})

test('写入成功但确认丢失：本轮不宣称成功，下轮读取后 skip', async () => {
  const app = setup()
  app.uncertainIds.add(sources[0].knowledgeId)
  assert.equal((await app.run()).failed, 1)
  app.requests.length = 0
  assert.equal((await app.run()).skipped, 21)
  assert.equal(app.requests.length, 0)
})

test('更新失败保留旧记录，下轮重新 Embedding 更新', async () => {
  const app = setup()
  await app.run()
  const old = clone(app.rows[0])
  const changed = clone(sources)
  changed[0].text += '更新'
  app.failIds.add(old.knowledgeId)
  assert.equal((await app.run({ sources: changed })).failed, 1)
  assert.deepEqual(app.rows[0], old)
  app.failIds.clear()
  assert.equal((await app.run({ sources: changed })).updated, 1)
})

test('orphan 跨分页检测，只报告 ID、不删除', async () => {
  const app = setup()
  app.rows = Array.from({ length: 105 }, (_, i) => ({ _id: `orphan-${i}`, knowledgeId: `orphan-${i}` }))
  const result = await app.run()
  assert.equal(result.orphanScanComplete, true)
  assert.equal(result.orphanCount, 105)
  assert.equal(result.orphanKnowledgeIds.length, 105)
  assert.ok(result.orphanKnowledgeIds.every(id => id.startsWith('orphan-')))
  assert.equal(app.rows.length, 126)
})

test('不假设永远21条，47条分五批处理', async () => {
  const app = setup()
  const larger = Array.from({ length: 47 }, (_, i) => ({ ...clone(sources[0]), knowledgeId: `test-${i}` }))
  const result = await app.run({ sources: larger })
  assert.equal(result.inserted, 47)
  assert.deepEqual(app.requests.map(r => r.config.data.input.length), [10, 10, 10, 10, 7])
})

test('已存在重复 knowledgeId：预检失败，不请求模型', async () => {
  const app = setup()
  app.rows = [{ _id: '1', knowledgeId: sources[0].knowledgeId }, { _id: '2', knowledgeId: sources[0].knowledgeId }]
  assert.equal((await app.run()).errCode, 'INDEX_DATABASE_DUPLICATE_OR_INVALID')
  assert.equal(app.requests.length, 0)
})

test('并发插入最多产生21条；冲突不伪装成功', async () => {
  const app = setup()
  const results = await Promise.all([app.run(), app.run()])
  assert.equal(app.rows.length, 21)
  assert.equal(new Set(app.rows.map(x => x.knowledgeId)).size, 21)
  assert.ok(results.some(x => x.errCode !== 0))
})

test('同一毫秒并发更新：条件更新只允许一次成功', async () => {
  const app = setup()
  await app.run()
  const changed = clone(sources)
  changed[0].text += '更新'
  const clock = app.rows[0].updateTime
  const results = await Promise.all([
    app.run({ sources: changed, now: () => clock }),
    app.run({ sources: changed, now: () => clock })
  ])
  assert.equal(results.reduce((sum, result) => sum + result.updated, 0), 1)
  assert.equal(results.reduce((sum, result) => sum + result.failed, 0), 1)
  assert.equal(app.rows.length, 21)
  assert.ok(app.rows[0].updateTime > clock)
})

for (const kind of ['unverified', 'duplicate-source', 'missing-dish', 'read-failed']) {
  test(`预检拒绝 ${kind}，不消耗 Embedding`, async () => {
    const app = setup()
    const changed = clone(sources)
    if (kind === 'unverified') changed[0].verified = false
    if (kind === 'duplicate-source') changed[1].knowledgeId = changed[0].knowledgeId
    if (kind === 'missing-dish') app.dishes.clear()
    if (kind === 'read-failed') app.readFails = true
    const result = await app.run({ sources: changed })
    assert.notEqual(result.errCode, 0)
    assert.equal(app.requests.length, 0)
    assert.equal(app.rows.length, 0)
  })
}

for (const kind of ['network', 'http', 'json', 'api']) {
  test(`${kind} 错误安全返回，未处理项全部记 failed`, async () => {
    const app = setup()
    if (kind === 'network') app.networkFails = true
    if (kind === 'http') app.response = { status: 401, data: 'Authorization test-only-secret' }
    if (kind === 'json') app.response = { status: 200, data: 'test-only-secret' }
    if (kind === 'api') app.response = { status: 200, data: '{"error":"test-only-secret"}' }
    const result = await app.run()
    assert.equal(result.failed, 21)
    assert.equal(result.errCode, 'INDEX_PARTIAL_FAILURE')
  })
}

test('时间预算耗尽：不再调用模型，不能返回成功', async () => {
  const app = setup()
  let clock = 0
  const result = await app.run({ now: () => { clock += 90000; return clock } })
  assert.equal(result.errCode, 'INDEX_TIME_BUDGET')
  assert.equal(app.requests.length, 0)
})

test('索引云对象允许管理端/云函数来源，拒绝客户端/HTTP/缺失来源', async () => {
  const code = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag/index.obj.js'), 'utf8')
  let builds = 0
  const sandbox = { module: { exports: {} }, uniCloud: { database: () => ({}), httpclient: {} },
    require: name => name === './indexer' ? { buildIndex: async () => { builds++; return { errCode: 0 } } } : require(name) }
  vm.runInNewContext(code, sandbox)
  const method = sandbox.module.exports.buildKnowledgeIndex
  for (const source of ['client', 'http', undefined]) {
    assert.equal((await method.call({ getClientInfo: () => ({ source }) })).errCode, 'INDEX_FORBIDDEN')
  }
  assert.equal(builds, 0)
  assert.equal((await method.call({ getClientInfo: () => ({ source: 'server' }) })).errCode, 0)
  assert.equal((await method.call({ getClientInfo: () => ({ source: 'function' }) })).errCode, 0)
  assert.equal(builds, 2)
})

test('管理云函数拒绝伪造 event 来源，server 才能调用 rag', async () => {
  const code = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag-index-admin/index.js'), 'utf8')
  let calls = 0
  const sandbox = { exports: {}, uniCloud: { importObject: () => ({ buildKnowledgeIndex: async () => { calls++; return { errCode: 0 } } }) } }
  vm.runInNewContext(code, sandbox)
  const method = sandbox.exports.main
  assert.equal((await method({ clientInfo: { source: 'server' } }, { SOURCE: 'client' })).errCode, 'INDEX_FORBIDDEN')
  assert.equal(calls, 0)
  assert.equal((await method({}, { SOURCE: 'server' })).errCode, 0)
  assert.equal(calls, 1)
})

test('管理云函数保留可用失败统计；未知异常不泄露内容、不宣称成功', async () => {
  const code = fs.readFileSync(path.join(__dirname, '../uniCloud-aliyun/cloudfunctions/rag-index-admin/index.js'), 'utf8')
  let error = { errCode: 'INDEX_PARTIAL_FAILURE', total: 21, inserted: 20, updated: 0, skipped: 0, failed: 1,
    orphanCount: 0, orphanScanComplete: true, orphanKnowledgeIds: [],
    failures: [{ knowledgeId: sources[0].knowledgeId, code: 'INDEX_WRITE_FAILED' }], sensitive: 'test-only-secret' }
  const sandbox = { exports: {}, uniCloud: { importObject: () => ({ buildKnowledgeIndex: async () => { throw error } }) } }
  vm.runInNewContext(code, sandbox)
  const result = await sandbox.exports.main({}, { SOURCE: 'server' })
  assert.equal(result.failed, 1)
  assert.equal(result.inserted, 20)
  assert.equal(result.failures[0].knowledgeId, sources[0].knowledgeId)
  assert.ok(!JSON.stringify(result).includes('test-only-secret'))
  error = new Error('Authorization test-only-secret')
  const unknown = await sandbox.exports.main({}, { SOURCE: 'server' })
  assert.equal(unknown.errCode, 'INDEX_ADMIN_CALL_FAILED')
  assert.ok(!JSON.stringify(unknown).includes('test-only-secret'))
})
