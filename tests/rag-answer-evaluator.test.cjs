const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const crypto = require('node:crypto')
const vm = require('node:vm')
const { evaluateAnswers, loadDataset, validateDataset, scoreQuery, summarize } = require('../uniCloud-aliyun/cloudfunctions/rag/answer-evaluator')
const source = require('../docs/rag/knowledge-source.json')
const dataset = loadDataset()
const row = id => dataset.queries.find(q => q.id === id)
const evidence = id => {
  const s = source.find(s => s.knowledgeId === id)
  return Object.fromEntries(['knowledgeId','dishId','scope','type','title','text'].map(k => [k,s[k]]))
}
function result(q, selected = [], retrieved = selected, answerable = selected.length > 0) {
  const ev = selected.map(evidence)
  return { errCode: 0, query: q.query, retrieval: { topK: 3, results: retrieved.map(evidence) },
    generation: { answerable, answer: answerable ? ev.map(e => e.text).join('\n') : '当前提供的知识不足以回答这个问题。',
      usedKnowledgeIds: selected, dishIds: [...new Set(ev.map(e => e.dishId).filter(Boolean))], evidence: ev } }
}
const partial = () => scoreQuery(row('beef'), result(row('beef'), ['dish-2-description','dish-4-taste'],
  ['dish-2-description','dish-2-ingredients','dish-4-taste']))

test('固定12条与6/3/3；所有标签确实存在', () => {
  assert.equal(dataset.queries.length, 12)
  for (const [kind,n] of [['supported',6],['unsupported-domain',3],['external-ood',3]]) assert.equal(dataset.queries.filter(q => q.kind===kind).length,n)
  assert.deepEqual(row('peppers').relevantKnowledgeIds, ['dish-5-description','dish-5-ingredients','dish-6-description','dish-6-ingredients','dish-7-ingredients'])
})
for (const [name, mutate] of [
  ['条数', d=>d.queries.pop()], ['类别',d=>d.queries[0].kind='other'],
  ['expected boolean',d=>d.queries[0].expectedAnswerable='true'],
  ['expected kind',d=>d.queries[6].expectedAnswerable=true],
  ['supported缺标签',d=>delete d.queries[0].relevantKnowledgeIds],
  ['supported空标签',d=>d.queries[0].relevantKnowledgeIds=[]],
  ['无答案不接受标签',d=>d.queries[6].relevantKnowledgeIds=[]],
  ['未知标签',d=>d.queries[0].relevantKnowledgeIds=['unknown']],
  ['重复标签',d=>d.queries[0].relevantKnowledgeIds=['dish-3-taste','dish-3-taste']],
  ['重复id',d=>d.queries[0].id=d.queries[1].id],
  ['重复query',d=>d.queries[0].query=d.queries[1].query]
]) test(`Dataset拒绝${name}`,()=>{const d=structuredClone(dataset);mutate(d);assert.throws(()=>validateDataset(d,source))})
test('回答正确、FP、FN分别记录',()=>{
  assert.equal(partial().answerabilityCorrect,true)
  assert.equal(scoreQuery(row('invoice'),result(row('invoice'),['dish-3-taste'])).answerabilityCorrect,false)
  const fn=scoreQuery(row('beef'),result(row('beef'),[],['dish-2-description']))
  assert.equal(fn.actualAnswerable,false);assert.equal(fn.evidencePrecision,0);assert.equal(fn.evidenceRecall,0)
})
test('部分命中precision/recall与无关及遗漏ID',()=>{
  const s=partial()
  assert.equal(s.evidenceHit,true);assert.equal(s.evidencePrecision,0.5);assert.equal(s.evidenceRecall,0.25)
  assert.deepEqual(s.selectedRelevantKnowledgeIds,['dish-2-description'])
  assert.deepEqual(s.selectedIrrelevantKnowledgeIds,['dish-4-taste'])
  assert.deepEqual(s.missedRelevantKnowledgeIds,['dish-2-ingredients','dish-6-description','dish-6-ingredients'])
})
test('retrieval availability与两类miss',()=>{
  const s=partial()
  assert.equal(s.retrievalHit,true);assert.equal(s.retrievalRecallAt3,0.5)
  assert.deepEqual(s.retrievalMissKnowledgeIds,['dish-6-description','dish-6-ingredients'])
  assert.deepEqual(s.evidenceSelectionMissKnowledgeIds,['dish-2-ingredients'])
})
test('零命中',()=>{
  const s=scoreQuery(row('beef'),result(row('beef'),['dish-4-taste']))
  assert.equal(s.evidenceHit,false);assert.equal(s.evidencePrecision,0);assert.equal(s.retrievalHit,false)
})
test('合法true/false结构检查通过',()=>{
  assert.equal(partial().serverGroundingPass,true)
  assert.equal(scoreQuery(row('invoice'),result(row('invoice'))).serverGroundingPass,true)
})
for (const [name, mutate] of [
  ['扩写',r=>r.generation.answer+='解腻'],
  ['文本与检索不一致',r=>{r.generation.evidence[0].text='不可信';r.generation.answer='不可信'}],
  ['未选中却有证据',r=>r.generation.usedKnowledgeIds=[]],
  ['引用在检索外',r=>r.retrieval.results=[]],
  ['菜品关联不匹配',r=>r.generation.dishIds=['dish-8']],
  ['重复ID',r=>r.generation.usedKnowledgeIds.push('dish-2-description')]
]) test(`grounding结构拒绝${name}`,()=>{
  const r=result(row('beef'),['dish-2-description']);mutate(r)
  assert.equal(scoreQuery(row('beef'),r).serverGroundingPass,false)
})
test('false有evidence或非固定文案均标异常',()=>{
  const r=result(row('invoice'));r.generation.evidence=[evidence('dish-4-taste')]
  assert.equal(scoreQuery(row('invoice'),r).serverGroundingPass,false)
  r.generation.evidence=[];r.generation.answer='随便拒答'
  assert.equal(scoreQuery(row('invoice'),r).serverGroundingPass,false)
})
test('duplicate ID不提高指标',()=>{
  const r=result(row('beef'),['dish-2-description','dish-2-description'])
  const s=scoreQuery(row('beef'),r)
  assert.equal(s.evidenceRecall,0.25);assert.equal(s.evidencePrecision,1);assert.equal(s.serverGroundingPass,false)
})
test('汇总全部指标精确值；unsupported不参与evidence均值',()=>{
  const scored=[partial(),scoreQuery(row('clean'),result(row('clean'),[],['dish-3-taste'])),
    scoreQuery(row('invoice'),result(row('invoice'),['dish-4-taste'])),
    scoreQuery(row('reservation'),result(row('reservation'))),scoreQuery(row('weather'),result(row('weather')))]
  const s=summarize(scored)
  assert.equal(s.answerabilityAccuracy,3/5);assert.equal(s.answerabilityCorrectCount,3)
  assert.equal(s.truePositiveCount,1);assert.equal(s.supportedAnswerRate,1/2)
  assert.equal(s.trueNegativeCount,2);assert.equal(s.rejectionRate,2/3)
  assert.equal(s.unsupportedDomainRejectionRate,1/2);assert.equal(s.externalOodRejectionRate,1)
  assert.equal(s.evidenceHitCount,1);assert.equal(s.evidenceHitRate,1/2)
  assert.equal(s.averageEvidencePrecision,0.25);assert.equal(s.averageEvidenceRecall,0.125)
  assert.equal(s.retrievalHitCount,2);assert.equal(s.retrievalHitRate,1)
  assert.equal(s.averageRetrievalRecallAt3,(0.5+1/3)/2)
  assert.deepEqual(s.falsePositiveQueries.map(q=>q.id),['invoice']);assert.deepEqual(s.falseNegativeQueries.map(q=>q.id),['clean'])
  assert.equal(s.serverGroundingPassCount,5);assert.equal(s.serverGroundingPassRate,1)
})
test('失败不是正常拒答；空分母null，不伪造成功率',()=>{
  const s=scoreQuery(row('invoice'),{errCode:'FAILED',errMsg:'sensitive'})
  assert.equal(s.actualAnswerable,null);assert.equal(s.answerabilityCorrect,null)
  const m=summarize([s]);assert.equal(m.failedCount,1);assert.equal(m.rejectionRate,null);assert.equal(m.answerabilityAccuracy,null)
})
test('诊断额外敏感字段不会扩散到报告',()=>{
  const r=result(row('beef'),['dish-2-description'])
  r.rawResponse='sensitive';r.embedding=Array(512).fill(1);r.generation.apiKey='sensitive'
  r.generation.evidence[0].embedding=[1,2];r.retrieval.results[0].headers={Authorization:'sensitive'}
  const text=JSON.stringify(scoreQuery(row('beef'),r))
  for(const word of ['embedding','apiKey','rawResponse','Authorization','sensitive']) assert.ok(!text.includes(word))
})
test('并发最多3，完成乱序仍按固定Query映射',async()=>{
  let active=0,max=0,calls=0
  const report=await evaluateAnswers({},async query=>{
    active++;max=Math.max(max,active);calls++
    const q=dataset.queries.find(q=>q.query===query)
    await new Promise(resolve=>setTimeout(resolve,q.id==='clean'?15:1))
    active--
    return result(q,q.expectedAnswerable?[q.relevantKnowledgeIds[0]]:[])
  })
  assert.equal(calls,12);assert.equal(max,3);assert.equal(report.errCode,0)
  assert.deepEqual(report.queries.map(q=>q.id),dataset.queries.map(q=>q.id))
  assert.equal(report.answerabilityAccuracy,1)
})
test('部分调用错误继续收集，非零总状态；不泄露原异常',async()=>{
  const report=await evaluateAnswers({},async query=>{
    const q=dataset.queries.find(q=>q.query===query)
    if(q.id==='invoice') throw new Error('Authorization secret-test')
    return result(q,q.expectedAnswerable?[q.relevantKnowledgeIds[0]]:[])
  })
  assert.equal(report.errCode,'ANSWER_EVAL_PARTIAL_FAILED');assert.equal(report.failedCount,1)
  assert.equal(report.completedCount,11);assert.equal(report.evaluatedUnsupportedDomainCount,2)
  assert.ok(!JSON.stringify(report).includes('secret-test'))
})
test('结构失败整轮非零',async()=>{
  const report=await evaluateAnswers({},async query=>{
    const q=dataset.queries.find(q=>q.query===query),r=result(q,q.expectedAnswerable?[q.relevantKnowledgeIds[0]]:[])
    if(q.id==='clean')r.generation.answer='扩写'
    return r
  });assert.equal(report.errCode,'ANSWER_EVAL_STRUCTURE_FAILED');assert.equal(report.serverGroundingPassCount,11)
})
test('默认evaluator确实走共享answerQuery及真实retriever（仅HTTP和DB为本地模拟）',async()=>{
  let embeddingCalls=0,generationCalls=0
  const records=source.map(s=>({...s,embedding:[1,...Array(511).fill(0)],embeddingModel:'qwen3.7-text-embedding-flash',embeddingDimension:512}))
  const dishes=require('../uniCloud-aliyun/database/dishes.init_data.json')
  const db={command:{in:ids=>ids},collection(name){let c;return {where(x){c=x;return this},orderBy(){return this},skip(){return this},limit(){return this},field(){return this},async get(){return {data:name==='knowledge_chunks'?records:dishes.filter(d=>c._id.includes(d._id))}}}}}
  const httpclient={async request(url,config){
    if(url.endsWith('/embeddings')) {embeddingCalls++;assert.ok(dataset.queries.some(q=>q.query===config.data.input));return {status:200,data:JSON.stringify({data:[{index:0,embedding:[1,...Array(511).fill(0)]}]})}}
    generationCalls++;return {status:200,data:JSON.stringify({choices:[{finish_reason:'stop',message:{content:JSON.stringify({answerable:false,dishIds:[],usedKnowledgeIds:[]})}}]})}
  } }
  const report=await evaluateAnswers({db,httpclient,env:{DASHSCOPE_API_KEY:'secret-test',LLM_BASE_URL:'https://example.invalid/v1',RAG_LLM_MODEL:'test-model',EMBEDDING_MODEL:'qwen3.7-text-embedding-flash',EMBEDDING_DIMENSION:'512'}})
  assert.equal(embeddingCalls,12);assert.equal(generationCalls,12);assert.equal(report.completedCount,12)
  assert.equal(report.falseNegativeQueries.length,6);assert.equal(report.serverGroundingPassRate,1)
})
test('冻结正式Answer管线和原接口测试未修改',()=>{
  const frozen=require('./fixtures/rag-answer-pipeline-frozen.json')
  for(const [file,hash] of Object.entries(frozen))assert.equal(crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),hash,file)
})
test('管理入口和云对象方法拒绝客户端，不转发event/标签',async()=>{
  let calls=0
  const sandbox={exports:{},uniCloud:{importObject:name=>{assert.equal(name,'rag');return {evaluateAnswers:async(...args)=>{assert.equal(args.length,0);calls++;return {errCode:0}}}}}}
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/rag-answer-eval-admin/index.js','utf8'),sandbox)
  for(const SOURCE of ['client','http',undefined])assert.equal((await sandbox.exports.main({}, {SOURCE})).errCode,'ANSWER_EVAL_FORBIDDEN')
  await sandbox.exports.main({query:'injected'},{SOURCE:'server'});assert.equal(calls,1)
  const cloud={module:{exports:{}},require:name=>name==='./answer-evaluator'?{evaluateAnswers:async(...args)=>{assert.equal(args.length,1);assert.equal(args[0].db,'db');return {errCode:0}}}:require(name),uniCloud:{database:()=> 'db',httpclient:'http'}}
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/rag/index.obj.js','utf8'),cloud)
  const method=cloud.module.exports.evaluateAnswers
  for(const source of ['client','http',undefined])assert.equal((await method.call({getClientInfo:()=>({source})})).errCode,'ANSWER_EVAL_FORBIDDEN')
  assert.equal((await method.call({getClientInfo:()=>({source:'function'})},{query:'ignored'})).errCode,0)
})
