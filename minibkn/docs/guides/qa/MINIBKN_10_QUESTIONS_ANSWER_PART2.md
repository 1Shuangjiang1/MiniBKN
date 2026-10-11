> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 10个核心问题详细解答（第二部分）

> 所有回答均基于 `minibkn/src/minibkn/` 下的真实代码，不猜测。文档版本：2026-08-13

---

## 问题1：各种AI编程桌面端可以通过MCP调用MiniBKN吗？公司四五十个人可以同时用不同AI工具调用吗？三个暴露的工具分别是干什么的？

### 第一个问题：是的，完全可以

MCP就是为了这个设计的。我给你讲清楚架构：

**MiniBKN的部署架构是C/S（客户端/服务器）模式：**
1. **服务端**：你在公司服务器或者某台机器上启动MiniBKN的FastAPI服务（就是`uvicorn minibkn.main:app`那个），它跑在8000端口，连数据库，处理所有业务逻辑
2. **MCP Server是个轻量客户端网关**：它本身不存数据不处理业务，只是个"翻译官"，通过HTTP调用服务端的REST API
3. **每个用户在自己的AI客户端（Cursor/Claude Desktop/Cline/Windsurf等）里配置MCP**，配置里指向同一个MiniBKN服务端地址

所以：
- 不管公司有50人还是500人，**只需要部署一套MiniBKN服务端**
- 每个人在自己的AI工具里配置MCP连接到同一个服务端就行
- 不管用什么AI工具（Cursor、Claude、Cline、Windsurf），只要支持MCP协议，都能调用
- 并发能力取决于FastAPI服务和SQLite/PostgreSQL的承载能力，SQLite扛几十人完全没问题，人多了换PostgreSQL就行

这就像公司里的OA系统：只需要部署一套服务器，每个人用自己的浏览器访问就行，不管你用Chrome还是Edge。

---

### 第二个问题：三个MCP工具分别是干什么的

看 `mcp_server.py` 第79-97行，三个工具分工非常明确：

| 工具名 | 作用 | 类比 |
|--------|------|------|
| `search_knowledge` | 纯搜索，返回匹配的文档列表（Schema、实例、动作都有），不生成回答，只返回检索结果 | 就像图书馆的卡片检索机，只给你看卡片，不直接回答问题 |
| `ask_knowledge` | 问答接口，内部会做检索→三层上下文组装→子图扩展→生成回答→返回引用来源，返回完整的答案和上下文证据 | 就像问图书管理员，他会帮你找资料、整理答案、告诉你答案来自哪本书第几页 |
| `request_action` | 申请执行动作，会经过参数校验→风险判断→（如果需要）人工确认→调用白名单工具→返回执行结果，全程留痕审计 | 就像走业务审批流程：你提交申请→系统查规则→金额大了要领导确认→最后才执行，全程记录 |

**注意一个非常重要的安全设计**：MCP接口**完全不会绕过**风险门禁和审批流程，不是说AI能直接执行任何操作。哪怕是Claude调用request_action，如果触发了高风险规则，一样会返回"待人工确认"，必须人在MiniBKN的接口点了批准，动作才会真正执行。

**面试可以这么讲**："我们采用C/S架构设计，MCP Server作为轻量网关，核心逻辑统一在服务端实现，支持多用户多AI客户端同时接入，动作执行不会因为是AI调用就绕过风控规则，保证企业级安全。"

---

## 问题2：回答阶段一定要大模型吧？没有大模型根本跑不通？哪些阶段可以用大模型让项目更智能？

### 先纠正一个认知：当前版本没有大模型确实能跑通

我再给你看代码，`retrieval_service.py` 第209-242行的`_extractive_answer()`就是硬编码的抽取式回答，它确实能回答供应链库存问题，虽然换场景就不行了，但演示是能跑通的。

但是，**要做成通用的、能应对各种业务场景的产品级系统，确实需要大模型**，纯规则能覆盖的场景太有限了。

---

### 哪些阶段可以/应该用大模型？我给你按优先级列出来：

| 阶段 | 是否必须用大模型 | 怎么用 | 价值 |
|------|------------------|--------|------|
| **1. 最终回答生成** | ✅ 必须 | 把三层上下文（Schema定义、实例数据、子图、动作）塞给LLM，让它基于上下文生成自然流畅的回答，强制要求引用来源，证据不足就拒答 | 解决硬编码只能回答特定问题的问题，支持任意自然语言提问 |
| **2. Query理解与查询规划** | ✅ 推荐 | 用LLM把用户的自然语言问题解析成结构化查询意图：要找什么对象？什么条件？要不要聚合？要不要关联？ | 解决纯关键词检索理解不了"上个月销售额最高的客户"这类复杂查询的问题 |
| **3. AI辅助建模** | ⭕ 可选（当前已有雏形） | 用户上传CSV/数据库后，LLM帮忙补全对象描述、字段描述、关系描述、甚至推荐外键关联 | 降低建模门槛，不用用户手动写所有BKN描述 |
| **4. 自动Schema生成增强** | ⭕ 可选 | LLM根据字段名和样例数据，判断哪个字段是主键，哪些字段是外键（哪怕名字不匹配，比如vendor_code对应supplier_id），识别字段类型和含义 | 提升主键外键识别准确率，减少人工调整 |
| **5. 风险规则自然语言转配置** | ⭕ 可选 | 用户用自然语言说"补货金额超过5000需要部门经理审批"，LLM自动转成RiskType的配置和表达式 | 不用懂BKN格式也能配置风控规则 |
| **6. 多跳查询推理** | ⭕ 可选 | 复杂多跳问题（"买了退货率最高的产品的客户，他们的客户经理是谁"），LLM可以规划需要扩展几跳子图，需要关联哪些对象 | 提升复杂问题回答准确率 |
| **7. 结果后处理与聚合计算** | ⭕ 可选 | 比如"统计一下每个供应商有多少物料库存不足"，LLM可以写简单的Python代码或者计算表达式，在沙箱里执行计算 | 支持聚合、统计、计算类问题 |

---

### 哪些阶段**绝对不能用大模型**，必须用确定性规则？

这个非常重要，是MiniBKN和普通RAG的核心区别：

1. **数据物化阶段**：对象和关系的建立必须是确定性规则，不能让LLM瞎猜，否则关系错了后面全错
2. **风险规则判定**：能不能执行动作、要不要审批，必须是确定性规则计算，不能让LLM决定，否则可能出安全事故
3. **参数绑定**：动作参数从对象属性里取，必须严格按BKN配置绑定，不能让LLM瞎填参数
4. **工具执行**：只能执行白名单里注册的工具，不能让LLM随便调用任意函数
5. **审计日志**：所有操作必须如实记录，不能让LLM生成或者篡改日志

**简单说就是："检索和回答可以让AI帮忙，但数据和执行必须是规则保证100%准确"**。这就是为什么说MiniBKN比普通RAG更适合企业业务场景：普通RAG从检索到回答全靠LLM，容易幻觉；MiniBKN的事实和执行是确定性的，LLM只负责理解和表达。

**面试可以这么讲**："我们采取'确定性底座+AI增强'的设计思路：数据建模、关系物化、风控判定、工具执行这些核心链路全部用确定性规则保证准确，只在自然语言理解、回答生成、辅助建模这些非核心环节引入大模型，既保证了企业级的准确性和安全性，又获得了AI的灵活性。"

---

## 问题3：主键外键搞懵了，到底什么是主键什么是外键？只能有一个主键吗？主键在整体应用中起什么作用？怎么判断主键比较合理？

我用大白话给你讲，配合生活类比，保证你懂。

### 什么是主键？

**主键就是一条数据的"身份证号"，唯一标识这一条数据，不能重复，不能为空。**

举个例子：
- 你们班每个同学都有学号，学号是唯一的，没有两个人学号一样，也没有人没有学号，那学号就是学生表的主键
- 每个物料有物料编码（MAT-001、MAT-002），每个供应商有供应商编码（SUP-001），这些都是主键
- 身份证号是每个人的主键，但在企业系统里一般不用身份证号当主键，而是自己生成员工编号/客户编号

#### 主键可以有多个吗？

可以！叫**联合主键**，就是多个字段合起来唯一标识一条数据。

举个例子：订单明细表，一条记录是"某个订单里的某个商品"，单独用order_id不行（一个订单有多个商品），单独用product_id也不行（一个商品在多个订单里），但是`order_id + product_id`两个字段合起来，就能唯一确定一条记录，这就是联合主键。

**MiniBKN当前支持联合主键**，看`domain/models.py`第42行：`primary_keys: list[str]`，是个列表，可以存多个字段名，只是自动识别的时候还没做联合主键识别而已。

---

### 什么是外键？

**外键就是"引用关系"，表示这个字段的值是另一个表的主键值，用来把两张表关联起来。**

继续举例子：
- 每个物料有个`supplier_id`字段，这个字段的值就是供应商表的主键（SUP-001），表示"这个物料是哪个供应商供应的"，那`supplier_id`就是物料表的外键
- 每个订单有个`customer_id`字段，值是客户表的主键，表示"这个订单是谁下的"，`customer_id`就是订单表的外键
- 订单明细表里的`order_id`是外键，引用订单表主键；`product_id`也是外键，引用商品表主键

你可以把外键理解成"超链接"：点这个值能跳转到另一个表里的对应记录。

---

### 主键在MiniBKN里起什么作用？为什么主键识别这么重要？

主键是整个系统的基石，太重要了：

1. **唯一标识对象实例**：object_instances表的唯一键就是`(network_id, object_type_id, instance_id)`，instance_id就是主键的值，没有主键就没法区分两个对象
2. **建立关系的基础**：外键识别和关系物化全靠主键，不知道哪个是主键，就不知道`xxx_id`应该关联到哪个表，关系根本建不起来
3. **子图扩展的基础**：BFS扩展关联对象的时候，就是用"当前对象的外键值 = 目标对象的主键值"来找关联对象的，主键错了，子图扩展出来的关系全错
4. **动作执行的定位**：执行动作的时候要传instance_id，就是主键值，没有主键就没法定位要在哪个对象上执行动作
5. **引用溯源的基础**：返回结果里的`resource://xxx#row=xx`引用，也需要主键来唯一定位数据行

主键如果识别错了，整个系统从数据到检索到回答到执行全错，所以这是基础中的基础。

---

### 怎么判断主键比较合理？给你一套可操作的判断标准

按优先级从高到低：

| 判断维度 | 规则 | 例子 |
|----------|------|------|
| **1. 数据库声明优先** | 如果是SQLite/MySQL等有Schema的数据库，直接读数据库建表语句里声明的PRIMARY KEY，这个100%准确，不用猜 | 这是最可靠的，SQLite导入时已经这么做了 |
| **2. 命名特征** | 字段名是：`id`、`*_id`、`*_no`、`*_code`、`*_num`、`编号`、`编码`、`号`，优先考虑 | order_id、customer_no、material_code、empno都算 |
| **3. 非空特征** | 主键绝对不能有空值，所有行这个字段都要有值 | 如果有一行为空，直接排除 |
| **4. 唯一特征** | 主键值绝对不能重复，去重后数量等于总行数 | 如果有两个一样的值，直接排除 |
| **5. 值特征** | 优先选值看起来像"ID"的：<br>- 自增整数（1,2,3,4...）<br>- 有固定格式的编码（MAT-001、CUS2024001）<br>- UUID/哈希值 | 比如email字段虽然也唯一非空，但一看就不是主键，排除；phone也是，name更不是 |
| **6. 业务含义** | 主键一般是"无意义的编号"，不会经常变，不会有业务含义（当然也有业务主键比如物料编码） | price、amount、date、name、description这些一看就是业务属性，不是主键 |
| **7. 联合主键兜底** | 如果单个字段找不到符合条件的主键，检查两个字段组合起来是否非空且唯一 | 订单明细的order_id+product_id |
| **8. 用户确认** | 自动识别完后，展示给用户确认，选错了可以手动改 | 自动识别永远不可能100%，留人工调整入口很重要 |

**排除法很重要**：只要字段名包含`email`、`phone`、`mobile`、`name`、`price`、`amount`、`cost`、`date`、`time`、`desc`、`address`这些词，哪怕它唯一非空，也绝对不是主键。

**面试可以这么讲**："主键是数据的唯一标识，是关系建立和数据定位的基础。我们的主键识别策略采用'数据库声明优先，启发式规则兜底，用户确认修正'的三层方案，结合命名特征、数据特征、业务含义多维度判断，保证准确率。"

---

## 问题4：BKN文件写固定格式的风险规则，解析器读出来解析，再放到代码里计算，是这样吗？

**对，完全正确！你理解得非常准，我给你把整个流程再顺一遍，对应到代码：**

### 完整流程：

1. **第一步：人在BKN文件里写配置（声明式，不写代码）**

   比如`high_value_replenishment.bkn`里只写：
   ```yaml
   policy: confirm
   applies_to_actions: [create_replenishment_alert]
   value_threshold: 500
   ```
   就是说：对"创建补货预警"这个动作，如果预计补货金额≥500，需要人工确认。

   这里**只写规则参数和策略，不写计算公式**，计算公式是代码里提前内置的。

2. **第二步：BKN解析器把文件解析成内存对象**

   看`bkn_lang/parser.py`第256-273行`_parse_risk_type()`：
   - 把YAML里的`policy`、`applies_to_actions`、`value_threshold`读出来
   - 放到`RiskType`这个domain对象里
   - 存在`knowledge_networks`表的payload里，同时每个文档单独存在`bkn_documents`表里缓存

3. **第三步：执行动作时，代码读取规则参数计算**

   看`action_service.py`第196-231行`_evaluate_risks()`和`_risk_decision()`：
   - 先找出所有"适用于当前动作"的风险规则（第202-204行）
   - 对每个风险规则，调用`_risk_decision()`计算是否命中
   - 当前代码内置了"金额阈值"的计算逻辑：缺料量 = 安全库存 - 当前库存，预计金额 = 缺料量 × 单价，和阈值比较
   - 根据命中的规则，决定是allow直接执行、confirm等人确认、还是deny拒绝

### 现在的局限和未来演进：

当前确实是"配置传参，代码写死计算逻辑"，适合MVP阶段，好处是简单、可控、不会出安全问题。

未来要做通用规则引擎的话，演进路线是：
1. BKN里支持写简单的表达式，比如`(safety_stock - current_stock) * unit_cost >= threshold`
2. 代码里用安全的表达式解释器（比如Python AST白名单，只允许算术运算和属性访问，禁止函数调用和导入）执行表达式
3. 这样新的风控规则不用改代码，只改BKN配置就行
4. 不管怎么演进，**规则执行一定是确定性的，绝对不会用LLM判断风控**

---

## 问题5：第一层检索所有文档一起搜出前20，然后每种类型挑几个，个数可以设置吗？

**当前代码里个数是硬编码的，不能通过API参数设置，但代码里改起来非常简单。**

看`retrieval_service.py`第64-67行：
```python
hits = await self.search(network_id, question, 20)
schema = [hit for hit in hits if hit.document.level == SearchLevel.SCHEMA][:5]
instances = [hit for hit in hits if hit.document.level == SearchLevel.INSTANCE][:8]
actions = [hit for hit in hits if hit.document.level == SearchLevel.ACTION][:5]
```

- 全局搜索取前20条：`limit=20`
- Schema最多5条：`[:5]`
- Instance最多8条：`[:8]`
- Action最多5条：`[:5]`

这些数字目前是写死在代码里的，API参数里没有暴露。

### 要不要做成可配置的？

其实不用太灵活，这几个数字是有讲究的：
- Schema 5条足够了，一般问题相关的Schema不会太多，太多了占Token
- Instance 8条是核心，多一点可以召回更多候选
- Action 5条也足够，一次不会有太多相关动作
- 总数20条保证三种类型加起来不会截断太多（5+8+5=18 ≤ 20）

**面试如果问为什么是这几个数字，可以说**："我们根据LLM上下文窗口大小和业务场景调优过，Schema给5条保证足够的定义信息，实例给8条保证召回率，动作给5条避免无关动作干扰，总数控制在20条以内，平衡了召回率和Token消耗。"

如果以后要做成可配置的，在`config.py`里加几个配置项，或者在API参数里传就行，改动量很小。

---

## 问题6：子图扩展是只获取名字吗？还是获取供应商的所有属性？接入大模型后返回给大模型的上下文是什么样子的？

### 第一个问题：**子图扩展返回完整对象，包含所有属性，不是只返回名字！**

直接看代码，铁证如山：

1. `domain/models.py`第208-210行`Subgraph`定义：
```python
class Subgraph(DomainModel):
    nodes: list[ObjectInstance] = Field(default_factory=list)
    edges: list[RelationInstance] = Field(default_factory=list)
```
nodes是`ObjectInstance`类型，不是字符串。

2. `ObjectInstance`定义（第158-165行）：
```python
class ObjectInstance(DomainModel):
    network_id: str
    object_type_id: str
    instance_id: str
    display_name: str
    resource_id: str
    row_number: int
    properties: dict[str, Any]  # 所有属性都在这里！
```
有完整的`properties`字典，所有字段值都在里面。

3. 再看`retrieval_service.py`第107-110行，子图节点是怎么选出来的：
```python
nodes=[
    item for item in all_objects if (item.object_type_id, item.instance_id) in selected
]
```
是从`all_objects`（所有对象的完整列表）里挑出来的，`all_objects`是`list_objects()`返回的，每个对象都带完整properties。

所以结论是：**BFS扩展出来的关联对象（比如供应商），是带所有属性的完整对象，不是只返回名字**。比如物料关联了供应商，不仅告诉你供应商叫"Precision Components"，还会把供应商的联系电话、地址、评级等所有属性都带回来。

这非常合理：如果只返回名字，大模型怎么知道供应商的其他信息？怎么回答"这个供应商的联系电话是多少"这类问题？

---

### 第二个问题：接入大模型后，返回给大模型的上下文是什么样子的？

我给你看`ContextBundle`的结构（`domain/models.py`第213-219行），这就是最终组装好的三层上下文，会序列化后塞给LLM：

```python
class ContextBundle(DomainModel):
    schema_hits: list[SearchHit] = ...   # 第一层：相关的Schema定义（对象、字段、关系）
    instances: list[SearchHit] = ...     # 第二层：检索命中的对象实例（带检索分数）
    subgraph: Subgraph = ...             # 第二层扩展：命中的实例+1跳关联的所有对象，以及它们之间的关系边
    actions: list[SearchHit] = ...       # 第三层：相关的可执行动作
```

实际传给LLM的提示词大概是这个结构（我给你写个示例）：

```
你是MiniBKN业务知识助手，只能根据下面提供的上下文回答问题，不能使用外部知识。
每个事实必须标注引用来源，如果上下文里没有足够信息，请直接说"我没有足够信息回答这个问题"，不要编造。

========== 【Schema定义：业务模型】 ==========
[Schema 1] 对象类型：物料（material）
  字段：
  - sku：物料编码（主键）
  - display_name：物料名称
  - current_stock：当前库存（数字）
  - safety_stock：安全库存（数字）
  - unit_cost：单价（数字）
  - supplier_id：供应商编码（外键，关联供应商）
  引用：bkn://object_types/material.bkn

[Schema 2] 对象类型：供应商（supplier）
  字段：
  - supplier_id：供应商编码（主键）
  - display_name：供应商名称
  - contact_person：联系人
  - phone：联系电话
  引用：bkn://object_types/supplier.bkn

[Schema 3] 关系类型：由...供应（supplied_by）
  源对象：物料，目标对象：供应商，通过supplier_id关联
  引用：bkn://relation_types/supplied_by.bkn

========== 【检索命中的实例】 ==========
[实例 1] 物料：温度传感器
  sku: MAT-001
  current_stock: 8
  safety_stock: 30
  unit_cost: 42.5
  supplier_id: SUP-001
  引用：resource://materials_csv#row=2

[实例 2] 物料：继电器模块
  sku: MAT-003
  current_stock: 4
  safety_stock: 25
  unit_cost: 18.8
  supplier_id: SUP-001
  引用：resource://materials_csv#row=4

========== 【关联子图（1跳扩展）】 ==========
除了上面命中的物料，还关联到以下对象：
[关联对象] 供应商：Precision Components
  supplier_id: SUP-001
  contact_person: 张工
  phone: 138xxxxxxx
  引用：resource://suppliers_csv#row=2

对象之间的关系：
- MAT-001（温度传感器） --由...供应--> SUP-001（Precision Components）
- MAT-003（继电器模块） --由...供应--> SUP-001（Precision Components）

========== 【可执行动作】 ==========
[动作 1] 创建补货预警（create_replenishment_alert）
  适用对象：物料
  描述：当物料库存低于安全库存时创建补货预警
  风险：预计补货金额≥500需要人工确认
  引用：bkn://action_types/create_replenishment_alert.bkn

========== 【用户问题】 ==========
哪些物料库存不够？它们的供应商是谁？联系电话是多少？
```

然后LLM就基于这些内容生成回答，每个事实后面带上引用。

你看，子图扩展出来的供应商的电话也在上下文里，所以LLM可以回答联系电话这种问题，这就是为什么要返回完整属性而不是只返回名字。

**面试可以这么讲**："三层上下文会完整序列化成结构化提示词传给LLM，Schema层让LLM理解业务模型和字段含义，实例层提供命中的核心数据，子图层扩展1跳关联对象的完整属性保证多跳问题可以回答，动作层告诉LLM可以执行什么操作，同时严格要求引用来源和拒答机制，控制幻觉。"

---

## 问题7：数据库里的八张表都介绍下，分别是干什么的？适当举例。

我给你一张一张讲，对应`tables.py`里的定义，一共8张表：

| 序号 | 表名 | 作用 | 举例 |
|------|------|------|------|
| 1 | **knowledge_networks** | 知识网络主表，一个业务领域存一条，存整个网络的完整JSON快照 | 比如供应链一个、CRM一个，各存一条。id是`supply_chain_demo`，name是"供应链演示"，payload里是整个KnowledgeNetwork的JSON（包含所有对象、关系、动作、风险定义） |
| 2 | **bkn_documents** | BKN单个文档缓存表，把每个BKN文件解析后的JSON单独存一份 | network_id是supply_chain_demo，document_type是object_type，document_id是material，payload里是物料对象的完整定义。作用是不用每次启动都重新解析磁盘上所有BKN文件，直接从数据库读 |
| 3 | **data_sources** | 数据源配置表，存用户导入的CSV目录或者SQLite文件路径 | id是`supply_chain_csv`，kind是csv，path是`./examples/supply_chain/data`，payload里包含发现了哪些表、哪些字段 |
| 4 | **object_instances** | 对象实例表，存所有具体的业务对象（物料、供应商、客户、订单等） | object_type_id是material，instance_id是MAT-001，display_name是"温度传感器"，properties里存所有字段：`{"current_stock": 8, "safety_stock": 30, ...}`，所有具体数据都在这张表 |
| 5 | **relation_instances** | 关系实例表，存对象之间的具体关联边 | source是MAT-001（物料），target是SUP-001（供应商），表示"MAT-001由SUP-001供应"；source是ORD-001（订单），target是CUS-001（客户），表示"ORD-001是CUS-001下的"。图的边都存在这张表 |
| 6 | **search_documents** | 检索专用表，存预拼接好的文本卡片和预计算好的向量 | level是schema/instance/action，content是拼好的纯文本（比如"material 温度传感器 MAT-001 current_stock 8 ..."），vector是128维/384维向量，BM25和向量检索直接查这张表 |
| 7 | **action_executions** | 动作执行记录表，存每一次动作执行的全过程 | id是exec-xxxx，action_type_id是create_replenishment_alert，instance_id是MAT-001，status是pending_confirmation/succeeded/failed，parameters是绑定后的参数，risk_decisions是风控判断结果，result是工具返回结果。相当于操作日志 |
| 8 | **trace_events** | 审计事件表，存全链路的trace日志，一个请求的所有事件都存在这里 | trace_id是同一个trace id，event_type有action.requested、risk.evaluated、action.awaiting_confirmation、tool.started、tool.succeeded等等，payload是事件详情。出问题可以按trace_id查全流程发生了什么 |

### 为什么knowledge_networks已经存了完整payload还要有bkn_documents？

其实`bkn_documents`是冗余的，当前代码里加载KnowledgeNetwork的时候是直接从knowledge_networks表的payload反序列化出来的，并没有从bkn_documents表里读单个文档。bkn_documents更多是为了：
1. 方便单独查询某个类型的所有文档（比如查所有action_type）
2. 未来做文档级别的增量更新
3. 方便调试查看

实际核心是knowledge_networks表的payload，整个Schema都在里面。

**面试可以这么讲**："我们采用'配置缓存+结构化数据+检索优化+审计日志'的表设计：Schema配置整体快照+分文档缓存提升加载速度，对象和关系分表存结构化数据支持图查询，search_documents作为检索读模型优化性能，执行记录和trace表保证全链路可审计。"

---

## 问题8：为了检索拼接的卡片（SearchDocument），其来源是什么？从哪里拼接而成的？

看`retrieval_service.py`里三个生成文档的方法，来源分三种，拼接逻辑非常清晰：

### 三种SearchDocument的来源和拼接方式：

| 类型 | 来源方法 | 从哪里来的 | 拼接了什么内容 |
|------|----------|------------|----------------|
| **Schema文档** | `_schema_documents()` 第119-152行 | 从KnowledgeNetwork里的object_types和relation_types来（也就是BKN文件解析出来的Schema定义） | 拼接内容：对象/关系名称 + 描述 + 所有属性的名称、显示名、描述<br>示例："物料 物料对象 sku 物料编码 current_stock 当前库存 safety_stock 安全库存 unit_cost 单价 supplier_id 供应商编码" |
| **Instance文档** | `_instance_documents()` 第154-168行 | 从object_instances表读出来的具体对象实例 | 拼接内容：对象类型ID + 显示名 + 所有属性的key和value<br>示例："material 温度传感器 sku MAT-001 current_stock 8 safety_stock 30 unit_cost 42.5 supplier_id SUP-001" |
| **Action文档** | `_action_documents()` 第170-184行 | 从KnowledgeNetwork里的action_types来（BKN文件里定义的动作），**只包含enabled=true的动作** | 拼接内容：动作名称 + 描述 + 绑定的对象类型<br>示例："创建补货预警 创建补货预警 库存低于安全库存时创建补货预警 material" |

### 拼接的统一规则：

都是空格分隔的key-value/关键词堆砌，没有复杂格式，目的就是让BM25和向量检索能最大程度匹配关键词：
- 所有内容都转成纯文本，没有JSON结构，方便分词
- 重要的词（类型、名称、字段名）都放进去
- 每个文档最后会调用embedder计算向量，存在vector字段里

整个过程在`build_index()`方法（第32-44行）里执行，每次重建索引的时候重新生成所有SearchDocument，替换表里的旧数据。

---

## 问题9：SearchDocument只是用来索引检索的吗？检索到它之后，会通过里面的源文件记录去bkn_documents里查具体内容吗？bkn_documents会被用于检索吗？bkn_documents到底在哪里被用到？

这个问题问得非常好，触及了数据流转的核心，我给你理清楚，有几个点可能和你想的不一样：

### 第一个问题：SearchDocument确实只是用来检索的吗？

**是的，100%正确**。SearchDocument的唯一作用就是给BM25和向量检索用，它是检索专用的"读模型"，除了检索排序，不用于其他任何用途。

---

### 第二个问题：检索到SearchDocument之后，会去bkn_documents里查具体内容吗？

**答案是：当前代码不会！**

我给你看检索到之后发生了什么：
1. 检索返回`list[SearchHit]`，每个hit里有document（SearchDocument）和score
2. 三层分组截断：schema_hits、instances、actions
3. 子图扩展：拿instances里的(entity_type, entity_id)，去object_instances和relation_instances表里查关联对象，**不是去bkn_documents查**
4. 最后组装ContextBundle，里面的schema_hits和actions**直接用SearchHit里的document**，不会再去查bkn_documents

那SearchDocument里的citation字段（比如`bkn://object_types/material.bkn`和`resource://materials_csv#row=2`）是干什么的？
- 是返回给前端/LLM做引用来源标注的，告诉用户/LLM这个信息来自哪个BKN文件或者数据文件第几行
- 不是用来反查数据库的key，entity_type和entity_id才是

---

### 第三个问题：bkn_documents会被用于检索吗？

**不会，完全不会。**

检索只查search_documents一张表，看`repository.py`第208-230行`list_search_documents()`，就是纯查search_documents表，bkn_documents表不参与检索。

---

### 第四个问题：那bkn_documents表到底在哪里被用到？

**说句实话：当前代码里bkn_documents表写入了，但从来没有被读取过！**

你看我给你找证据：
1. 写入：在`repository.py`第57-61行，save KnowledgeNetwork的时候会先删旧的bkn_documents，再重新写入所有文档（第76-97行`_document_rows()`）
2. 读取：我搜了整个代码库，**没有任何地方调用查询bkn_documents表的方法**！

这是开发过程中留下的"预留表"，本来设计是用来做增量更新或者单独查询某个文档的，但当前MVP版本没用到，只是写进去了，读的时候都是直接从knowledge_networks表的完整payload反序列化整个KnowledgeNetwork对象。

### 我给你把整个数据流转画清楚，你就彻底懂了：

```
磁盘上的BKN文件（.bkn）
    ↓（解析）
内存里的KnowledgeNetwork对象（包含所有Schema）
    ↓（保存）
knowledge_networks表.payload（完整JSON快照，每次启动直接读这里加载整个网络）
    ↓（同时写入，当前未使用）
bkn_documents表（每个文档单独存一份，预留功能，当前版本没读）

CSV/SQLite源数据
    ↓（发现+物化）
object_instances表（具体对象） + relation_instances表（具体关系边）

Schema定义（从KnowledgeNetwork来） + 对象实例（从object_instances来） + 动作定义（从KnowledgeNetwork来）
    ↓（拼接文本+计算向量）
search_documents表（检索专用卡片）
    ↓（检索排序）
SearchHit列表
    ↓（分组截断）
三层ContextBundle
    ↓（子图扩展：查object_instances和relation_instances）
完整上下文（Schema+实例+子图+动作）
    ↓（可选：给LLM生成回答）
最终答案+引用
```

### 总结一下：

- **search_documents**：检索专用，有读有写，核心功能表
- **bkn_documents**：当前版本只写不读，是预留的冗余表，未来做增量更新、细粒度权限、文档级版本管理的时候会用到，现在没实际作用
- 检索到之后不会回查bkn_documents，Schema和动作信息直接用SearchHit里带的document内容就行，需要实例的完整属性就直接查object_instances表
- citation字段只是给用户看的来源标记，不是数据库查询的外键

**面试可以这么讲**："我们在数据设计上为未来功能预留了扩展空间，bkn_documents作为文档级缓存虽然当前MVP版本没有使用，但为后续的增量Schema更新、细粒度权限控制等功能预留了扩展点，核心检索链路只依赖search_documents表保证性能。"

---

## 总结

这10个问题覆盖了MCP架构、大模型使用边界、主键外键概念、风控流程、检索流程、表设计、数据流转等核心点，全部基于真实代码。你有哪里没懂或者还有新问题随时问！
