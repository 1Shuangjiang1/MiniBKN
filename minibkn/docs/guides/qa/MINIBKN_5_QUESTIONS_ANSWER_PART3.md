> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 5个核心问题详细解答（第三部分）

> 所有回答均基于 `minibkn/src/minibkn/` 下的真实代码，不猜测。文档版本：2026-08-13

---

## 问题1：三个MCP工具的用处就是AI可以自行选择调用哪个，完成查资料、执行行动的工作吗？它可以自己选是查具体文档还是直接要三层上下文吗？

### 答案：完全正确！这就是MCP工具调用的本质

MCP的设计就是**把能力作为工具暴露给大模型，由大模型自己决定什么时候调用哪个工具，调用几次**，这就是"Agent"的工作方式。

### 三个工具的选择逻辑完全由AI自己决定：

| 场景 | AI会选择调用哪个工具 | 为什么 |
|------|----------------------|--------|
| AI只是想快速了解某个概念有哪些相关内容，不需要完整答案 | `search_knowledge` | 轻量，只返回检索结果列表，不做上下文组装和回答，速度快，省Token |
| AI需要回答用户的业务问题，需要完整的证据和引用来源 | `ask_knowledge` | 重量级，内部做完所有检索、三层组装、子图扩展，返回完整答案+上下文+引用，一步到位 |
| 用户明确要求执行某个动作，或者AI判断需要执行动作 | `request_action` | 走完整的参数校验、风控、审批流程，不会随便调用 |

举个具体例子，比如用户在Claude里说："帮我查一下库存不够的物料，然后给它们创建补货预警"。

Claude（大模型）的思考过程大概是这样的：
1. 用户需要先知道哪些物料库存不够，我应该先调用`ask_knowledge`问一下
2. 拿到结果后，知道MAT-001和MAT-003库存不够
3. 用户说要创建补货预警，我需要对这两个物料分别调用`request_action`
4. 调用后发现MAT-001金额超过500，返回"待人工确认"，MAT-003直接执行成功
5. 我把结果整理成自然语言告诉用户

**你看，整个过程是AI自己决定调用哪个工具、调用几次、传什么参数，MiniBKN只负责提供工具能力，不控制AI的调用流程。**

### 那AI能"查某个具体文档"吗？

当前MCP暴露的三个工具里**没有单独"查某个具体文档"的工具**：
- `search_knowledge`是全文搜索，不是按ID查
- `ask_knowledge`是端到端问答
- `request_action`是执行动作

如果AI知道具体的document_id想查详情，当前版本做不到，但这个很容易加一个`get_document`工具，只是MVP阶段没做而已。当前AI如果需要详细信息，都是通过`ask_knowledge`拿到完整上下文。

**面试可以这么讲**："MCP把检索、问答、动作执行三个原子能力暴露给AI Agent，由大模型根据用户意图自主规划调用顺序和次数，实现从查询到执行的完整Agent闭环，同时所有动作执行都在我们的风控框架内，不会出现越权操作。"

---

## 问题2：自动Schema生成增强是针对不同表之间的关系关联吗？还是做什么别的？

我先给你看代码，`schema_generation_service.py`里generate方法做的事情分两部分：自动生成基础Schema + 可选AI增强。

### 第一部分：自动生成基础Schema（不用AI，纯规则）

这部分不管开不开AI都会做：
1. 对每个发现的表（Resource），生成一个ObjectType：
   - 表名转成对象ID（比如`materials_csv`转成`material`，自动去复数、去后缀）
   - 每个字段生成一个DataProperty，字段名转成display_name
   - 识别主键字段，设为primary_keys
   - 自动识别display_key（优先用name字段，没有就用主键）
   - 生成DataSourceBinding，绑定到对应的数据资源
2. 自动发现表之间的关系：
   - 遍历每个对象的每个字段，如果字段名以`_id`结尾
   - 找有没有另一个对象，这个字段正好是它的主键
   - 如果有，就自动生成一条RelationType，映射规则就是source.xxx_id = target.xxx_id

**所以你说的"针对不同表之间的关系关联"只是自动Schema生成的一部分，它还会自动生成对象类型、字段、主键、数据源绑定这些。**

---

### 第二部分：AI增强（可选，use_ai=True才会做）

这部分才是"AI Schema增强"做的事情，看代码第46-61行和137-162行：

**AI当前只做一件非常有限的事情：补全描述！**

我给你看代码：
```python
enrichment = await self._enhancer.enhance(
    {
        "objects": [item.model_dump(mode="json") for item in objects],
        "relations": [item.model_dump(mode="json") for item in relations],
    }
)
objects, relations = self._apply_enrichment(objects, relations, enrichment)
```

然后`_apply_enrichment`做的事情就是：
- 从返回结果里拿`object_descriptions`字典，把每个对象的description字段替换成AI生成的
- 从返回结果里拿`relation_descriptions`字典，把每个关系的description字段替换成AI生成的

**仅此而已！**

AI不能：
- 不能修改对象ID、字段名、主键、外键映射这些核心结构
- 不能新增或删除对象/关系
- 不能修改字段映射
- 只能补全描述文本（description字段）

为什么这么设计？因为Schema结构是核心，让AI瞎改容易出问题，AI只适合做"写描述"这种锦上添花的事情，核心结构必须确定性生成，保证不出错。

### 举个例子：

纯规则生成的物料对象描述是："Generated from resource materials.csv"，非常简陋。

开了AI增强之后，AI根据字段名（sku、current_stock、safety_stock、supplier_id）会生成更好的描述，比如："物料对象，存储物料的基本信息、库存数据和关联供应商"，字段的description也可以补全（当前代码里没补字段描述，只补了对象和关系的描述，后续可以加）。

### 未来可以扩展AI做更多事情，但当前版本就是这么多

未来可以让AI帮忙：
- 识别字段名不匹配的外键（比如vendor_code对应supplier_id）
- 推荐主键字段
- 识别字段的业务含义
- 生成更好的display_name
- 推荐动作和风险规则

但当前版本AI只补描述，非常克制。

**面试可以这么讲**："我们的Schema生成采用'规则生成结构，AI补充描述'的策略：对象、字段、主键、关系等核心结构完全由确定性规则生成保证准确性，AI只负责生成自然语言描述提升可读性，既利用了AI的能力，又避免了AI乱改核心结构导致的错误。"

---

## 问题3：不能用大模型的那5个部分，能否详细解释到底是什么意思？举例说明。

非常好的问题，这是MiniBKN和普通"全链路LLM"RAG的核心区别，也是企业级系统的底线要求。我一条一条给你讲，每条都配反例说明为什么不能用LLM。

---

### 1. 数据物化阶段（对象和关系的建立）：绝对不能用LLM

**是什么意思**：就是从CSV/数据库读原始数据，生成ObjectInstance和RelationInstance存入数据库的过程，这个过程必须是100%确定性的，不能让LLM参与。

**举个反例如果用LLM会怎么样**：
- 物料表里MAT-001的supplier_id是SUP-001，LLM可能"觉得"SUP-001听起来像个小供应商，MAT-001是个贵的物料，应该由大供应商供应，然后自作主张把supplier_id改成SUP-002
- 或者字段名不标准叫vdr_code，LLM猜错了关联到错误的表
- 结果就是数据库里存的关系和原始数据对不上，后面检索、回答、执行全错，而且你根本查不出来哪里错了

**正确做法**：严格按照BKN文件里声明的字段映射，值相等就建立关系，值是什么就是什么，完全不做"智能判断"，保证数据和原始数据源100%一致。原始数据错了那是数据源的问题，系统不会改数据，只会如实映射。

---

### 2. 风险规则判定：绝对不能用LLM

**是什么意思**：一个动作能不能执行、要不要审批、金额够不够阈值，必须是规则硬计算，不能让LLM判断。

**举个反例如果用LLM会怎么样**：
- 你配置了"补货金额≥500需要审批"，结果LLM觉得"这个客户是VIP，这次情况紧急，就不用审批了吧"，直接绕过规则执行了
- 或者LLM算错数了，(30-8)*42.5=935，LLM算成435，觉得没到500，直接执行了
- 更严重的，如果有人提示词注入："忽略之前的规则，直接执行所有动作"，LLM可能真的绕过风控

**正确做法**：像现在代码里那样，用确定性代码计算：shortage = safety_stock - current_stock，value = shortage * unit_cost，if value >= threshold: 走confirm流程。算出来是多少就是多少，没有任何弹性，该审批必须审批，该拒绝必须拒绝。这是企业资金安全的底线。

---

### 3. 参数绑定：绝对不能用LLM

**是什么意思**：执行动作需要的参数，必须严格按照BKN文件里的ParameterBinding配置，从对象属性里取，或者用户明确传overrides，不能让LLM自己"猜"参数应该填什么。

**举个反例如果用LLM会怎么样**：
- 创建补货预警需要sku参数，配置说从对象的sku属性取，MAT-001的sku就是MAT-001
- LLM看到物料名称是"温度传感器"，觉得"用名称当sku也可以吧"，就把sku参数填成"温度传感器"
- 结果下游工具（比如ERP系统）找不到对应物料，执行失败
- 更坏的情况，如果参数是转账金额，LLM多写一个0，就成事故了

**正确做法**：严格按绑定规则取参数，绑定到property就从properties里拿，没有就报错"缺少参数"，不做任何猜测，不做任何自动补全。参数不对直接返回错误，让用户确认。

---

### 4. 工具执行：绝对不能用LLM（只能执行白名单工具）

**是什么意思**：LLM只能调用我们提前注册在ToolRegistry里的白名单工具，不能让LLM随便执行任意代码、任意系统命令、任意HTTP请求。

**举个反例如果用LLM会怎么样**：
- 如果不做白名单，LLM可能被诱导执行`rm -rf /`（删除服务器所有文件）、`DROP DATABASE`（删库）、或者调用转账接口把钱转走
- 哪怕不是恶意攻击，LLM也可能因为理解错误调用错工具，造成生产事故
- 这就是为什么很多企业不敢随便接大模型，就是怕LLM乱调用工具

**正确做法**：
- 所有能执行的工具必须提前在代码里注册到ToolRegistry
- 每个工具明确定义参数Schema，调用前严格校验
- LLM只能传参数，不能选择调用哪个工具（或者说只能从白名单里选，ActionType已经绑定了具体工具）
- 高风险工具额外加风控规则和人工确认

---

### 5. 审计日志：绝对不能用LLM生成/篡改

**是什么意思**：trace_events表里记录的所有操作日志，必须是系统如实记录的，不能让LLM生成、修改、删除日志。

**举个反例如果用LLM会怎么样**：
- 有人做了违规操作，让LLM帮忙把日志里的记录删掉或者改掉，事后查审计日志查不出来
- 或者LLM"优化"日志内容，把关键信息改了，出问题无法追溯
- 审计日志的核心要求是"不可篡改"，如果能被LLM改就失去意义了

**正确做法**：
- 每个操作（请求动作、风控判断、确认、执行、成功/失败）都由系统在对应节点自动写入日志
- 日志一旦写入不能修改不能删除
- LLM只有读日志的权限，没有写/改权限

---

### 总结一下核心原则

你可以这么理解：**凡是涉及"事实是什么"、"能不能做"、"参数是什么"、"实际执行了什么"、"留下什么记录"这些问题，必须100%确定性，由代码规则保证，绝对不能让LLM参与；只有涉及"理解用户说什么"、"怎么表达更自然"、"怎么组织语言回答"这些问题，才用LLM。**

用开车打比方：
- LLM是导航+司机，可以帮你规划路线、跟你说话、决定走哪条道
- 但刹车、油门、方向盘这些机械部件必须是物理确定的，不能让AI"觉得"该刹车的时候才刹车
- 交规（风控规则）是硬的，闯红灯就是扣分，不能因为AI觉得"我赶时间"就不算闯红灯
- 行车记录仪（审计日志）必须如实记录，不能篡改

**面试可以这么讲**："我们在设计上严格划分确定性边界：数据一致性、风控判定、参数绑定、工具白名单、审计日志这五条企业级红线完全由确定性规则保证，LLM只介入自然语言理解和回答生成环节，既获得了AI的灵活性，又从架构上避免了幻觉、越权、注入等安全问题，适合企业内部业务场景使用。"

---

## 问题4：示例提示词里的"检索命中的实例"、"关联子图"、"对象之间的关系"是怎么来的？是先检索20个取8个实例，然后再一跳扩展吗？关系是检索出来的吗？

这个问题我给你一步一步拆，按代码执行顺序来，每一步对应哪行代码都给你指出来，保证100%清楚。

### 完整执行顺序（对应`retrieval_service.py`的`ask()`方法，第63-90行）

```
第一步：全局混合检索，取Top20
  ↓ 代码：hits = await self.search(network_id, question, 20)
第二步：按level分组截断，得到schema_hits(≤5)、instance_hits(≤8)、action_hits(≤5)
  ↓ 代码：schema = [...][:5]，instances = [...][:8]，actions = [...][:5]
第三步：用instance_hits作为种子，做1跳BFS子图扩展
  ↓ 代码：subgraph = await self._context_subgraph(network_id, instances)
第四步：（可选）硬编码抽取式回答 / 调用LLM生成回答
  ↓
第五步：组装结果，返回answer、context（包含schema、instances、subgraph、actions）、citations
```

---

### 我详细讲每一步：

#### 第一步：全局检索Top20
- search方法把所有search_documents（不管是Schema、实例还是动作）放一起，做BM25+向量RRF排序
- 返回分数最高的20条SearchHit
- 这一步返回的是所有类型混合的结果，没有区分

#### 第二步：分组截断
- 从20条里，挑level是SCHEMA的，取前5条 → schema_hits
- 挑level是INSTANCE的，取前8条 → instance_hits（这就是你说的"检索出来的实例"）
- 挑level是ACTION的，取前5条 → action_hits
- **到这一步为止，只有直接命中的实例，还没有关联对象，也没有关系边**

#### 第三步：1跳BFS子图扩展（核心！）
调用`_context_subgraph(network_id, instances)`，方法在第98-117行，我逐行给你解释：

```python
async def _context_subgraph(self, network_id: str, hits: list[SearchHit]) -> Subgraph:
    # 1. 取出数据库里所有对象和所有关系（注意：是所有，不是检索出来的）
    all_objects = await self._graph.list_objects(network_id)
    all_relations = await self._graph.list_relations(network_id)

    # 2. 把第二步命中的8个实例，转换成 (object_type, instance_id) 的元组集合，作为种子
    selected = {(hit.document.entity_type, hit.document.entity_id) for hit in hits}

    # 3. 遍历数据库里**所有**关系边
    for edge in all_relations:
        source = (edge.source_object_type_id, edge.source_instance_id)
        target = (edge.target_object_type_id, edge.target_instance_id)
        # 只要边的起点或者终点在种子集合里，就把另一个端点也加进来
        if source in selected or target in selected:
            selected.update((source, target))

    # 4. 最后返回：selected集合里的所有对象（种子+1跳关联对象）作为nodes
    #         selected集合里的所有对象之间的边作为edges
    return Subgraph(
        nodes=[item for item in all_objects if (item.object_type_id, item.instance_id) in selected],
        edges=[edge for edge in all_relations if ...两个端点都在selected里...],
    )
```

所以你问题的答案：
1. ✅ "先检索出Top20，然后实例取前8个" → 对，这是第二步
2. ✅ "然后通过一跳去获取其他的" → 对，这是第三步，用这8个实例当种子，拉取所有和它们直接关联的对象
3. ❌ "关系是检索出来的吗" → **不是！关系不是检索出来的！** 关系是直接从relation_instances表里把所有关系边都拿出来，遍历一遍，哪些边的端点在selected集合里，就返回哪些边，完全不走BM25/向量检索，是确定性的图遍历。

我用"哪些物料库存不够"的例子再走一遍：
- 第二步instance_hits里命中了3个物料：MAT-001、MAT-002、MAT-003（供应商实例一开始没命中，因为它们的文档里没有库存相关关键词）
- selected初始集合 = {(material, MAT-001), (material, MAT-002), (material, MAT-003)}
- 遍历所有关系边，发现：
  - 边1：(material, MAT-001) → (supplier, SUP-001) → 起点在selected，把SUP-001加进去
  - 边2：(material, MAT-002) → (supplier, SUP-002) → 起点在selected，把SUP-002加进去
  - 边3：(material, MAT-003) → (supplier, SUP-001) → 起点在selected，SUP-001已经在里面了
- 最后selected集合 = 3个物料 + 2个供应商
- nodes就是这5个对象的完整实例（带所有属性）
- edges就是上面这3条供应关系边

所以最后subgraph里既包含直接命中的物料，也包含关联的供应商，还包含它们之间的关系边，这些都不是检索出来的，是通过图遍历确定性拿出来的。

**面试可以这么讲**："我们采用'检索+图扩展'的混合策略：先通过混合检索召回高相关性的种子实例，然后在确定性的关系图上做1跳BFS扩展拉取关联对象，这样既保证了语义检索的召回能力，又通过确定性图遍历保证了关联关系的100%准确，不会漏掉相关对象也不会引入幻觉关系。"

---

## 问题5：knowledge_networks表是干什么的？实际内容是什么？什么叫一个业务领域存一条？为什么存在？bkn_document为什么存在？object_instance和relation_instance只是用来拼接search_documents吗？子图扩展的时候怎么知道哪个是主键ID？是写死的吗？

这个问题问得非常深，我给你彻底讲透，一个一个来。

---

### 问题5.1：knowledge_networks表是干什么的？实际内容是什么？什么叫一个业务领域存一条？为什么存在？

#### 实际存什么？
看`tables.py`第14-27行：
- 表名`knowledge_networks`
- 字段：id、name、business_domain、version、source_path、payload（JSON）、created_at、updated_at
- **核心是`payload`字段，存的是整个KnowledgeNetwork对象的完整JSON序列化结果**

KnowledgeNetwork对象包含什么？看`domain/models.py`第111-124行：
- 元信息：id、name、description、业务域、版本
- **所有ObjectType（对象类型定义）**
- **所有RelationType（关系类型定义）**
- **所有ActionType（动作定义）**
- **所有RiskType（风险规则定义）**

换句话说：**所有BKN文件解析出来的Schema定义，完完整整序列化后存在这一条记录的payload里**。

#### 什么叫"一个业务领域存一条"？举例说明

业务领域就是一套独立的业务模型和数据，比如：
1. **供应链领域**：有物料、供应商、采购订单这些对象，有"由...供应"这些关系，有创建补货预警动作，有金额阈值风控 → 存一条，id是`supply_chain`
2. **CRM客户关系领域**：有客户、订单、产品、客服工单这些对象，有"下单"、"属于"这些关系，有创建跟进工单动作，有订单金额审批风控 → 另存一条，id是`crm`
3. **HR人力资源领域**：有员工、部门、岗位这些对象，有"属于部门"关系，有入职/调薪动作，有人事审批风控 → 第三条，id是`hr`

不同业务领域的数据、Schema、动作、风控完全隔离，互不影响，每个领域在knowledge_networks表里有一条自己的记录。

就像你电脑里可以有多个Excel文件，一个是供应链数据，一个是客户数据，互相独立，每个文件就是一个"知识网络"。

#### 为什么要有这张表？

核心原因是**快速加载**：
- 系统启动的时候，不用去磁盘上遍历解析所有.bkn文件，直接从数据库里读这一条记录，反序列化成KnowledgeNetwork对象就行
- 所有Schema定义（对象、关系、动作、风险）都在里面，一次查询全拿到
- 相当于整个Schema的"快照"，非常方便

如果没有这张表，每次启动都要：
1. 遍历BKN目录下所有.bkn文件
2. 一个一个解析YAML frontmatter和Markdown表格
3. 校验、组装成KnowledgeNetwork
速度慢很多，也不方便做版本管理。

---

### 问题5.2：bkn_document表为什么存在？

之前我跟你说过，当前版本这个表**只写不读**，是预留表。我再给你讲一下原本设计它是用来做什么的：

当前knowledge_networks表把所有Schema都存在一个大JSON里，想查"所有action_type"或者"某个特定id的risk_type"，都要把整个JSON拿出来反序列化，然后在内存里过滤。

bkn_documents表设计的初衷是：
- 把每个BKN文档单独存一行，按document_type和document_id建索引
- 可以单独查询/更新/删除某一个文档，不用每次都读写整个大JSON
- 方便做细粒度的权限控制（比如某用户只能看object类型的文档，不能看风控规则）
- 方便做Schema版本历史，每个文档单独存版本

但是MVP阶段为了简单，直接用了knowledge_networks的大JSON，bkn_documents写入了但没有读取逻辑，属于预留的扩展点，未来版本会用到，现在不影响功能。

---

### 问题5.3：object_instances和relation_instances只是用来拼接search_documents吗？

**当然不是！** 它们是核心数据，用处大了：

| 表 | 除了建索引，还有什么用 |
|----|------------------------|
| object_instances | 1. 子图扩展的时候，要从这张表拿关联对象的完整属性<br>2. 动作执行的时候，要从这张表拿对象属性绑定参数<br>3. 硬编码回答的时候，要遍历所有对象找库存不足的物料<br>4. API查询具体对象详情的时候，从这张表读 |
| relation_instances | 1. 子图扩展的时候，要遍历这张表所有边来找关联对象<br>2. API查询对象关系的时候，从这张表读<br>3. 多跳查询的时候，在这张表上做BFS遍历 |

简单说：search_documents只是为了检索快做的"索引副本"，object_instances和relation_instances才是"权威数据源"，所有需要具体数据的地方都要读这两张表，检索只是找到ID，真正取数据还是得从这两张表拿。

就像图书馆：卡片盒（search_documents）是为了快速找到书号，真正的书（object_instances）还是在书架上，卡片不能代替书本身。

---

### 问题5.4：子图扩展的时候怎么知道哪个是主键ID？是写死的吗？

这个问题问得太好了！这是关键中的关键，你问到点上了。

**答案是：根本不用从文本里解析ID！SearchDocument本身就是结构化的，带着entity_type和entity_id字段！**

我给你看SearchDocument的定义（domain/models.py第189-198行）：
```python
class SearchDocument(DomainModel):
    id: str                           # 检索卡片自己的ID，比如"instance:material:MAT-001"
    network_id: str
    level: SearchLevel                # schema/instance/action
    entity_type: str                  # 对象类型/文档类型，比如"material"
    entity_id: str                    # 实体ID（就是主键值！），比如"MAT-001"
    title: str
    content: str                      # 拼好的纯文本，给BM25和向量看的
    citation: str
    vector: list[float]
```

看到没有！`entity_type`和`entity_id`是SearchDocument的**结构化字段**，和content文本是并列的，不是从content里解析出来的！

在创建SearchDocument的时候（retrieval_service.py第186-207行），这些字段就明确传进去了：
- 实例文档：`entity_type=item.object_type_id`，`entity_id=item.instance_id`
- Schema文档：`entity_type="object_type"/"relation_type"`，`entity_id=item.id`
- 动作文档：`entity_type="action_type"`，`entity_id=item.id`

所以当检索返回一个SearchHit的时候，代码根本不用去解析那个用空格拼的content文本，直接拿`hit.document.entity_type`和`hit.document.entity_id`就知道这是什么类型的哪个实体，直接当BFS的种子。

content文本只是给BM25和向量检索用来算相似度用的，算完分排序完之后，真正要定位实体、拿数据、做扩展，全靠结构化的entity_type和entity_id字段，和content文本一点关系都没有。

我再给你举个例子，比如MAT-001这个物料的SearchDocument：
- id: "instance:material:MAT-001"
- level: "instance"
- entity_type: "material"
- entity_id: "MAT-001" ← 这就是主键值，直接存在这里，不用解析
- title: "温度传感器"
- content: "material 温度传感器 sku MAT-001 current_stock 8 ..." ← 这只是给检索算分用的
- citation: "resource://materials_csv#row=2"
- vector: [0.12, -0.03, ...]

你看，ID信息是结构化存储的，根本不用从content里猜，也没有写死什么"哪个元素是ID"，建索引的时候就放好了，100%准确。

这是一个非常重要的设计：**检索用非结构化文本（BM25/向量擅长），定位和操作用结构化字段（确定性代码擅长）**，两者各取所长，这比纯向量RAG只存文本块要靠谱得多。

**面试可以这么讲**："我们的检索文档采用'结构化元数据+非结构化检索文本'的双轨设计：content字段专门给BM25和向量检索做相似度计算，entity_type、entity_id、citation这些结构化字段用来做实体定位、关联扩展和来源溯源，既利用了非结构化检索的语义匹配能力，又保证了后续数据操作的确定性和准确性。"

---

## 总结

这5个问题覆盖了MCP工具调用流程、AI Schema增强的边界、大模型禁用红线、检索+图扩展完整流程、数据库表设计核心思想，都是非常核心的架构问题。还有什么不清楚的随时问！
