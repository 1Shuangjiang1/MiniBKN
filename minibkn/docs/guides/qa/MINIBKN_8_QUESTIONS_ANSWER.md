> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 8个核心问题详细解答（基于真实源码）

> 所有回答均基于 `minibkn/src/minibkn/` 下的真实代码，不猜测。文档版本：2026-08-13

---

## 问题1：MCP协议是什么意思？怎么接入Cursor或者Claude？

### MCP是什么（大白话解释）

MCP全称是 **Model Context Protocol（模型上下文协议）**，你可以把它理解成"AI工具的USB接口标准"。

以前每个AI工具（Cursor、Claude Desktop、Cline等）要接入外部能力，都要单独写适配，就像以前手机充电口有安卓、苹果、Type-C好几种，混乱得很。MCP就是Anthropic牵头搞的一个统一标准，就像现在大家都用Type-C一样，**只要一个服务实现了MCP协议，所有支持MCP的AI客户端都能直接用它**。

MiniBKN的MCP服务给AI暴露了3个"工具"：
1. `search_knowledge` - 搜索知识网络
2. `ask_knowledge` - 问答，返回三层上下文+引用来源
3. `request_action` - 申请执行业务动作，会经过风险门禁

### 源码实现在哪里

看 `minibkn/src/minibkn/mcp_server.py`：
- 用官方 `mcp.server.MCPServer` SDK实现
- 走的是 **stdio传输**（标准输入输出），不是HTTP
- MCP Server本身不直接操作数据库，而是作为"网关"通过HTTP调用MiniBKN的FastAPI接口（第25-65行 `HttpMiniBKNGateway`）

### 怎么接入Cursor/Claude Desktop

MCP服务是一个独立的命令行程序，启动命令在 `mcp_server.py` 第105-106行：
```python
def run() -> None:
    mcp.run(transport="stdio")
```

**接入步骤（以Claude Desktop为例）：**
1. 先启动MiniBKN的FastAPI服务（`uvicorn minibkn.main:app`，默认跑在8000端口）
2. 打开Claude Desktop的配置文件（一般在 `~/.claude/claude_desktop_config.json`）
3. 添加mcpServers配置：
```json
{
  "mcpServers": {
    "minibkn": {
      "command": "python",
      "args": ["-m", "minibkn.mcp_server"],
      "cwd": "<local-path>",
      "env": {
        "MINIBKN_API_BASE_URL": "http://127.0.0.1:8000",
        "MINIBKN_API_KEY": ""
      }
    }
  }
}
```
4. 重启Claude Desktop，就能在工具列表里看到MiniBKN的3个工具了

**Cursor的接入方式类似**，Cursor最新版也支持MCP，在设置里找MCP配置，加同样的command就行。

**面试可以这么讲**："MCP是AI工具的统一接入标准，类似AI界的Type-C。我们实现了MCP stdio Server，把检索、问答、受控动作三个能力暴露出去，任何支持MCP的AI Agent（Cursor/Claude/Cline）都可以零代码接入，直接调用我们的知识引擎能力，而且动作执行不会绕过我们的风险门禁和审计。"

---

## 问题2：目前项目需要哪些大模型？哪些需要API Key？

直接看 `minibkn/src/minibkn/config.py` 的配置项：

| 配置项 | 默认值 | 是否需要API Key | 用途 |
|--------|--------|----------------|------|
| `llm_provider` | `"extractive"` | 否（默认硬编码） | 问答用什么方式 |
| `llm_api_key` | `""` | 是（如果用LLM的话） | LLM的API Key |
| `llm_base_url` | `""` | - | LLM接口地址（OpenAI兼容格式） |
| `llm_model` | `""` | - | 模型名称 |
| `embedding_provider` | `"token_hashing"` | 否（默认离线） | 向量嵌入用什么方式 |
| `embedding_model` | `"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"` | 否（本地模型） | Sentence Transformers模型名 |

### 结论：**默认零依赖，不需要任何API Key就能跑通全流程**

1. **问答模块默认是硬编码的抽取式回答**：就是你看到的供应链库存逻辑，完全不用大模型，看 `retrieval_service.py` 第209-242行 `_extractive_answer()` 方法
2. **向量默认是Token Hashing**：就是zlib.crc32哈希做的128维"伪向量"，纯本地计算，不需要模型也不需要API Key，看 `hybrid.py` 第18-32行 `TokenHashingEmbedder`
3. **只有一个地方可选使用LLM**：就是自动生成Schema时的"AI补描述"功能，看 `schema_generation_service.py` 第46-61行，`use_ai=True` 时才会调用，而且这是可选的，关了也完全能用

### 如果要开启LLM能力需要什么？

- 任何OpenAI兼容接口的API Key都行（豆包、通义千问、DeepSeek、OpenAI都可以）
- 配置 `MINIBKN_LLM_PROVIDER=openai_compatible`（或者你实现的其他adapter）
- 配 `MINIBKN_LLM_BASE_URL`、`MINIBKN_LLM_API_KEY`、`MINIBKN_LLM_MODEL` 三个环境变量就行
- 如果要用真实语义向量，配 `MINIBKN_EMBEDDING_PROVIDER=sentence_transformers`，第一次运行会自动下载开源模型到本地，也不需要API Key

**面试可以这么讲**："我们做了可插拔设计，默认全链路确定性代码跑通，不需要依赖任何外部大模型服务，这在企业内网部署很重要。如果需要语义增强，可以一键切换到Sentence Transformers本地向量或者OpenAI兼容的云端模型，接口边界已经留好了。"

---

## 问题3：三个问题能否解决？方案是什么？

三个问题都是真实存在的，完全可以解决，而且都是P0优先级。我给你每个问题讲清楚现状、解决方案、代码改动点：

---

### ❌ 问题A：问答硬编码了供应链逻辑，换场景跑不通

**现状（看代码）**：`retrieval_service.py` 第209-242行的 `_extractive_answer()` 是硬编码的：
- 写死了判断 `current_stock < safety_stock`
- 写死了找 `supplier_id` 关联供应商
- 写死了问题里要包含"库存"、"stock"、"安全"这些关键词
- 完全不能适配其他场景

**解决方案（分两步走）**：

| 阶段 | 方案 | 工作量 | 效果 |
|------|------|--------|------|
| P0（短期，1-2天） | 通用抽取式回答模板化 | 小 | 不需要LLM，基于三层上下文做通用回答，支持80%常见查询 |
| P1（中期） | 接入LLM做生成式回答 + 事实校验 | 中 | 用LLM基于上下文生成自然回答，同时做引用校验和幻觉检测 |

**P0具体怎么做（纯规则，不用LLM）**：
1. 第一层返回的Schema里已经有对象类型、字段名、字段描述了
2. 第二层返回的实例里已经有具体属性值了
3. 第三层返回的子图已经把关联对象带过来了
4. 不要硬编码判断字段名，而是：
   - 从问题里提取关键词匹配字段名/显示名/描述
   - 对匹配到的数值型字段支持比较查询（大于/小于/等于）
   - 自动把子图里的关联对象信息拼进去
   - 找不到足够证据就拒答，不瞎编

**P1具体怎么做（LLM版）**：
把三层上下文（Schema定义、实例数据、关联子图、动作列表）全部塞给LLM，系统提示词严格要求：
- 只能用提供的上下文回答，不能用外部知识
- 每个事实必须附上引用来源
- 证据不足直接说"我没有足够信息回答这个问题"
- 可以用Ragas做Faithfulness校验

---

### ❌ 问题B：200道题是凑出来的，不是通用业务题，也没测Faithfulness

**现状**：现在的评测集确实是"5实体×8问法×5模板"凑的，看评测代码 `evaluation/benchmark.py`。

**解决方案**：

1. **第一步：做CRM场景真实测试集**
   - 设计客户、订单、产品、客服工单4-5个对象
   - 准备真实模拟数据（至少100+实例，几十条关系）
   - 人工设计50-100道真实业务问题，覆盖：
     - 单对象查询（"张三的订单金额是多少"）
     - 多跳关联查询（"买了产品A的客户都有谁"）
     - 聚合查询（"本月订单总金额是多少"）
     - 动作相关查询（"哪些订单需要审批"）
   - 每道题写标准答案和应该命中的引用

2. **第二步：跑Ragas完整评测指标**
   - Context Precision：检索回来的上下文有多少是相关的
   - Context Recall：应该检索到的上下文有多少真的检索回来了
   - Faithfulness：回答里有多少是能被上下文支持的（幻觉率）
   - Answer Relevance：回答和问题的相关度
   - 对比基线：纯向量检索、纯BM25、我们的三层混合检索，三个结果对比

3. **简历数字替换原则**：所有数字必须是真实跑出来的，跑出来多少写多少，不能造假。如果提升20%就写20%，提升10%就写10%，真实就好。

---

### ❌ 问题C：默认向量是简单Token哈希，不是真的Sentence Transformers语义向量

**现状（看代码）**：
- 默认用的是 `TokenHashingEmbedder`（`hybrid.py` 18-32行），就是把每个token做crc32哈希，随机映射到128维空间，只能算"词面重合度近似"，完全没有语义理解能力
- 但代码已经留好了扩展接口：看 `semantic.py` 已经实现了 `SentenceTransformerEmbedder`，只是默认没开启

**解决方案（非常简单，已经有现成代码）**：

1. 安装依赖：`uv sync --extra semantic` 或者 `pip install sentence-transformers`
2. 修改配置，把环境变量 `MINIBKN_EMBEDDING_PROVIDER` 设为 `sentence_transformers`
3. 默认模型是 `paraphrase-multilingual-MiniLM-L12-v2`，支持中文，体积小（~100MB），速度快，效果好
4. 重新build索引就生效了

**为什么默认用哈希？** 因为开箱即用，不需要用户下载几百MB模型，第一体验好。但做评测和简历项目一定要切到真实Sentence Transformers向量。

**如果想更好**：还可以接OpenAI的text-embedding-3或者BGE中文向量模型，效果会更好，但本地部署优先用开源的Sentence Transformers。

**面试可以这么讲**："我们做了嵌入层抽象，默认用无依赖的Token哈希基线保证开箱即用，同时预留了Sentence Transformers和云端LLM适配器，一行配置切换，不需要改业务代码。"

---

## 问题4：主键识别方式需要优化，太简单不严谨

### 现状（看真实代码，确实简单）

看 `adapters/datasource/local.py` 第128-135行 `_looks_like_primary_key()`：

```python
def _looks_like_primary_key(name: str, rows: list[dict[str, str]]) -> bool:
    values = [row.get(name) for row in rows]
    return (
        bool(rows)
        and (name.lower() in {"id", "sku"} or name.lower().endswith("_id"))
        and None not in values
        and len(set(values)) == len(values)
    )
```

**当前逻辑就是4条规则（只对CSV有效，SQLite是直接读数据库建表信息的，这个是准的）：**
1. 字段名是 `id` 或 `sku`，或者以 `_id` 结尾
2. 没有空值
3. 值全不重复（唯一）

**问题在哪里？**
1. 太依赖命名规范了，如果主键叫 `order_no`、`material_code`、`customer_id`（这个其实能命中）、`empno` 就识别不出来
2. 有些非主键字段也可能满足：比如 `email`、`phone` 也唯一非空，但不是主键
3. 不支持联合主键（多个字段一起当主键）
4. 没有利用数据特征，比如自增ID、有格式规律的编码（如MAT-001）

### 优化方案（分优先级）

| 优先级 | 优化点 | 具体逻辑 |
|--------|--------|----------|
| P0 | 扩展命名规则 | 除了id/sku/_id，再加：`*_no`、`*_code`、`*_num`、`*_id`、`uuid`、`guid`，中文的话"编号"、"编码"、"号"也加上 |
| P0 | 排除明显不是主键的字段 | 字段名包含 `email`、`phone`、`mobile`、`name`、`date`、`time`、`amount`、`price`、`count` 的，就算唯一也不当主键（除非名字里有id/code） |
| P1 | 值特征判断 | 自增ID：值都是整数，且连续/近似连续（如1,2,3,4...）；有格式规律：用正则匹配，比如 `^[A-Z]+-\d+$` 这种MAT-001格式的编码 |
| P1 | 优先级排序 | 如果多个字段都满足，选命名最像的（id > xxx_id > xxx_code > xxx_no > 其他唯一字段） |
| P2 | 联合主键支持 | 如果单个字段没有主键，检查两个字段组合起来是否唯一，且命名像（比如 `order_id` + `product_id` 组成订单明细表主键） |
| P2 | 用户交互确认 | 自动识别完后展示给用户，让用户可以手动调整，选错了可以改 |

**SQLite的主键识别是准的**，因为直接读 `PRAGMA table_info()` 第5列（`primary_key` 标记），那个是数据库建表时声明的，不会错。问题只在CSV导入时的自动识别。

**面试可以这么讲**："CSV没有Schema，所以我们需要启发式识别主键。当前用的是命名+唯一性校验，我们计划扩展命名规则、加入值特征判断、排除非主键字段、支持联合主键，并增加用户确认环节，保证准确率。"

---

## 问题5：风险规则金额计算是AI来还是规则来？怎么从BKN变成可执行代码？

### 答案：**100%是规则计算，完全不用AI**

直接看源码 `action_service.py` 第206-231行 `_risk_decision()`：

```python
@staticmethod
def _risk_decision(risk: RiskType, instance: ObjectInstance) -> RiskDecision:
    threshold = risk.condition.get("value_threshold")
    if threshold is None:
        return RiskDecision(...)
    shortage = max(
        0.0,
        float(instance.properties.get("safety_stock", 0))
        - float(instance.properties.get("current_stock", 0)),
    )
    estimated_value = shortage * float(instance.properties.get("unit_cost", 0))
    matched = estimated_value >= float(threshold)
    return RiskDecision(...)
```

### 整个流程是这样的：

1. **BKN文件里只声明规则参数，不写代码**

   看供应链Demo的 `high_value_replenishment.bkn`，frontmatter里只写了：
   ```yaml
   policy: confirm
   applies_to_actions: [create_replenishment_alert]
   value_threshold: 500
   ```
   意思是：补货动作，预计金额≥500就要人工确认。

2. **BKN解析器把文件解析成内存对象**

   `bkn_lang/parser.py` 第256-273行 `_parse_risk_type()`，把YAML里的字段读出来，存在 `RiskType` 这个domain对象里，包括：
   - 适用哪些动作
   - 风控策略（allow/confirm/deny）
   - 阈值参数（这里是value_threshold: 500）

3. **硬编码的规则解释器执行计算**

   **重点来了**：当前版本**不是通用规则引擎**，是硬编码的补货金额计算逻辑！

   代码里写死了：
   - 缺料量 = 安全库存 - 当前库存
   - 预计补货价值 = 缺料量 × 单价
   - 如果预计价值 ≥ 阈值，命中风控规则

   BKN文件只是传了一个阈值参数500进来，计算公式是代码里提前写死的。

### 为什么这么做？

这是MVP阶段的合理简化：
- 企业级BKN Foundry是有完整表达式引擎的，可以在BKN文件里写自定义公式，甚至调用沙箱代码
- MiniBKN作为简化版，当前只内置了"补货金额阈值"这一种风控规则，足够演示
- 但架构是留了扩展点的：以后要加新的风控规则，只要在 `_risk_decision()` 里加新的condition类型判断就行

### 如果要做成通用规则引擎（后续优化）

可以这样改：
1. BKN里支持写简单表达式，比如 `${shortage} * ${unit_cost} >= ${threshold}`
2. 用一个安全的表达式解析库（比如Python的AST解析，只允许算术运算和属性访问，不允许函数调用，防止注入）
3. 执行时把实例属性注入到上下文里，计算表达式结果
4. 这样新增风控规则就不用改代码了，只改BKN文件就行

**面试可以这么讲**："风险判定是确定性规则执行，完全不经过AI，保证结果100%可预测、可审计、可复现，这是企业业务系统的核心要求。MVP阶段内置了金额阈值风控，BKN文件只传参数，架构上我们预留了扩展点，可以演进为安全的表达式引擎支持自定义规则。"

---

## 问题6：外键就是表里非主键的xxx_id字段关联另一个表主键，是这样吗？

**基本正确，但有几个细节要纠正，看真实代码 `schema_generation_service.py` 第102-135行 `_relations()`：**

### 自动发现外键的真实逻辑是4条同时满足：

1. **源对象（从表）有个字段名以 `_id` 结尾**（第107行：`if not prop.name.endswith("_id"): continue`）
2. **这个字段不是源对象自己的主键**（代码里没明写，但第113行找target的时候排除了source自己）
3. **存在另一个目标对象（主表），这个 `xxx_id` 字段正好是目标对象的主键**（第110-116行：`prop.name in item.primary_keys`）
4. **满足条件就创建一条关系，映射规则是源表.xxx_id = 目标表.xxx_id**

### 举个供应链Demo的真实例子：

- material表（物料）有字段 `supplier_id`
- material表的主键是 `sku`，所以 `supplier_id` 不是自己的主键
- supplier表（供应商）的主键正好是 `supplier_id`
- 所以自动发现关系：material → supplier，通过 `supplier_id` 字段关联

### 你的理解基本对，但有2个小纠正：

1. **不是"任意一行"，是"这个字段在每一行的值"去关联目标表主键的值**：
   - 不是说这个字段某一行的值等于某个主键就行，而是**对每个实例**，用这个字段的值去目标表找主键等于这个值的实例，两个实例之间就建立一条关系边
   - 比如物料MAT-001的supplier_id是SUP-001，那MAT-001和SUP-001这两个具体实例之间就有一条"supplied_by"关系边

2. **字段名不匹配时自动发现不了，需要手动写BKN**：
   - 比如从表字段叫 `vendor_code`，主表主键叫 `supplier_id`，虽然业务上是同一个东西，但名字不一样，自动规则发现不了
   - 这时候就需要手动写relation_type的BKN文件，在Mapping Rules表里手动指定：source property是vendor_code，target property是supplier_id
   - 看 `bkn_lang/parser.py` 第206-212行，关系是支持自定义字段映射的，不要求字段名必须一样

3. **SQLite数据源的外键是直接读数据库的吗？**
   - 不是！SQLite虽然支持外键约束，但当前代码读SQLite的时候只读了 `PRAGMA table_info()`，没读 `PRAGMA foreign_key_list()`
   - 所以SQLite导入时的外键关系发现，和CSV一样，走的也是这套xxx_id字段名匹配规则
   - 后续可以优化：SQLite直接读数据库声明的外键，准确率更高

**面试可以这么讲**："我们通过字段名约定做外键自动发现：源表的xxx_id字段匹配目标表同名主键时自动建立关系，实例物化时按字段值相等建立具体关联边。对于字段名不匹配的情况，支持在BKN文件里手动声明映射规则，保证灵活度。"

---

## 问题7：问"哪些物料库存不够"时，三层检索具体会返回什么？过滤条件到底是什么？

**这个问题问得非常好！我现在完全按照真实代码一行一行给你拆解，没有任何模糊，所有逻辑都在 `retrieval_service.py` 里。**

首先你要知道一个**非常重要的真相**：

### 第一层检索（全局混合搜索）：**没有任何过滤条件！所有文档一起搜！**

看代码第64行：
```python
hits = await self.search(network_id, question, 20)
```
`search()` 方法（第46-61行）会把 `search_documents` 表里**所有文档**（Schema、实例、动作三种类型全算上），一起做BM25+向量RRF排序，取前20条。

**没有任何类型过滤，没有任何对象类型过滤，三种文档平等竞争排名。**

为什么？因为用户问的问题里可能提到任何东西，系统不做预判，让检索自己决定什么相关。

---

### 第二层：三层拆分，这里有"过滤"，但不是你想的那种过滤

看代码第65-67行：
```python
schema = [hit for hit in hits if hit.document.level == SearchLevel.SCHEMA][:5]
instances = [hit for hit in hits if hit.document.level == SearchLevel.INSTANCE][:8]
actions = [hit for hit in hits if hit.document.level == SearchLevel.ACTION][:5]
```

**这里的"过滤"就是按level字段拆分，然后截断数量**：
- 从20条结果里，挑出level是SCHEMA的，最多5条
- 挑出level是INSTANCE的，最多8条
- 挑出level是ACTION的，最多5条

**就这么简单！没有"上一层结果决定下一层过滤条件"，之前可能讲错了！**

我给你用人话再讲一遍：
1. 所有文档放一起搜，取前20
2. 从这20条里，Schema类的挑前5个，实例类的挑前8个，动作类的挑前5个
3. 没有用第一层Schema的结果去过滤第二层实例，完全没有这个逻辑！
4. 三层是并行从同一个Top20结果里按level分组截断的

---

### 第三层：子图扩展，这里才有真正的"关联"逻辑

看代码第68行 `_context_subgraph()`，方法在第98-117行：

```python
async def _context_subgraph(self, network_id: str, hits: list[SearchHit]) -> Subgraph:
    all_objects = await self._graph.list_objects(network_id)
    all_relations = await self._graph.list_relations(network_id)
    selected = {(hit.document.entity_type, hit.document.entity_id) for hit in hits}
    for edge in all_relations:
        source = (edge.source_object_type_id, edge.source_instance_id)
        target = (edge.target_object_type_id, edge.target_instance_id)
        if source in selected or target in selected:
            selected.update((source, target))
    # 返回selected里的所有节点和边
```

**逻辑是：**
1. 先把刚才命中的8个实例（不管是物料还是供应商），放到 `selected` 集合里作为"种子"
2. 遍历数据库里**所有**关系边
3. 只要一条边的**起点或者终点**在selected集合里，就把边的另一个端点也加进来
4. 这就是**1层BFS扩展**（只扩展1跳，不递归扩展多跳）
5. 最后返回selected集合里的所有节点（包括种子+扩展出来的1跳关联节点）和它们之间的边

---

### 用"哪些物料库存不够"这个问题给你走一遍完整流程

假设供应链Demo数据：
- 3个物料（MAT-001温度传感器、MAT-002电容、MAT-003继电器模块）
- 2个供应商（SUP-001 Precision、SUP-002 Quality）
- 物料文档内容包含："material 温度传感器 MAT-001 current_stock 8 safety_stock 30 supplier_id SUP-001 ..."
- 供应商文档内容包含："supplier Precision Components SUP-001 contact ..."

**第一步：全局搜索Top20（实际只有9个文档）**

- 问题是"哪些物料库存不够"，关键词：物料、库存、不够
- BM25和向量都会优先命中**物料实例文档**，因为物料文档里有"物料"、"current_stock"、"safety_stock"这些词
- 供应商文档里没有"库存"相关的词，所以供应商实例一开始大概率排不上前8个INSTANCE
- Schema里的object_type:material会命中SCHEMA
- Action里的"创建补货预警"因为描述里有库存、补货，会命中ACTION

所以hits前20里：
- SCHEMA：object_type:material 排第一，可能还有relation_type:supplied_by，最多5条
- INSTANCE：三个物料实例都命中（MAT-001、MAT-002、MAT-003），因为它们的文档里都有库存相关字段
- ACTION：create_replenishment_alert 命中

**第二步：按level分组截断**
- schema = [material的Schema, supplied_by的Schema, ...] 最多5条
- instances = [MAT-001, MAT-002, MAT-003] 这三个物料实例，因为供应商文档不相关，一开始这里没有供应商
- actions = [create_replenishment_alert] 最多5条

**第三步：1跳BFS子图扩展**
- selected初始集合 = {(material, MAT-001), (material, MAT-002), (material, MAT-003)}
- 遍历所有关系边：MAT-001的supplier_id是SUP-001，有一条边 (material, MAT-001) → (supplier, SUP-001)
- 因为起点(MAT-001)在selected里，所以把终点(SUP-001)加进selected
- 同理MAT-003关联的SUP-001也加进来，MAT-002如果库存够，它关联的供应商也会被加进来（因为MAT-002在种子里）
- 最后selected集合里就是：3个物料 + 它们关联的供应商（SUP-001、SUP-002）

**第四步：硬编码回答**
- `_extractive_answer()` 里写死了找current_stock < safety_stock的物料
- MAT-001（库存8<30）和MAT-003（库存4<25）会被挑出来
- 然后通过supplier_id找到对应的SUP-001 Precision Components
- 拼接成回答："库存低于安全库存的物料有：温度传感器（MAT-001...供应商Precision）；继电器模块（MAT-003...供应商Precision）"

### 总结：你之前可能误解的点

| 之前的模糊理解 | 真实代码逻辑 |
|----------------|--------------|
| "第一层检索Schema，第二层用Schema的结果过滤实例" | ❌ 错！三层是从同一个Top20结果里按level分组，没有层层过滤 |
| "第二层检索加什么过滤条件" | ❌ 实例层没有额外过滤条件，就是全局搜出来的实例按分排，取前8 |
| "第三层过滤条件怎么决定" | ❌ 第三层不是过滤，是**子图扩展**：拿到命中的实例种子，通过关系表把1跳关联的对象拉进来，不管是什么对象类型 |
| "问物料会返回供应商吗" | ✅ 会！如果物料实例命中了，BFS扩展会自动把关联的供应商拉进来，不管供应商有没有在初始检索里命中 |

**这才是真实的代码逻辑，之前如果讲错了以这个为准。**

**面试可以这么讲**："我们采用全局混合检索加分层截断加子图扩展的策略：首先所有类型文档平等检索取TopN，然后按Schema/实例/动作三层分组截断保证上下文结构均衡，最后基于命中的实例做1跳BFS扩展拉取关联对象，既保证了检索召回，又通过分层保证了大模型拿到的上下文结构合理，不会全是同一种类型。"

---

## 问题8：search_documents和schema相关表是干什么的？为什么除了对象实例和关系实例还要有这些表？

先给你看完整的数据库表清单，在 `tables.py` 里一共是8张表：

| 表名 | 作用 |
|------|------|
| `knowledge_networks` | 知识网络元信息，一个业务领域一个 |
| `bkn_documents` | 存BKN原始文件的解析结果缓存 |
| `data_sources` | 数据源配置（CSV路径/SQLite路径） |
| `object_instances` | 对象实例表，具体的物料/供应商/客户 |
| `relation_instances` | 关系实例表，对象之间的关联边 |
| **`search_documents`** | **检索专用表，给BM25和向量检索用的"卡片"** |
| `action_executions` | 动作执行记录 |
| `trace_events` | 审计日志 |

注意：**没有单独的schema_definitions表！** Schema定义存在哪里呢？存在两个地方：
1. BKN文件本身（磁盘上的.yaml+.md文件）
2. `bkn_documents` 表的JSON payload里，作为缓存
3. 内存里构建KnowledgeNetwork对象时加载进来

你说的`schema_definitions`可能是之前讲的时候口头说的，代码里实际表名是`bkn_documents`。

---

### 为什么要有 `search_documents` 表？为什么不直接搜object_instances？

这是个非常好的架构问题。我给你讲为什么：

#### 原因1：**检索需要的是"纯文本卡片"，不是结构化对象**

BM25和向量检索都是处理纯文本的，它们不懂什么对象类型、字段、关系。

看 `retrieval_service.py` 第154-168行，每个对象实例会拼成一段这样的纯文本：
```
material 温度传感器 sku MAT-001 current_stock 8 safety_stock 30 unit_cost 42.5 supplier_id SUP-001 ...
```
Schema文档拼成：
```
物料 物料对象 sku 物料编码 current_stock 当前库存 safety_stock 安全库存 unit_cost 单价 ...
```
Action文档拼成：
```
创建补货预警 创建补货预警 库存低于安全库存时创建补货预警 material ...
```

这些专门为检索拼接的"文本卡片"，就是SearchDocument，存在search_documents表里，content字段是纯文本，vector字段是预计算好的向量。

**如果不这样做，每次检索都要：**
1. 把所有对象实例查出来
2. 动态拼接文本
3. 现场计算向量
4. 现场算BM25

性能会差很多，而且每次都重复计算。预计算好存表，检索的时候直接查出来排序就行。

#### 原因2：**三种不同来源的内容要统一格式检索**

你想想，检索需要搜三类完全不同的东西：
1. **Schema定义**：对象有哪些字段？关系是什么？动作是什么？这些存在BKN文件/bkn_documents表里，不是实例
2. **实例数据**：具体的物料、供应商，这些在object_instances表里
3. **动作定义**：能执行什么操作？这些也在BKN文件里

这三类东西来源不同、结构不同，但检索的时候需要**放在同一个池子里平等排序**。SearchDocument表就是把这三类东西统一格式，都转成 `{id, level, content, vector}` 的标准结构，这样检索逻辑就不用关心内容来源了，统一处理。

这叫**检索侧的读模型优化**，类似CQRS模式：写的时候存结构化数据（对象、关系分开存），读的时候专门做一张适合检索的表。

#### 原因3：**向量要预计算，不能每次搜都算**

向量Embedding是很重的操作，尤其是用Sentence Transformers模型的时候，每个文本编码要几十毫秒。如果每次用户提问都给所有文档编码一次，几百个文档就几秒出去了。

所以在build_index阶段，一次性把所有文档的向量都算好，存在search_documents的vector字段里（JSON数组），检索的时候直接拿出来算余弦相似度就行，非常快。

#### 原因4：**为什么不直接在object_instances表加个content和vector字段？**

因为SearchDocument不止有对象实例：
- Schema文档（object_type、relation_type）在object_instances表里根本没有对应记录
- Action文档在action_executions里也没有
- 以后接入文档类型的实体，也是SearchDocument的一种

所以单独一张表，level字段区分类型，扩展性最好。

---

### bkn_documents表是干什么的？

`bkn_documents` 表存的是**所有BKN文件解析后的原始内容缓存**：
- 每个.bkn文件解析完，JSON存在payload字段
- network_id、document_type、document_id做唯一索引
- 作用：不用每次启动都重新解析磁盘上所有BKN文件，直接从数据库读缓存

Schema定义（ObjectType、RelationType、ActionType、RiskType）就是从这个表加载的，不是存在单独的schema_definitions表里。

---

### 我给你打个比方，你就彻底懂了：

想象你开了一家图书馆：
- `object_instances` 和 `relation_instances` 是**书库**，书按分类（对象类型）整齐放在书架上，书和书之间的引用关系（关系）单独记在索引柜里，这是给"精确找书"用的，比如你要找MAT-001这本书，直接按编号去书架拿
- `search_documents` 是**前台的检索卡片盒**，每个文档（不管是Schema规则、具体书、还是能做的操作）都做了一张标准卡片，上面写了关键词和摘要，提前按检索方式排好序，还做了语义编码。用户来问问题，图书管理员先翻卡片盒快速找到相关卡片，再根据卡片去书库拿完整的书和相关的书
- `bkn_documents` 是**编目记录**，每类书的分类规则、借阅规则存在这里

为什么不直接让用户去书库找？因为书库是按分类放的，用户问"哪些书讲了库存不足"，你总不能把所有书都翻一遍吧？卡片盒就是专门为了"快速搜索"优化的。

这就是为什么需要额外的search_documents表，这不是冗余，是典型的**为检索优化的读模型**。

**面试可以这么讲**："我们采用了类似CQRS的思想，结构化存储和检索存储分离：对象和关系用结构化表保证数据一致性和关联查询效率，另外构建一张search_documents表作为检索读模型，将Schema定义、实例数据、动作定义统一预拼接成文本卡片并预计算向量，大幅提升检索性能和灵活性。"

---

## 总结

所有答案100%基于当前代码，没有猜测。如果有哪里和之前讲的不一样，以代码和这份文档为准。接下来你有什么问题可以继续问，或者我们可以开始动手改这几个P0问题。
