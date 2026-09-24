const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const serviceText = fs.readFileSync('src/services/rag.js', 'utf8')
const pageText = fs.readFileSync('src/pages/rag-qa/index.vue', 'utf8')
const clone = value => JSON.parse(JSON.stringify(value))
const response = () => ({ errCode: 0, answerable: true, answer: '菜单原文。\n第二行。',
  dishIds: ['dish-4','dish-3'], usedKnowledgeIds: ['dish-4-taste'],
  evidence: [{ knowledgeId: 'dish-4-taste', title: '菜品说明', text: '知识原文', embedding: [9], price: 1 }], similarity: 1 })
function service(reply = response(), timers = {}) {
  const calls = []
  const context = { setTimeout, clearTimeout, ...timers, uniCloud: { importObject(name, options) {
    assert.equal(name, 'rag'); assert.equal(options.customUI, true)
    return { answer: async query => { calls.push(query); if (reply instanceof Error) throw reply; return reply } }
  } } }
  vm.runInNewContext(serviceText.replace('export async function', 'async function')+'\nthis.call = answerMenuQuestion', context)
  return { calls, call: context.call }
}
function page(options = {}) {
  const calls = [], navigation = []
  const context = { ref: value => ({ value }), computed: getter => ({ get value() { return getter() } }), setTimeout, clearTimeout,
    answerMenuQuestion: async q => { calls.push(q); return options.answer ? options.answer(q) : response() },
    getDishes: options.menu || (async () => [
      { id:'dish-3', name:'沙拉', price:20, status:'on_sale', image:'3.png' },
      { id:'dish-4', name:'柠檬茶', price:8, status:'sold_out', image:'4.png' }
    ]), uni: { navigateTo: data => navigation.push(data) } }
  const script = pageText.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
  vm.runInNewContext(script+'\nthis.state={query,loading,result,errorMessage,relatedDishes,dishesError,queryLength,submit,fillExample,goToDetail}',context)
  return { ...context.state, calls, navigation }
}
test('service trim并只调用正式answer，返回字段白名单',async()=>{
  const s=service(),r=await s.call('  我想吃牛肉\n')
  assert.deepEqual(s.calls,['我想吃牛肉'])
  assert.equal(r.answer,response().answer)
  assert.deepEqual(clone(r.evidence),[{title:'菜品说明',text:'知识原文'}])
  for(const key of ['embedding','similarity','price','knowledgeId'])assert.ok(!Object.hasOwn(r.evidence[0],key))
  assert.ok(!Object.hasOwn(r,'similarity'))
})
for(const [query,msg] of [['','请输入问题'],[' \n ','请输入问题'],[null,'请输入问题'],['中'.repeat(201),'问题请控制在 200 字以内']]) {
  test('无效输入不消耗请求 '+String(query).slice(0,10),async()=>{const s=service();await assert.rejects(()=>s.call(query),e=>e.message===msg);assert.equal(s.calls.length,0)})
}
test('Unicode 200字符允许，不按UTF16截断',async()=>{const s=service();await s.call('🍋'.repeat(200));assert.equal(s.calls.length,1)})
test('false是正常结果原文展示',async()=>{
  const r={errCode:0,answerable:false,answer:'当前提供的知识不足以回答这个问题。',dishIds:[],usedKnowledgeIds:[],evidence:[]}
  assert.equal((await service(r).call('天气')).answerable,false)
  let reads=0
  const p=page({answer:async()=>r,menu:async()=>{reads++;return []}});await p.submit()
  assert.equal(p.errorMessage.value,'');assert.equal(p.result.value.answer,r.answer);assert.equal(reads,0)
})
for(const reply of [{errCode:'RAG_QUERY_INVALID',errMsg:'内部信息'},Object.assign(new Error('敏感信息'),{errCode:'RAG_QUERY_INVALID'}),{errCode:'RETRIEVAL_FAILED',errMsg:'敏感信息'},new Error('Authorization secret-test'),null]) {
  test('安全错误映射 '+String(reply?.errCode),async()=>{
    const expected=reply?.errCode==='RAG_QUERY_INVALID'?'问题格式不正确，请重新输入':'暂时无法获取回答，请稍后重试。'
    await assert.rejects(()=>service(reply).call('牛肉'),e=>e.message===expected)
  })
}
test('service等待有上限且清理定时器',async()=>{
  let timer,cleared=false
  const s=service(new Promise(()=>{}),{setTimeout:fn=>{timer=fn;return 1},clearTimeout:()=>{cleared=true}})
  const request=s.call('牛肉');timer();await assert.rejects(request,e=>e.message==='暂时无法获取回答，请稍后重试。');assert.equal(cleared,true)
})
test('提交期间同步拦截重复调用；新提交立即清空旧结果',async()=>{
  let resolve
  const p=page({answer:()=>new Promise(r=>{resolve=r})})
  p.result.value=response();p.errorMessage.value='旧错误';p.query.value='牛肉'
  const first=p.submit();await p.submit()
  assert.equal(p.calls.length,1);assert.equal(p.loading.value,true)
  assert.equal(p.result.value,null);assert.equal(p.errorMessage.value,'')
  resolve(response());await first;assert.equal(p.loading.value,false);assert.equal(p.result.value.answer,response().answer)
})
test('相关菜品用实时菜单价格状态，保持ID顺序且跳过未知ID',async()=>{
  const r=response();r.dishIds=['dish-4','missing','dish-3','dish-4']
  const p=page({answer:async()=>r});await p.submit()
  assert.deepEqual(clone(p.relatedDishes.value.map(d=>d.id)),['dish-4','dish-3'])
  assert.deepEqual(clone(p.relatedDishes.value.map(d=>d.price)),[8,20])
  assert.equal(p.relatedDishes.value[0].status,'sold_out')
})
test('菜单失败保留回答并显示独立友好提示',async()=>{
  const p=page({menu:async()=>{throw new Error('secret')}});await p.submit()
  assert.equal(p.result.value.answer,response().answer);assert.equal(p.loading.value,false)
  assert.equal(p.errorMessage.value,'');assert.equal(p.dishesError.value,'相关菜品暂时加载失败，可稍后重新提问。')
})
test('技术失败清空回答、finally恢复并允许重试',async()=>{
  let fail=true
  const p=page({answer:async()=>{if(fail)throw new Error('暂时无法获取回答，请稍后重试。');return response()}})
  await p.submit();assert.equal(p.result.value,null);assert.equal(p.loading.value,false)
  assert.equal(p.errorMessage.value,'暂时无法获取回答，请稍后重试。')
  fail=false;await p.submit();assert.equal(p.errorMessage.value,'');assert.ok(p.result.value)
})
test('示例只填文本，loading期间忽略点击',()=>{
  const p=page();p.fillExample('我想吃牛肉');assert.equal(p.query.value,'我想吃牛肉');assert.equal(p.calls.length,0)
  p.loading.value=true;p.fillExample('其他');assert.equal(p.query.value,'我想吃牛肉')
})
test('复用菜品详情导航',()=>{
  const p=page();p.goToDetail({id:'dish-4'});assert.equal(p.navigation[0].url,'/pages/dish-detail/index?id=dish-4')
})
test('模板仅展示回答、依据标题正文，不暴露内部字段；无购物车和诊断调用',()=>{
  const template=pageText.split('<script setup>')[0]
  assert.ok(template.includes('{{ result.answer }}'))
  assert.ok(template.includes('{{ item.title }}')&&template.includes('{{ item.text }}'))
  for(const word of ['knowledgeId','usedKnowledgeIds','scope','embedding','similarity','RAG','Qwen','Answerability','Retrieval'])assert.ok(!template.includes(word),word)
  for(const word of ['testRagGeneration','evaluateAnswers','testRetrieval','testEmbedding','useCartStore','addDish','setStorageSync'])assert.ok(!(serviceText+pageText).includes(word),word)
  assert.ok(!pageText.includes('console.'))
})
test('首页入口与路由已注册，TabBar保持5项',()=>{
  const home=fs.readFileSync('src/pages/home/index.vue','utf8')
  assert.ok(home.includes('/pages/rag-qa/index'))
  const pages=JSON.parse(fs.readFileSync('src/pages.json','utf8'))
  assert.equal(pages.pages.find(p=>p.path==='pages/rag-qa/index').style.navigationBarTitleText,'菜单问答')
  assert.equal(pages.tabBar.list.length,5)
  assert.ok(!pages.tabBar.list.some(p=>p.pagePath==='pages/rag-qa/index'))
})
