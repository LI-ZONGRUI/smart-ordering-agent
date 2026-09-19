# 知识源 V1 人工审核说明

`knowledge-source.json` 已完成对 `dishes.init_data.json` 与 `src/constants/dish.js` 的人工逐条审核，21 条 Knowledge Source V1 均已确认，`verified` 已统一设为 `true`，`sourceVersion` 仍为 `1`。Knowledge Source V1 已冻结，可作为下一阶段 Embedding 的正式输入。它只依据仓库中的初始化数据与字段定义，不代表已经核对当前云数据库或实际出餐配方。没有 embedding，也未接入任何运行代码。

## 来源与追溯

实际读取的文件：

- `uniCloud-aliyun/database/dishes.init_data.json`：8 道菜的 ID、名称、描述、配料和辣度。
- `src/constants/dish.js`：`spicyLevelLabels` 的 0～5 索引文案。
- `uniCloud-aliyun/database/dishes.schema.json`：辣度整数范围、配料数组等字段定义。
- `src/pages/dish-detail/index.vue`：确认 `ingredients` 在现有页面称为“主要配料”，`spicyLevel` 通过标签数组显示。

每条 `sourceFields` 是来源定位列表：`file` 为项目根目录相对路径，`recordId` 按初始化数组记录的 `_id` 定位，`fields` 为依据的字段；常量和 schema 使用字段路径。`dishId` 直接采用原 `_id`。知识 ID 不以价格或售卖状态命名。

本次来源文件 SHA-256（用于识别审核所依据的文件版本）：

| 文件 | SHA-256 |
| --- | --- |
| dishes.init_data.json | `109c05d5e05134cfd049201edc11913a65e5a23f7e13e7d3e3148550eb018a6a` |
| dish.js | `e4c7be9ff574177017846ec5fe25e6d4af9be4854f88baba89b7121e48bcd971` |
| dishes.schema.json | `6e8d0ae380c1ddeb9b9e99118cdefa23b747b4ecbb0873e2ef8dcc6f736316c4` |
| dish-detail/index.vue | `714cce9e3e36569eed04c782ed5a998a79a2b29b5fef36173b9b09452c77bcee` |

## 数量与取舍

| 类型 | 菜品级 | 餐厅级 | 合计 |
| --- | ---: | ---: | ---: |
| description | 6 | 0 | 6 |
| taste | 6 | 1 | 7 |
| ingredients | 8 | 0 | 8 |
| 合计 | 20 | 1 | 21 |

- 每道菜均保留一条完整的主要配料记录；没有拆分单个配料来增加数量。8 条菜品级 spicy-level 知识已删除，不补充新知识。
- taste 的菜品级记录仅保留 6 条原描述中的风味或口感，knowledgeId 统一为 `dish-N-taste`（原 `dish-N-flavor`）。正文统一明确归因于“项目描述为……”，不作为已验证的客观口味结论。
- 柠檬茶（dish-4）、酸梅汤（dish-8）没有生成 description：原描述除风味外主要是搭配或主观效果建议，没有额外、明确且适合独立成块的菜品介绍。其风味保留在 taste 中。
- 香辣鸡丁（dish-5）、双椒牛肉（dish-6）在删除菜品级辣度记录后不再保留 taste；不补充“下饭”“锅气十足”等主观文案。
- 保留 `restaurant-spicy-level-definitions`，该条 restaurant 级 taste 记录完整的辣度 0～5 定义，内容不变。它描述项目统一标签，不代表已测量餐厅实际辣度。
- 保留全部 8 道菜的长期描述资料，不按初始化时的售卖状态筛选。知识正文与来源字段中均不收录 price、status、sales；也不把推荐或交易规则写成知识。

## 审核后保留的歧义与边界

1. `ingredients` 只显示为“主要配料”，没有完整配方声明。“油醋汁”“青菜”等也没有进一步成分或品种信息。不得补充推测成分，不得把未列出视为不含某食材或过敏原。
2. `description` 混合事实与营销、主观表达。已去掉“饱腹又满足”“开胃”“轻盈”“适合搭配正餐”“下饭”“锅气十足”“解腻”“冰镇风味更佳”等内容，不推导营养、功效、官方搭配或固定出餐温度。
3. `spicyLevel` 是项目标签，未定义客观测量方式或统一体感标准。“不辣”不能推导为无辣椒或过敏安全。知识源只保留统一标签定义，不再保存单道菜的辣度记录。
4. 双椒牛肉的“青红椒”依据 `ingredients` 中的“青椒”“红椒”展开；拍黄瓜的“蒜香酱汁”来自 description，不能推定酱汁的完整配方。
5. “快炒”“拌”等仅在原 description 明确出现时保留，没有补充温度、时间、器具或其他制作步骤。

本次人工审核已逐条核对正文与 `sourceFields`，21 条均已确认并标记为已审核。此确认仅针对现有项目数据的可追溯性，不消除上述数据歧义。V1 已冻结，本次仅更新审核标记，未修改知识正文、其他字段或 `sourceVersion`；未开展任何 V4.2 工作。
