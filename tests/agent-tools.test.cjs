const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const { executeTool } = require('../uniCloud-aliyun/cloudfunctions/agent/tools/executor')
const { getToolDefinitions } = require('../uniCloud-aliyun/cloudfunctions/agent/tools/registry')
const source = require('../uniCloud-aliyun/database/dishes.init_data.json')
const categorySource = require('../uniCloud-aliyun/database/categories.init_data.json')
function setup(options = {}) {
  const calls = []
  const dishes = structuredClone(options.dishes || source)
  const categories = structuredClone(options.categories || categorySource)
  const db = { collection(name) {
    assert.ok(['dishes','categories'].includes(name))
    let condition = {}, offset = 0, size = 100
    return {
      where(value) { condition=value;return this }, field() {return this},
      orderBy(key, direction) {assert.equal(key,'_id');assert.equal(direction,'asc');return this},
      skip(n) {offset=n;return this},limit(n) {size=n;return this},
      async get() {
        calls.push({ name, condition, offset, size })
        if (options.fails) throw new Error('database password secret-test Authorization')
        if (options.badResponse) return { data: null }
        const all = name === 'dishes' ? dishes : categories
        return { data: all.filter(row => Object.entries(condition).every(([key,value])=>row[key]===value))
          .sort((a,b)=>a._id < b._id ? -1 : a._id > b._id ? 1 : 0).slice(offset,offset+size) }
      },
      add() {assert.fail('write forbidden')},update() {assert.fail('write forbidden')},remove() {assert.fail('write forbidden')}
    }
  } }
  return { calls, dishes, run:(name,args)=>executeTool(name,args,{db}) }
}
function loadExecutorWithCartAction(prepareAddToCart) {
  const sandbox = { module: { exports: {} }, require(name) {
    if (name === './registry') return { getToolDefinitions: () => [{ function: { name: 'prepare_add_to_cart', parameters: {
      type: 'object', additionalProperties: false, required: ['dishId', 'quantity'],
      properties: { dishId: { type: 'string', minLength: 1, maxLength: 64 }, quantity: { type: 'integer', minimum: 1, maximum: 20 } }
    } } }] }
    if (name === './menu-tools') return { searchMenu() {}, listAvailableDrinks() {}, getDishDetail() {} }
    if (name === './cart-actions') return { prepareAddToCart }
    throw new Error('unexpected require: ' + name)
  } }
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent/tools/executor.js', 'utf8'), sandbox)
  return sandbox.module.exports.executeTool
}
test('Registry恰好4个唯一工具，function JSON Schema明确且JSON可序列化',()=>{
  const tools=getToolDefinitions()
  assert.deepEqual(tools.map(t=>t.function.name),['search_menu','list_available_drinks','get_dish_detail','prepare_add_to_cart'])
  assert.equal(new Set(tools.map(t=>t.function.name)).size,4)
  for(const tool of tools){
    assert.equal(tool.type,'function');assert.ok(tool.function.description)
    const p=tool.function.parameters;assert.equal(p.type,'object');assert.equal(p.additionalProperties,false)
    assert.ok(Array.isArray(p.required));for(const key of p.required)assert.ok(['string','integer'].includes(p.properties[key].type))
  }
  assert.deepEqual(JSON.parse(JSON.stringify(tools)),tools)
  tools[0].function.name='create_order';tools[0].function.parameters.properties.query.maxLength=999
  assert.equal(getToolDefinitions()[0].function.name,'search_menu')
  assert.equal(getToolDefinitions()[0].function.parameters.properties.query.maxLength,50)
})
test('prepare_add_to_cart Schema只接受dishId和1～20整数quantity',()=>{
  const schema=getToolDefinitions().find(tool=>tool.function.name==='prepare_add_to_cart').function.parameters
  assert.deepEqual(schema.required,['dishId','quantity'])
  assert.deepEqual(Object.keys(schema.properties),['dishId','quantity'])
  assert.equal(schema.properties.dishId.type,'string')
  assert.deepEqual(schema.properties.quantity,{type:'integer',minimum:1,maximum:20,description:'准备加入的数量，必须为1～20的整数'})
})
for(const name of ['unknown','constructor','__proto__','toString','../orders','create_order','add_to_cart',null]) {
  test('拒绝未知/危险工具 '+name,async()=>{const a=setup();assert.equal((await a.run(name,{})).errCode,'AGENT_TOOL_NOT_FOUND');assert.equal(a.calls.length,0)})
}
for(const args of [{query:''},{query:'   '},{query:'中'.repeat(51)},{query:3},{},{query:['牛肉']},null,[],{query:'牛肉',collection:'orders'},{query:'牛肉',implementation:'other'},JSON.parse('{"query":"牛肉","__proto__":{}}')]) {
  test('拒绝错误search参数 '+JSON.stringify(args).slice(0,35),async()=>{const a=setup();assert.equal((await a.run('search_menu',args)).errCode,'AGENT_TOOL_ARGUMENT_INVALID');assert.equal(a.calls.length,0)})
}
test('拒绝getter，不执行用户函数',async()=>{
  let invoked=false
  const args={get query(){invoked=true;return '牛肉'}}
  assert.equal((await setup().run('search_menu',args)).errCode,'AGENT_TOOL_ARGUMENT_INVALID');assert.equal(invoked,false)
})
test('trim后匹配牛肉，字段来自实时DB；搜索包括售罄记录',async()=>{
  const a=setup();a.dishes.find(d=>d._id==='dish-2').price=29.5
  a.dishes.find(d=>d._id==='dish-6').status='sold_out'
  const r=await a.run('search_menu',{query:' 牛肉\n'})
  assert.equal(r.errCode,0);assert.equal(r.query,'牛肉');assert.equal(r.count,2)
  assert.deepEqual(r.items.map(i=>i.dishId),['dish-2','dish-6'])
  assert.equal(r.items[0].price,29.5);assert.equal(r.items[1].status,'sold_out')
  assert.deepEqual(Object.keys(r.items[0]).sort(),['dishId','name','categoryId','price','status','spicyLevel'].sort())
})
test('可乐没有匹配只返回空items，无不存在的自然语言结论',async()=>{
  assert.deepEqual(await setup().run('search_menu',{query:'可乐'}),{errCode:0,tool:'search_menu',query:'可乐',count:0,items:[]})
})
test('配料匹配冰糖',async()=>{
  const r=await setup().run('search_menu',{query:'冰糖'})
  assert.deepEqual(r.items.map(i=>i.dishId),['dish-8'])
})
test('描述字段匹配；字面匹配，不使用正则或语义推断',async()=>{
  const a=setup();a.dishes[0].description='唯一描述 LATTE'
  assert.equal((await a.run('search_menu',{query:'latte'})).items[0].dishId,a.dishes[0]._id)
  assert.equal((await a.run('search_menu',{query:'.*'})).count,0)
})
test('正好50 Unicode字符合法',async()=>{
  assert.equal((await setup().run('search_menu',{query:'🍋'.repeat(50)})).errCode,0)
})
test('分页不漏掉第101条真实匹配',async()=>{
  const rows=Array.from({length:101},(_,i)=>({...source[0],_id:String(i).padStart(3,'0'),name:i===100?'可乐':'其他',description:'描述',ingredients:['水']}))
  const a=setup({dishes:rows});const r=await a.run('search_menu',{query:'可乐'})
  assert.equal(r.count,1);assert.equal(r.items[0].dishId,'100');assert.deepEqual(a.calls.map(c=>c.offset),[0,100])
})
test('饮料分类从DB解析真实ID，过滤在售；不硬编码drink',async()=>{
  const categories=structuredClone(categorySource);categories.find(c=>c.name==='饮料')._id='beverage-live'
  const dishes=structuredClone(source)
  for(const d of dishes)if(d.categoryId==='drink')d.categoryId='beverage-live'
  dishes.find(d=>d._id==='dish-8').status='sold_out'
  const a=setup({categories,dishes});const r=await a.run('list_available_drinks',{})
  assert.equal(r.errCode,0);assert.deepEqual(r.items.map(i=>i.dishId),['dish-4'])
  assert.deepEqual(a.calls[0].condition,{name:'饮料'})
  assert.deepEqual(a.calls[1].condition,{categoryId:'beverage-live',status:'on_sale'})
})
test('初始化酸梅汤售罄，实际只返回柠檬茶',async()=>{
  const r=await setup().run('list_available_drinks',{})
  assert.deepEqual(r.items.map(i=>i.name),['柠檬茶'])
})
for(const categories of [[],[...categorySource,{_id:'other',name:'饮料'}]]) {
  test('饮料分类缺失/重复明确执行失败',async()=>assert.equal((await setup({categories}).run('list_available_drinks',{})).errCode,'AGENT_TOOL_EXECUTION_FAILED'))
}
test('list工具不接受额外过滤器',async()=>assert.equal((await setup().run('list_available_drinks',{status:'sold_out'})).errCode,'AGENT_TOOL_ARGUMENT_INVALID'))
test('详情字段与DB一致，不返回内部额外字段',async()=>{
  const a=setup();a.dishes[3].privateField='secret-test'
  const d=a.dishes.find(d=>d._id==='dish-4'),r=await a.run('get_dish_detail',{dishId:' dish-4 '})
  assert.equal(r.errCode,0);assert.equal(r.found,true);assert.equal(r.item.price,d.price);assert.equal(r.item.status,d.status)
  assert.deepEqual(r.item.ingredients,d.ingredients);assert.equal(r.item.description,d.description)
  assert.ok(!JSON.stringify(r).includes('privateField'));assert.ok(!Object.hasOwn(r.item,'_id'))
})
test('详情不存在返回明确found=false',async()=>{
  assert.deepEqual(await setup().run('get_dish_detail',{dishId:'missing'}),{errCode:0,tool:'get_dish_detail',dishId:'missing',found:false,item:null})
})
for(const args of [{dishId:''},{dishId:1},{dishId:' '},{}]) {
  test('详情参数错误 '+JSON.stringify(args),async()=>assert.equal((await setup().run('get_dish_detail',args)).errCode,'AGENT_TOOL_ARGUMENT_INVALID'))
}
for(const args of [{quantity:1},{dishId:'dish-4'},{dishId:'dish-4',quantity:0},{dishId:'dish-4',quantity:-1},
  {dishId:'dish-4',quantity:1.5},{dishId:'dish-4',quantity:21},{dishId:'dish-4',quantity:'2'},
  {dishId:'dish-4',quantity:2,name:'假的柠檬茶'},{dishId:'dish-4',quantity:2,price:0},{dishId:' ',quantity:2}]) {
  test('购物车提案拒绝非法参数 '+JSON.stringify(args),async()=>{
    const a=setup();assert.equal((await a.run('prepare_add_to_cart',args)).errCode,'AGENT_TOOL_ARGUMENT_INVALID');assert.equal(a.calls.length,0)
  })
}
test('在售菜品重新查询DB并生成服务端Pending Action',async()=>{
  const a=setup(),dish=a.dishes.find(item=>item._id==='dish-4')
  dish.name='实时柠檬茶';dish.price=12.34;dish.status='on_sale'
  const result=await a.run('prepare_add_to_cart',{dishId:' dish-4 ',quantity:3})
  assert.deepEqual(result,{errCode:0,tool:'prepare_add_to_cart',pendingAction:{type:'add_to_cart',dishId:'dish-4',
    name:'实时柠檬茶',quantity:3,unitPrice:12.34,totalPrice:37.02,requiresConfirmation:true}})
  assert.deepEqual(a.calls.map(call=>call.condition),[{_id:'dish-4'}])
})
test('模型不能通过参数提供name/price/status/totalPrice',async()=>{
  const result=await setup().run('prepare_add_to_cart',{dishId:'dish-4',quantity:2,name:'伪造',price:1,status:'on_sale',totalPrice:2})
  assert.equal(result.errCode,'AGENT_TOOL_ARGUMENT_INVALID')
})
test('sold_out菜品不生成Pending Action',async()=>{
  const result=await setup().run('prepare_add_to_cart',{dishId:'dish-8',quantity:1})
  assert.deepEqual(result,{errCode:'AGENT_ACTION_DISH_UNAVAILABLE',errMsg:'当前菜品不可用'})
  assert.equal(Object.hasOwn(result,'pendingAction'),false)
})
test('不存在菜品不生成Pending Action',async()=>{
  const result=await setup().run('prepare_add_to_cart',{dishId:'missing',quantity:1})
  assert.deepEqual(result,{errCode:'AGENT_ACTION_DISH_NOT_FOUND',errMsg:'未找到对应菜品'})
  assert.equal(Object.hasOwn(result,'pendingAction'),false)
})
test('Executor只透传白名单业务错误并使用固定安全文案',async()=>{
  for (const errCode of ['AGENT_ACTION_DISH_NOT_FOUND','AGENT_ACTION_DISH_UNAVAILABLE']) {
    const run=loadExecutorWithCartAction(async()=>({errCode,errMsg:'database internals',stack:'secret stack'}))
    const args=Object.assign(Object.create(null),{dishId:'dish-4',quantity:1})
    const result=await run('prepare_add_to_cart',args,{db:{}})
    assert.equal(result.errCode,errCode)
    assert.equal(Object.hasOwn(result,'stack'),false)
    assert.ok(!JSON.stringify(result).includes('database internals'))
  }
})
test('Executor未知返回错误码和未知异常仍统一泛化',async()=>{
  for (const implementation of [
    async()=>({errCode:'CUSTOM_DATABASE_ERROR',errMsg:'database internals',stack:'secret stack'}),
    async()=>{const error=new Error('database internals');error.code='CUSTOM_DATABASE_ERROR';throw error}
  ]) {
    const run=loadExecutorWithCartAction(implementation)
    const args=Object.assign(Object.create(null),{dishId:'dish-4',quantity:1})
    const result=await run('prepare_add_to_cart',args,{db:{}})
    assert.deepEqual({...result},{errCode:'AGENT_TOOL_EXECUTION_FAILED',errMsg:'工具执行失败，请检查菜单数据或稍后重试'})
    assert.ok(!JSON.stringify(result).includes('database internals'))
    assert.equal(Object.hasOwn(result,'stack'),false)
  }
})
for(const options of [{fails:true},{badResponse:true},{dishes:[{...source[0],price:NaN}]}]) {
  test('DB异常安全返回且不泄露内部错误',async()=>{
    const r=await setup(options).run('search_menu',{query:'鸡'})
    assert.deepEqual(r,{errCode:'AGENT_TOOL_EXECUTION_FAILED',errMsg:'工具执行失败，请检查菜单数据或稍后重试'})
    assert.ok(!JSON.stringify(r).includes('Authorization'));assert.ok(!JSON.stringify(r).includes('secret-test'))
  })
}
test('云对象受限，不接受第三参数依赖覆盖',async()=>{
  let calls=0,runnerCalls=0
  const sandbox={module:{exports:{}},require:name=>name==='./tools/executor'?{executeTool:async(name,args,options)=>{
    calls++;assert.equal(name,'search_menu');assert.equal(args.query,'牛肉');assert.equal(options.db,'server-db');return {errCode:0}
  }}:name==='./tools/registry'?{getToolDefinitions:()=>[]}:{runAgent:async(query,options)=>{
    runnerCalls++;assert.equal(query,'你好');assert.equal(options.db,'server-db');assert.equal(options.httpclient,'server-http')
    return options.includeTrace?{errCode:0,trace:[]}:{errCode:0,query,answer:'你好',completed:true}
  }},uniCloud:{database:()=> 'server-db',httpclient:'server-http'}}
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent/index.obj.js','utf8'),sandbox)
  const obj=sandbox.module.exports
  for(const source of ['client','http',undefined]){
    const ctx={getClientInfo:()=>({source})}
    assert.equal((await obj.testTool.call(ctx,'search_menu',{query:'牛肉'})).errCode,'AGENT_TOOL_FORBIDDEN')
    assert.equal((await obj.getToolDefinitions.call(ctx)).errCode,'AGENT_TOOL_FORBIDDEN')
    assert.equal((await obj.runForAdmin.call(ctx,'你好')).errCode,'AGENT_TOOL_FORBIDDEN')
  }
  await obj.testTool.call({getClientInfo:()=>({source:'function'})},'search_menu',{query:'牛肉'},{db:'fake'})
  assert.deepEqual(await obj.run('你好',{includeTrace:true}),{errCode:0,query:'你好',answer:'你好',completed:true})
  assert.deepEqual(await obj.runForAdmin.call({getClientInfo:()=>({source:'server'})},'你好'),{errCode:0,trace:[]})
  assert.equal(calls,1);assert.equal(runnerCalls,2)
  assert.deepEqual(Object.keys(obj).sort(),['getToolDefinitions','run','runForAdmin','testTool'])
})
test('admin只允许server并仅转发toolName和args',async()=>{
  const calls=[]
  const sandbox={exports:{},uniCloud:{importObject:name=>{assert.equal(name,'agent');return {testTool:async(...args)=>{calls.push(args);return {errCode:0}}}}}}
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent-tool-admin/index.js','utf8'),sandbox)
  for(const SOURCE of ['client','http',undefined])assert.equal((await sandbox.exports.main({source:'server'},{SOURCE})).errCode,'AGENT_TOOL_FORBIDDEN')
  await sandbox.exports.main({toolName:'search_menu',args:{query:'可乐'},db:'fake'},{SOURCE:'server'})
  assert.deepEqual(calls,[['search_menu',{query:'可乐'}]])
})
test('admin仅恢复云对象代理抛出的白名单业务错误',async()=>{
  for (const [errCode,errMsg] of [['AGENT_ACTION_DISH_UNAVAILABLE','当前菜品不可用'],['AGENT_ACTION_DISH_NOT_FOUND','未找到对应菜品']]) {
    const sandbox={exports:{},uniCloud:{importObject:()=>({testTool:async()=>{throw {errCode,errMsg:'database internals',stack:'secret stack'}}})}}
    vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent-tool-admin/index.js','utf8'),sandbox)
    const result=await sandbox.exports.main({toolName:'prepare_add_to_cart',args:{dishId:'dish-8',quantity:1}},{SOURCE:'server'})
    assert.deepEqual({...result},{errCode,errMsg})
    assert.ok(!JSON.stringify(result).includes('database internals'))
    assert.equal(Object.hasOwn(result,'stack'),false)
  }
})
test('admin未知自定义异常继续返回通用安全错误',async()=>{
  const sandbox={exports:{},uniCloud:{importObject:()=>({testTool:async()=>{throw {code:'CUSTOM_DATABASE_ERROR',message:'database internals',stack:'secret stack'}}})}}
  vm.runInNewContext(fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent-tool-admin/index.js','utf8'),sandbox)
  const result=await sandbox.exports.main({toolName:'prepare_add_to_cart',args:{dishId:'dish-8',quantity:1}},{SOURCE:'server'})
  assert.deepEqual({...result},{errCode:'AGENT_TOOL_EXECUTION_FAILED',errMsg:'工具调用未完成，请检查部署与菜单数据'})
  assert.ok(!JSON.stringify(result).includes('database internals'))
  assert.equal(Object.hasOwn(result,'stack'),false)
})
test('Agent工具层仍不含模型API、写操作、动态用户路径执行',()=>{
  const files=['tools/registry.js','tools/executor.js','tools/menu-tools.js','tools/cart-actions.js']
  const text=files.map(f=>fs.readFileSync('uniCloud-aliyun/cloudfunctions/agent/'+f,'utf8')).join('\n')
  for(const pattern of [/httpclient/,/DASHSCOPE_API_KEY/,/chat\/completions/,/\.add\(/,/\.update\(/,/\.remove\(/,/eval\(/,/new Function/,/require\(toolName/])assert.ok(!pattern.test(text.replace('seen.add(row._id)', '')),String(pattern))
})

test('实时DB酸梅汤改为在售时返回两种饮料',async()=>{
  const a=setup();a.dishes.find(d=>d._id==='dish-8').status='on_sale'
  assert.deepEqual((await a.run('list_available_drinks',{})).items.map(i=>i.name),['柠檬茶','酸梅汤'])
})
