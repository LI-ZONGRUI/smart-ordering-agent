# V5.1：Ordering Agent Tool Foundation

## 当前目标与边界

V4已完成单轮RAG问答和独立推荐；未来希望Ordering Agent能围绕用户目标选择菜单、知识、购物车或订单能力。V5.1先建立标准化、可校验的只读菜单工具，让后续模型使用真实服务器结果。

**V5.1还不是Agent。** 没有LLM调用、Function Calling、Agent Loop、多轮messages、前端入口或写操作。工具定义采用兼容后续tools/function的JSON形状，但本阶段不会发送给任何模型。三个只读工具已由开发者通过HBuilderX的agent-tool-admin，在真实uniCloud阿里云空间xlimao完成云端验收。以下真实结果由开发者提供，本次文档收尾未重新执行远程API。

## 文件与职责

```text
uniCloud-aliyun/cloudfunctions/
 ├─ agent/
 │   ├─ index.obj.js        受限testTool / getToolDefinitions
 │   ├─ package.json
 │   └─ tools/
 │       ├─ registry.js     名称、说明和参数JSON Schema
 │       ├─ executor.js     allowlist、参数验证、固定派发、安全错误
 │       └─ menu-tools.js   只读categories / dishes
 └─ agent-tool-admin/
     ├─ index.js           HBuilderX管理调用代理
     └─ package.json
```

普通函数只有实现；这里的Tool额外具备显式机器可读合同、可执行名单、统一参数验证和结构化结果。它仍是受控服务端函数，并非拥有自主计划能力。

## Registry与执行规则

每个定义为 `{ type: 'function', function: { name, description, parameters } }`。参数schema为object，声明properties、required和additionalProperties=false。Registry内部冻结，对外返回副本。

统一 `executeTool(toolName, args, { db })` 中，db为内部依赖，不由客户端提供：

1. toolName必须同时属于Registry和固定handler映射，拒绝constructor、__proto__等非工具名。
2. args必须是普通JSON对象，禁止额外字段、继承参数、getter和非字符串参数。
3. 字符串trim后按Unicode码点验证。search query为1～50字符，dishId非空。
4. 调用静态导入的对应函数，集合名固定在实现中，不接受外部collection/实现路径。
5. 返回 `{ errCode: 0, ...toolResult }`；失败只返回固定errCode / errMsg，不记录原始DB异常或参数。

错误码：AGENT_TOOL_NOT_FOUND、AGENT_TOOL_ARGUMENT_INVALID、AGENT_TOOL_EXECUTION_FAILED。管理来源不允许时为AGENT_TOOL_FORBIDDEN。

没有eval、动态require用户路径、任意函数执行或模型结果注入。这里的简洁校验仅支持当前三种参数合同；未来增加复杂类型时必须同时扩展校验和测试，不能只增加schema就默认获得完整JSON Schema校验能力。

## 三个只读工具

### search_menu

输入：`{"query":"可乐"}`。

按数据库 `_id` 升序分页读取dishes，每页100条，对name、description和ingredients逐项进行大小写不敏感的字面子串匹配。不拆词、不用正则、不做LLM语义推断。搜索包括on_sale与sold_out，以当前status区分“记录存在”和“当前可购买”。

无匹配成功结果：

```json
{"errCode":0,"tool":"search_menu","query":"可乐","count":0,"items":[]}
```

只表示当前读取的菜单中没有字面匹配，不能转述为“餐厅确定没有可乐”。有匹配时items包含dishId、name、categoryId、price、status、spicyLevel，均取自本次DB读取。

### list_available_drinks

输入：`{}`。

依据已检查的categories初始化数据，真实分类名为“饮料”、初始ID为drink。代码不硬编码该ID，而是在运行时查询 `categories.name === '饮料'`，要求唯一分类，然后读取该ID下 `status === 'on_sale'` 的菜品。缺少或重名分类视为执行异常，不能伪装为空菜单；不修改分类数据。

结果形状：`{ errCode: 0, tool: 'list_available_drinks', count, items }`，items字段与search_menu相同，不生成“推荐你喝…”等话术。

**初始化文件中柠檬茶在售，酸梅汤售罄；这只是初始化文件的内容，不用于推断远程数据库当前完整状态。** 本次真实available结果仅返回柠檬茶，具体记录见下文。返回数量必须以当次DB查询为准，不能固定count=2。

### get_dish_detail

输入：`{"dishId":"dish-4"}`。

按真实 `_id` 精确查询，存在时：

```text
{
  errCode: 0, tool: 'get_dish_detail', dishId, found: true,
  item: { dishId, name, categoryId, description, price, status, spicyLevel, ingredients }
}
```

不存在时：`{ errCode: 0, tool: 'get_dish_detail', dishId, found: false, item: null }`。这是明确not-found业务结果，不伪造菜品，不把不存在当作数据库连接失败。售罄菜品详情仍可返回真实状态。

所有返回均显式选取字段，不展开数据库原始记录。字段损坏时安全失败，不提供不可信价格或静默吞掉异常。只读查询不是跨多页事务快照；价格和状态反映查询时刻，未来下单仍须独立重新校验。

## 已完成的真实uniCloud云端验收

**V5.1 Read-only Agent Tool Foundation已完成真实uniCloud云端验收。** 验收环境为阿里云空间xlimao，通过HBuilderX的agent-tool-admin执行。以下为开发者确认的三个真实结果，不是本地测试替身返回。

### Case 1：search_menu

管理入口输入：

```json
{"toolName":"search_menu","args":{"query":"可乐"}}
```

真实结果：

```json
{
  "errCode": 0,
  "tool": "search_menu",
  "query": "可乐",
  "count": 0,
  "items": []
}
```

结论：本次在当前真实菜单数据库中没有搜索到“可乐”的匹配记录。这是Menu Tool的数据库查询事实，Tool本身不生成“餐厅没有可乐”的自然语言结论，也不构成商品在现实中绝对不存在的通用判断。未来由Agent根据Tool Result组织回答，当前尚未实现该能力。

### Case 2：list_available_drinks

管理入口输入：

```json
{"toolName":"list_available_drinks","args":{}}
```

真实结果：

```json
{
  "errCode": 0,
  "tool": "list_available_drinks",
  "count": 1,
  "items": [
    {
      "dishId": "dish-4",
      "name": "柠檬茶",
      "categoryId": "drink",
      "price": 12,
      "status": "on_sale",
      "spicyLevel": 0
    }
  ]
}
```

结论：当前真实数据库的在售饮料查询返回柠檬茶。酸梅汤未进入本次available result；仅记录该返回事实，不据此额外推断酸梅汤当前数据库完整状态。

### Case 3：get_dish_detail

管理入口输入：

```json
{"toolName":"get_dish_detail","args":{"dishId":"dish-4"}}
```

真实结果：

```json
{
  "errCode": 0,
  "tool": "get_dish_detail",
  "dishId": "dish-4",
  "found": true,
  "item": {
    "dishId": "dish-4",
    "name": "柠檬茶",
    "categoryId": "drink",
    "price": 12,
    "status": "on_sale",
    "spicyLevel": 0,
    "description": "清爽柠檬香，适合搭配正餐。",
    "ingredients": ["红茶", "柠檬"]
  }
}
```

结论：详情Tool能读取当前真实dishes DB中的菜单详情、价格、状态和配料。这里的description是本次实时菜单字段，不是修改RAG知识源或让模型扩写证据。

### V5.1完成状态

```text
Tool Registry
 → Executor Allowlist
 → Read-only Menu Tools
 → Local Tests
 → Real uniCloud Validation
```

search_menu、list_available_drinks、get_dish_detail均已完成真实云端验证。**V5.1仍然不是Agent**；Function Calling、LLM Tool Selection、Agent Loop、Multi-step Tool Orchestration、Cart Tool、Order Tool和Agent UI均尚未实现，属于后续阶段。本次只固化验收结果，不进入V5.2。

## 为什么没有Cart / Order Tool

购物车是前端Pinia状态，当前云对象不能假装直接修改它。V5.3将来需专门设计pending action、用户确认与前端状态更新，V5.1没有add_to_cart/get_cart。

下单有业务副作用，未来必须有用户确认和后端校验。本阶段不注册create_order，不代理orders，不让模型创建订单。现有前端、menu、orders、ai、rag、知识源和评测集均不改。

## 未来“可乐”场景（尚未实现）

```text
用户：有可乐吗？没有的话推荐点别的喝的。
未来LLM选择 search_menu({query:'可乐'})
 → Server返回真实匹配结果
 → 如果无匹配，未来LLM可选择 list_available_drinks({})
 → Server返回真实在售饮料
 → 后续再决定是否需要知识工具
```

V5.1只保证这些Tool自身工作，不自动执行这段流程。未来LLM只能选工具和参数，不能声明或伪造Tool Result；后续推理只能使用服务器执行结果。真正Function Calling / Agent Loop留到V5.2，本次不实现。

## HBuilderX部署与按需复验（保留操作说明）

1. 保持当前项目绑定已验证的uniCloud空间；本阶段不初始化数据库、不重新上传现有业务云对象。
2. 上传部署新增agent云对象，确保tools目录随包上传。
3. 上传新增agent-tool-admin普通云函数。不需要Model Studio API Key或任何新环境变量。
4. 在HBuilderX对agent-tool-admin设置以下任一参数，选择“上传并运行云函数”。

```json
{"toolName":"search_menu","args":{"query":"可乐"}}
```

```json
{"toolName":"list_available_drinks","args":{}}
```

```json
{"toolName":"get_dish_detail","args":{"dishId":"dish-4"}}
```

5. 核对无匹配count=0/items=[]；饮料结果只包含当前真实在售饮料；详情价格、status、ingredients与云端dishes一致。
6. 可额外传未知tool或额外参数，确认得到安全错误；不要填入密钥。HBuilderX生成的云函数 `*.param.json` 已由现有规则忽略。

admin只接受平台context.SOURCE=server，agent诊断方法只接受function/server来源。此限制用于受信任开发部署环境，不等于uni-id管理员认证；不要新增面向普通客户端的任意转发代理。微信页面不会调用这些诊断方法，也没有agent.run/chat/executeGoal。

## 本地验证

```sh
node --test tests/*.test.cjs
pnpm run build:mp-weixin
pnpm run rag:check-source
git diff --check
```

新增测试覆盖三工具合同、输入校验、Unicode边界、分页、字段匹配、实时分类解析、售罄过滤、not-found、安全错误与管理来源。数据库为只读测试替身，不访问模型或远程DB。不新增依赖，不修改V4冻结文件。
