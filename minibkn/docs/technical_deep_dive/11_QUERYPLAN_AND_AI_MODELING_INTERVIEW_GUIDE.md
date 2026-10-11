> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 补充问题 10：QueryPlan 和 AI 辅助 BKN 建模怎样向面试官介绍

## 1. 先用一句话说明两者关系

> AI 辅助 BKN 建模解决“公司数据的业务语义和规则怎样进入系统”；QueryPlan 解决“用户的一句自然语言怎样变成可校验、可执行的结构化查询”。前者建立可执行业务模型，后者在这个模型上安全查询。

它们不是两个独立的 LLM Demo，而是同一个闭环的建模阶段和运行阶段。

## 2. QueryPlan 应该怎样讲

### 2.1 先讲问题，而不是先讲 JSON

传统 RAG 把原问题直接做向量检索。对“客户有哪些订单”还勉强可用，但对以下问题较弱：

- “统计华东区已付款订单总额”；
- “从客户跳到订单，再找逾期发票”；
- “按部门分组计算平均报销金额”；
- “为 MAT-001 创建补货预警”。

这些问题包含精确过滤、多跳关系、聚合或动作意图。只召回几个相似片段再让大模型计算，会漏数据、算错数字、消耗大量上下文，甚至误触发动作。

所以项目增加查询理解层，把自然语言转成受限 QueryPlan。

### 2.2 QueryPlan 是什么

QueryPlan 是经过 Pydantic 校验的 JSON 领域合同，不是 SQL，也不允许任意代码。它只能使用当前 BKN 中真实存在的对象、字段、关系、已启用动作，以及白名单 filter/aggregate/traversal 操作符、limit 和 evidence budget。

数据合同见 [domain/query.py](../../src/minibkn/domain/query.py)。

示例：“统计已批准报销单数量”：

```json
{
  "intent":"aggregate",
  "object_types":["expense"],
  "filters":[
    {"field":"status","operator":"eq","value":"approved"}
  ],
  "aggregates":[
    {"function":"count","field":"","alias":"count"}
  ],
  "limit":20
}
```

### 2.3 完整运行流程

```text
用户问题
 → DeepSeek/规则分析
 → 改写、关键词、同义词、子问题
 → 发现实质歧义则追问并停止
 → 生成 QueryPlan 候选
 → Pydantic + BKN Schema + 真实枚举值校验
 → search 走混合检索
 → lookup/traverse/aggregate 走确定性执行器
 → action 只返回候选，另走风险门禁
 → 返回结构化证据和引用
```

代码入口：[LLM Query planner](../../src/minibkn/adapters/llm/query_planner.py)、[规则降级器与执行器](../../src/minibkn/application/query_plan_service.py)、[API](../../src/minibkn/api/routes.py)。

### 2.4 安全设计是面试亮点

- LLM 只生成候选，不直接访问数据库；
- 未知对象、字段、关系和动作被拒绝；
- `in` 必须是列表，aggregate/traverse intent 必须匹配；
- 最大跳数、limit、证据预算和扫描量受限；
- 当前用户不可访问的资源在执行前被过滤；
- action plan 不能通过查询执行器运行；
- 单实例 action 仍必须进入权限、风险、审批和工具白名单。

系统把“自然语言的不确定性”停在计划层，把“数据查询和动作执行”留给确定性代码。

### 2.5 实测结果和正确口径

可以说：

> 我构建了采购、财务、人事 60 题未调优冻结集，DeepSeek 生成 QueryPlan 的 exact accuracy 为 93.33%，组件准确率为 97.52%。另外在 30 道 CRM 多跳和聚合题上，用冻结正确 QueryPlan 与传统混合 RAG Top-20 做同模型、同提示词对照，输入 Token 减少 66.78%，必要证据覆盖从 0.25 提升到 1.0。

必须补一句：30 题 Token 实验使用冻结正确计划，用于评估执行和上下文组织，不能替代 60 题的自动规划准确率。

### 2.6 QueryPlan 的 60 秒表述

> 传统 RAG 对精确过滤、多跳和聚合不稳定，所以我在检索前增加了 QueryPlan 层。DeepSeek 先把问题改写、拆子问题并识别歧义，再生成受限 JSON 计划；服务端用 BKN Schema 校验对象、字段、关系和动作，最终由 Python 执行过滤、遍历和聚合。LLM 不能输出 SQL，也不能通过 QueryPlan 执行动作。60 题跨采购、财务、人事的未调优 holdout 上，自动规划 exact accuracy 是 93.3%。30 道多跳和聚合对照中，相比传统 Top-20 RAG，QueryPlan 输入 Token 减少 66.8%。

## 3. AI 辅助 BKN 建模应该怎样讲

### 3.1 先说明困难

企业拿来的通常只是 CSV 或数据库表。字段名只能告诉系统一部分信息：哪一列是主键、两个表是什么关系、表代表客户还是事件、允许什么动作、什么情况要审批。

完全手写 BKN 成本高；完全让 LLM 自动生成又有幻觉和安全风险。因此项目采用“确定性发现 + AI 辅助语义 + 人工审核发布”。

### 3.2 三层职责

#### 第一层：确定性数据发现

程序先读取真实表结构和取值，分析字段类型、空值、唯一率、单字段/组合主键、外键候选、取值重叠和置信度，再生成初始 ObjectType、Property 和 RelationType。

这一层不依赖 LLM，是可复现的事实基础。

代码：[data_profiling.py](../../src/minibkn/application/data_profiling.py)、[schema_generation_service.py](../../src/minibkn/application/schema_generation_service.py)。

#### 第二层：AI 辅助增强

配置 LLM 后，把用户业务说明和已发现对象/关系交给 OpenAI-compatible Schema Enhancer。AI 可以补充对象与关系的业务描述，建议动作和风险规则。

代码：[openai_compatible.py](../../src/minibkn/adapters/llm/openai_compatible.py)。

#### 第三层：提案审核与发布

系统把结果拆成六类独立 `SchemaProposal`：object_type、property、primary_key、relation、action、risk。

每条包含 payload、confidence、evidence、rationale 和状态。审核人逐条接受、拒绝或修改；只要有一条 pending，发布接口返回 409。全部审核后才组装并发布 KnowledgeNetwork；相同 network ID 再发布会版本加一。

代码：[modeling_service.py](../../src/minibkn/application/modeling_service.py)、[domain/modeling.py](../../src/minibkn/domain/modeling.py)。

### 3.3 AI 动作建议为什么不会立即变成危险工具

任何 AI 建议的动作都会被强制设置为：

```text
enabled = false
requires_approval = true
tool = unconfigured/unconfigured
```

AI 不能自行注册工具。风险建议只允许 `confirm` 或 `deny`，条件必须通过安全 Policy DSL 校验。非法输出被丢弃；审核时试图把动作改成 enabled 也会被拒绝。

因此 AI 只能提出“可能需要审批动作”，不能凭空获得调用 ERP、付款或删除数据的能力。

### 3.4 没有 LLM 时怎样工作

没有配置 LLM，系统仍能根据数据剖析生成对象、字段、主键和关系提案。如果用户指令包含“动作、审批、创建、更新”等词，规则路径会生成低置信度、默认禁用、必须审批的动作与风险草案。

所以 AI 是增强能力，不是系统可运行的单点依赖。

### 3.5 一个真实验收链路

浏览器验收实际完成：

```text
登记 CRM 两张 CSV
 → 字段发现
 → 创建建模会话
 → 生成 14 条提案
 → 人工逐条接受
 → 发布 crm_reviewed v1
 → 增量构建
 → 生成 7 个对象、4 条关系、10 个索引文档
 → 在 UI 中问答并查看证据
```

自动化测试还验证未审完不能发布、危险动作修改被拒绝、会话持久化、发布后不可修改和发布后可增量构建。

测试：[test_modeling_workflow_api.py](../../tests/integration/test_modeling_workflow_api.py)。

### 3.6 AI 建模的 60 秒表述

> BKN 建模不能完全依赖 LLM，因为主键、字段映射和动作会直接影响后续查询与执行。我采用确定性发现、AI 辅助、人工发布三层设计：程序先根据真实表结构识别字段类型、组合主键和外键候选；LLM 再补充业务描述，并提出动作和风险草案；所有结果拆成可独立审核的提案，必须全部接受、拒绝或修改后才能发布。AI 建议的动作强制 disabled、requires approval，而且工具绑定为 unconfigured，所以模型不能直接创造执行权限。

## 4. 怎样把两部分连成一个项目故事

> 数据进入系统后，先经过字段剖析和 AI 辅助 BKN 建模，形成经过人工审核的对象、关系、动作和风险 Schema。运行时，QueryPlan 只允许引用这份已发布 Schema 中存在的字段和关系。因此 BKN 是业务知识和安全边界，QueryPlan 是在这个边界内生成的单次执行计划。即使 LLM 输出错误，Schema 校验、权限、风险 DSL 和工具白名单仍会阻止它变成数据库或业务系统的任意操作。

这能体现项目不是简单 RAG，而是“建模—查询—行动”的完整架构。

## 5. 常见追问和回答要点

### “为什么不用 Text-to-SQL？”

> Text-to-SQL 绑定数据库方言和物理表结构，直接生成可执行语句风险高。QueryPlan 面向业务对象，可以统一 CSV、SQLite 和图关系，先做 Schema/权限校验，再由确定性执行器运行。代价是当前表达能力有限，不支持任意 join、窗口函数和复杂计算。

### “为什么不直接让 Agent 调工具？”

> 工具调用有副作用。项目把动作意图和执行分离：LLM 只能生成 action_request，真正执行还要经过 Principal 权限、对象可见性、参数绑定、Risk DSL、审批、幂等和 ToolRegistry。

### “AI 建模会不会识别错主外键？”

> 会，所以主外键首先来自可解释的数据剖析，AI 只做增强，所有结果都进入提案审核。组合键和部分外键还用多行业脏数据做了回归测试。当前仍缺更完善的候选审核 UI，复杂业务关系需要领域人员确认。

### “为什么要人工审核，自动化程度不是降低了吗？”

> 自动化目标不是无人负责，而是减少初稿成本。对象、关系、动作和风险会影响真实数据与执行权限，因此人工审核是产品要求。系统保留证据、置信度、修改人和版本，提升可追溯性。

### “QueryPlan 93.3% 是否可以上线？”

> 不能只凭合成集分数直接上线。它说明架构在跨行业冻结集上可行；生产还需要真实业务 gold、灰度、低置信度追问、失败降级和人工观察。系统之所以有严格校验，就是假设规划模型仍会出错。

### “为什么混合检索没超过 BM25？”

> CRM 题包含大量订单号和客户号，精确词法检索占优势。BGE-M3 显著超过哈希向量，但 RRF 混合只追平 BM25。我保留了这个负结论，并把 QueryPlan 用于真正需要过滤、遍历和聚合的问题，而不是让向量检索解决一切。

## 6. 面试时不要这样说

- 不要说“AI 自动生成完整 BKN 并直接上线”；实际有人工提案审核。
- 不要说“QueryPlan 100% 正确”；自动规划是 93.33%，100% 是给定冻结正确计划后的执行结果。
- 不要说“Token 在所有问题上降低 66.8%”；只适用于 30 道 CRM 多跳/聚合对照。
- 不要说“混合检索显著超过 BM25”；实测是追平。
- 不要说“已经有完整字段级和行级权限”；当前主要是网络、资源、文档域和动作级 RBAC。
- 不要说“AI 可以直接修改 ERP”；当前只有显式注册的演示工具，真实业务 adapter 尚需开发。

## 7. 推荐的两分钟完整回答

> 项目最初是一个面向供应链样例的轻量 BKN 复现。我把它扩展为通用企业知识网络，核心分成建模和运行两阶段。建模阶段不是让 LLM 凭空猜 Schema，而是先对 CSV/SQLite 做字段类型、组合主键和外键候选分析，再让 LLM 补充业务语义、动作和风险建议。结果拆成对象、字段、主键、关系、动作和风险六类提案，必须全部人工审核才能发布；AI 建议的动作强制禁用并要求审批，也没有真实工具绑定。
>
> 运行阶段增加 QueryPlan。因为传统 RAG 对精确过滤、多跳和聚合不稳定，DeepSeek 先做改写、同义词、子问题和歧义判断，再生成受限 JSON 计划。计划只能引用已发布 BKN 中的对象、字段和关系，由 Pydantic 和服务端白名单校验，然后由 Python 确定性执行；动作意图不能通过查询端点运行，必须另走权限、风险和审批链路。
>
> 我还做了分层评估。60 题采购、财务、人事未调优 holdout 上，QueryPlan exact accuracy 是 93.3%；30 道 CRM 多跳和聚合题中，相比传统混合 RAG Top-20，输入 Token 减少 66.8%，必要证据覆盖从 0.25 提升到 1.0。我也保留了边界：混合检索在编号密集数据上只追平 BM25，真实生产仍需行级权限、企业 SSO 和真实业务数据验证。

## 8. 深入阅读

- [QueryPlan 数据合同](../../src/minibkn/domain/query.py)
- [QueryPlan 服务](../../src/minibkn/application/query_plan_service.py)
- [LLM Query planner](../../src/minibkn/adapters/llm/query_planner.py)
- [AI 建模服务](../../src/minibkn/application/modeling_service.py)
- [Schema 生成](../../src/minibkn/application/schema_generation_service.py)
- [QueryPlan 开发报告](../reports/MINIBKN_S4_QUERY_PLAN_DEVELOPMENT_REPORT.md)
- [AI 建模开发报告](../reports/MINIBKN_S7_AI_MODELING_WORKFLOW_DEVELOPMENT_REPORT.md)
- [查询智能与完整评测](../reports/MINIBKN_QUERY_INTELLIGENCE_AND_FULL_EVALUATION_REPORT.md)
