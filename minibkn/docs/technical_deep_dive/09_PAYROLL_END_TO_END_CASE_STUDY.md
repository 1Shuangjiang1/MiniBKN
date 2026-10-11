> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 09：财务工时与薪酬场景——从三张表到查询、动作、审批的完整案例

> 目的：只用一个现实案例，把 MiniBKN 从数据进入系统到最终问答、动作执行和审计的完整流程串起来。\
> 事实边界：文中标记为“当前已实现”的能力可以在 MiniBKN 0.6.0 中找到代码；标记为“案例扩展”的部分，是把现有通用框架用于真实财务场景时还需要开发的内容。

## 1. 公司背景与真实需求

假设“星河装备公司”有 300 名员工，生产部门按工种和工时计算部分薪酬。财务部门每月需要汇总工时、工价和奖金。

公司最开始只有三张表：

1. 人员工时表；
2. 不同工种的单位工时酬劳表；
3. 人员奖金表。

公司希望员工能问：

- “我 8 月一共工作了多少小时？”
- “我的奖金是多少？”
- “我这月按工时计算的收入大约是多少？”
- “为什么我的加班没有算进去？”

主管希望问：

- “我负责的员工里，谁本月工时超过 220 小时？”
- “焊工班组本月总工时和预计人工成本是多少？”
- “哪些工时记录还没有审批？”

行政或考勤人员还希望执行：

- “把 E001 在 8 月 3 日的焊工工时从 7 小时更正为 8 小时。”
- “将这条工时记录提交给主管审批。”

财务经理则需要：

- 审批高风险修改；
- 查看动作审计记录；
- 查询工资制度、加班制度等非结构化文档；
- 同时结合制度和业务数据回答问题。

## 2. 为什么三张表还不够

原始三张表能表达“工时、工价、奖金”，但不能可靠表达“登录用户是谁”“谁是谁的主管”“谁属于哪个部门”。如果只凭姓名或问题中的“我”让大模型猜身份，会造成严重越权。

因此案例增加第四张人员目录表：

### 2.1 `employees.csv`：人员目录

| employee_id | employee_name | department_id | manager_id | employment_status |
| --- | --- | --- | --- | --- |
| E001 | 张伟 | D-PROD-01 | M001 | active |
| E002 | 李娜 | D-PROD-01 | M001 | active |
| E003 | 王强 | D-PROD-02 | M002 | active |
| M001 | 陈主管 | D-PROD-01 | CFO01 | active |
| HR001 | 刘行政 | D-HR | HRM01 | active |

主键：`employee_id`。

### 2.2 `timesheets.csv`：人员工时

| employee_id | work_date | job_code | hours | overtime_hours | status | supervisor_id | version |
| --- | --- | --- | ---: | ---: | --- | --- | ---: |
| E001 | 2026-08-03 | WELDER | 7 | 0 | approved | M001 | 1 |
| E001 | 2026-08-04 | WELDER | 8 | 1 | approved | M001 | 1 |
| E002 | 2026-08-03 | ASSEMBLER | 8 | 0 | submitted | M001 | 1 |
| E003 | 2026-08-03 | WELDER | 10 | 2 | approved | M002 | 1 |

为了讲解方便，暂用 `(employee_id, work_date, job_code)` 作为组合主键。真实系统最好增加稳定的 `timesheet_id`，因为同一天同一工种也可能被拆成多个项目或班次。

### 2.3 `job_rates.csv`：工种工价

| job_code | effective_from | effective_to | hourly_rate | overtime_multiplier |
| --- | --- | --- | ---: | ---: |
| WELDER | 2026-01-01 | 2026-12-31 | 80 | 1.5 |
| ASSEMBLER | 2026-01-01 | 2026-12-31 | 60 | 1.5 |

组合主键：`(job_code, effective_from)`。只用 `job_code` 不够，因为费率可能随时间变化。

### 2.4 `bonuses.csv`：奖金

| bonus_id | employee_id | bonus_month | amount | reason | status |
| --- | --- | --- | ---: | --- | --- |
| B001 | E001 | 2026-08 | 1000 | 项目质量奖 | approved |
| B002 | E002 | 2026-08 | 500 | 出勤奖 | submitted |
| B003 | E003 | 2026-08 | 800 | 技能奖 | approved |

主键：`bonus_id`，`employee_id` 是人员目录外键。

### 2.5 非结构化文档

此外还有：

- 《2026 年工时与加班管理制度》；
- 《奖金审批办法》；
- 《考勤数据更正操作手册》；
- 劳动合同模板。

这些制度不适合塞进表格，进入 LightRAG 文档分支。

## 3. 完整系统流程图

```text
四张结构化表                         财务制度/操作手册
     │                                      │
     ▼                                      ▼
登记 CSV 数据源                      授权文档集合 payroll-policy
     │                                      │
     ▼                                      ▼
字段剖析、主键/外键候选              LightRAG 切块、实体/关系、向量索引
     │                                      │
     ▼                                      │
BKN Schema：对象、关系、动作、风险          │
     │                                      │
     ▼                                      │
物化对象实例和关系图                        │
     │                                      │
     ▼                                      │
Schema/实例/动作搜索文档 + Embedding         │
     └──────────────────┬───────────────────┘
                        ▼
              身份认证、权限与知识路由
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
       QueryPlan/结构化检索     LightRAG 文档检索
              └─────────┬─────────┘
                        ▼
                统一证据与带引用回答
                        │
               若识别为明确动作请求
                        ▼
          动作权限 → 参数绑定 → 风险规则
                        │
              deny / confirm / allow
                        │
                        ▼
             白名单考勤工具 + 审计轨迹
```

接下来按照这个顺序逐步讲解。

## 4. 第一步：登记和发现数据源

财务管理员在 UI 的“数据源”页面填写：

```text
数据源 ID：payroll_files
名称：财务工时与奖金数据
类型：CSV
路径：<local-path>
```

页面依次调用：

```http
POST /api/v1/sources
POST /api/v1/sources/payroll_files/discover
```

当前实现中，CSV adapter 会：

1. 找出目录下所有 `.csv`；
2. 用 UTF-8 BOM 兼容方式读取；
3. 识别 integer、number、boolean、date、datetime、JSON、string；
4. 统计空值、唯一性等字段特征；
5. 寻找主键和组合主键候选；
6. 比较跨表字段名、类型和取值重叠，生成外键候选及置信度。

代码位置：

- [CSV/SQLite adapter](../../src/minibkn/adapters/datasource/local.py)
- [字段剖析和键候选](../../src/minibkn/application/data_profiling.py)
- [数据源用例](../../src/minibkn/application/graph_service.py)

### 4.1 系统可能发现什么

它可能给出：

- `employees.employee_id`：唯一、非空、名称像 ID，推荐主键；
- `timesheets(employee_id, work_date, job_code)`：组合后唯一，推荐组合主键；
- `job_rates(job_code, effective_from)`：推荐组合主键；
- `bonuses.bonus_id`：推荐主键；
- `timesheets.employee_id -> employees.employee_id`：值高度重叠，推荐外键；
- `bonuses.employee_id -> employees.employee_id`：推荐外键；
- `timesheets.job_code -> job_rates.job_code`：可能是外键候选。

最后一个候选需要人审查。因为 `job_rates.job_code` 在不同生效日期可能重复，它不是完整主键。真实关系还需要工时日期落在费率生效区间内。当前通用关系物化器只支持字段等值映射，不能直接表达“日期位于起止区间”。

这说明自动发现的定位是“提出可解释候选”，不是“AI 自动决定所有业务关系”。

## 5. 第二步：生成并审核 BKN Schema

BKN 可以理解为“机器可执行的业务说明书”。它不保存所有原始数据，而是说明：每张表代表什么对象、字段如何映射、对象如何关联、允许哪些动作、风险条件是什么。

### 5.1 对象定义

案例可以生成四类对象：

```text
employee   → employees_csv
timesheet  → timesheets_csv
job_rate   → job_rates_csv
bonus      → bonuses_csv
```

以 timesheet 为例，概念性 BKN 定义类似：

```yaml
type: object_type
id: timesheet
name: 工时记录
primary_keys: [employee_id, work_date, job_code]
display_key: employee_id
data_source:
  source_id: timesheets_csv
properties:
  employee_id: employee_id
  work_date: work_date
  job_code: job_code
  hours: hours
  overtime_hours: overtime_hours
  status: status
  supervisor_id: supervisor_id
  version: version
```

这段是案例说明，不是仓库中已经存在的 payroll BKN 文件。

### 5.2 关系定义

可以定义：

```text
recorded_for：timesheet.employee_id → employee.employee_id
bonus_belongs_to：bonus.employee_id → employee.employee_id
managed_by：employee.manager_id → employee.employee_id
uses_job_rate：timesheet.job_code → job_rate.job_code
```

当前关系物化原理非常直接：对两个对象集合比较 BKN 声明的映射字段，全部相等就创建一条 `RelationInstance`。

代码：[KnowledgeGraphService._map_relations](../../src/minibkn/application/graph_service.py)。

### 5.3 AI 在建模阶段做什么

用户可以用自然语言说明：

> 工时记录属于员工，奖金属于员工；行政人员可以申请更正工时；已经月结的记录不能修改；修改他人工时需要主管确认。

AI 建模服务可生成对象、关系、动作或风险提案，但每条提案都处于 `pending`。管理员必须接受或拒绝所有提案，才能发布网络。

当前安全原则：AI 可帮助起草和补充说明，不能绕过人工审核直接发布可执行 Schema。

代码：[modeling_service.py](../../src/minibkn/application/modeling_service.py)、[schema_generation_service.py](../../src/minibkn/application/schema_generation_service.py)。

## 6. 第三步：把表格物化成对象和关系

发布 Schema 后运行：

```http
POST /api/v1/networks/payroll/builds
```

系统逐行读取数据，按 ObjectType 映射。

### 6.1 具体对象

第一条工时可能变成：

```json
{
  "network_id":"payroll",
  "object_type_id":"timesheet",
  "instance_id":"E001|2026-08-03|WELDER",
  "display_name":"E001",
  "resource_id":"timesheets_csv",
  "row_number":2,
  "properties":{
    "employee_id":"E001",
    "work_date":"2026-08-03",
    "job_code":"WELDER",
    "hours":7,
    "overtime_hours":0,
    "status":"approved",
    "supervisor_id":"M001",
    "version":1
  }
}
```

`instance_id` 来自主键组合；`resource_id` 与 `row_number` 用于权限和引用溯源。

### 6.2 具体关系

系统发现该行的 `employee_id=E001` 与员工 E001 相等，于是产生：

```text
timesheet/E001|2026-08-03|WELDER
    -[recorded_for]->
employee/E001
```

员工 E001 的 `manager_id=M001` 又可以连接到 employee/M001。

### 6.3 增量更新

如果行政人员第二天又放入新工时，增量构建会比较旧对象和新对象的内容哈希：

- 新行：inserted；
- 已有行内容变化：updated；
- 消失的行：deleted；
- 未变化的行：不重建向量。

若建图或索引失败，会恢复旧对象、关系、搜索文档和 manifest，避免发布半成品。

代码：[graph_service.py](../../src/minibkn/application/graph_service.py)、[build_service.py](../../src/minibkn/application/build_service.py)。

## 7. 第四步：构建三层结构化索引

系统不直接把整个数据库交给大模型，而是为三类内容创建搜索文档。

### 7.1 Schema 层

例如：

```text
工时记录 timesheet：employee_id、work_date、job_code、hours、status……
```

它帮助系统理解“工时”“考勤”等词对应哪个对象和字段。

### 7.2 实例层

例如：

```text
timesheet E001 employee_id E001 work_date 2026-08-03 job_code WELDER hours 7 ...
```

引用是：

```text
resource://timesheets_csv#row=2
```

### 7.3 动作层

例如未来的动作定义：

```text
更正工时 adjust_timesheet，绑定 timesheet 对象
```

### 7.4 Embedding 与混合检索

构建时为所有搜索文档生成向量。当前支持：

- 离线 token hashing 基线；
- 本地 sentence-transformers；
- 硅基流动兼容 Embedding，例如 BGE-M3；
- 缓存、批处理、远程失败降级和版本检查。

查询时：

- BM25 擅长 E001、日期、WELDER 等精确词；
- 向量检索理解“工钱”和“单位工时酬劳”等相近表达；
- RRF 按两个排名融合。

代码：[retrieval_service.py](../../src/minibkn/application/retrieval_service.py)、[hybrid.py](../../src/minibkn/adapters/search/hybrid.py)。

## 8. 第五步：接入制度文档的 LightRAG 索引

财务经理把《2026 年工时与加班管理制度》提交到 `payroll-policy` collection。

MiniBKN 先检查当前 Principal 是否允许该 collection，再调用独立 LightRAG endpoint：

```http
POST /documents/text
```

LightRAG 异步进行文本切块、实体关系抽取和向量索引，返回 `track_id`。MiniBKN 轮询：

```http
GET /documents/track_status/{track_id}
```

检索时 MiniBKN 调用 `/query/data`，只取 entities、relationships、chunks 等证据，不直接信任 LightRAG 自己生成的最终答案。文档片段统一变成：

```text
document://payroll-policy/2026年工时与加班管理制度.md#chunk=...
```

代码：[document_knowledge.py](../../src/minibkn/adapters/document_knowledge.py)。

敏感集合需要独立 workspace。例如公共考勤手册、财务经理制度和劳动合同不能先混在一个 LightRAG workspace，再依赖结果过滤。

## 9. 第六步：认证和权限

### 9.1 角色设计

案例可设计：

| 角色 | 网络 | 资源 | 文档集合 | 动作 |
| --- | --- | --- | --- | --- |
| employee | payroll/read | employees、timesheets、bonuses 的授权范围 | public-policy | 无 |
| supervisor | payroll/read | 本团队工时和必要人员字段 | public-policy、manager-policy | approve_timesheet |
| hr_clerk | payroll/read+execute | timesheets、employees | operations-manual | adjust_timesheet |
| finance | payroll/read | timesheets、job_rates、bonuses | payroll-policy | 无 |
| finance_manager | read/model/execute/approve/audit | 全部 | 全部 | 全部获准动作 |

### 9.2 当前 RBAC 已经能做的

当前 `Principal` 能限制：

- permission；
- network；
- 整个 resource；
- LightRAG collection；
- action。

HTTP 中间件先认证并做路由权限；检索、QueryPlan、子图和动作服务又按 resource 过滤数据。

代码：[access_control_service.py](../../src/minibkn/application/access_control_service.py)、[main.py](../../src/minibkn/main.py)。

### 9.3 这个案例必须补的行级权限

如果 300 名员工都在同一个 `timesheets.csv`，当前 RBAC 只能允许或禁止整张表，不能让 E001 只看 E001 的行。因此真实上线必须增加：

```text
principal.employee_id = E001
principal.department_id = D-PROD-01
principal.manager_scope = [E001, E002]
```

并在数据进入以下链路前强制过滤：

- 检索语料；
- QueryPlan 对象集合；
- 子图节点和关系；
- 动作目标实例；
- 回答证据。

员工规则可以是 `row.employee_id == principal.employee_id`；主管规则可以是 `row.employee_id in principal.manager_scope`。

这属于**案例扩展、当前未实现**。不能仅让 LLM在回答最后“不说其他人的工资”，因为敏感行已经进入模型上下文。

字段级权限也需补充，例如普通主管可能能看工时但不能看奖金原因和具体工价。

## 10. 第七步：员工查询的完整过程

员工 E001 已通过企业身份认证，系统知道 Principal 对应 employee_id=E001。

他问：

> 我 8 月总工时是多少，奖金有多少？

### 10.1 查询理解

LLM planner 获得 payroll Schema 和用户可见的真实状态值，输出：

- 改写：“查询当前员工 E001 在 2026 年 8 月的总工时和已批准奖金”；
- 关键词：E001、2026-08、工时、奖金；
- 子问题：总工时、奖金总额；
- intent：aggregate；
- 两个结构化查询子目标。

当前 QueryPlan 数据合同见 [domain/query.py](../../src/minibkn/domain/query.py)。当前系统能拆 `sub_questions`，但一个 QueryPlan 尚不支持把两个完全不同对象的独立聚合组合成复杂执行 DAG；实践中应生成两个计划再合并，这是案例扩展的总编排能力。

### 10.2 工时计划

概念上：

```json
{
  "intent":"aggregate",
  "object_types":["timesheet"],
  "filters":[
    {"field":"employee_id","operator":"eq","value":"E001"},
    {"field":"work_date","operator":"gte","value":"2026-08-01"},
    {"field":"work_date","operator":"lte","value":"2026-08-31"}
  ],
  "aggregates":[
    {"function":"sum","field":"hours","alias":"total_hours"}
  ],
  "limit":20
}
```

示例数据结果：`7 + 8 = 15 小时`。

### 10.3 奖金计划

筛选 `employee_id=E001`、`bonus_month=2026-08`、`status=approved`，对 amount 求和，结果 1000 元。

### 10.4 回答

系统不是让模型心算，而是由 QueryPlan executor 计算，再产生 computed evidence：

> 你在示例数据中的 2026 年 8 月总工时为 15 小时，已批准奖金为 1000 元。

同时返回工时和奖金数据行引用。

### 10.5 “按工时收入”为什么更难

普通工时收入需要：

```text
普通工时 × 生效工价
+ 加班工时 × 生效工价 × 加班系数
```

还要按 `work_date` 匹配费率生效区间。当前 QueryPlan 支持过滤、等值关系遍历和单字段聚合，但不支持跨对象区间 join 后逐行乘法再求和。

可行扩展有两种：

1. 在数据层建立权威 `payroll_detail` 视图，预先计算每行金额，MiniBKN 只查询；
2. 扩展受限 QueryPlan，增加经过白名单校验的 temporal join 和 computed expression。

对财务系统更推荐第一种：薪资计算应由权威薪酬引擎完成，MiniBKN 负责解释、检索和操作编排，而不是重新发明工资计算核心。

## 11. 第八步：歧义追问

主管问：

> 最近工时太多的人有哪些？

这里至少有两个实质歧义：

- “最近”是 7 天、30 天还是本月？
- “太多”是超过 200 小时、220 小时，还是超过制度上限？

`/ask-intelligent` 应返回 `needs_clarification`，例如：

```json
{
  "status":"needs_clarification",
  "ambiguities":[
    {"id":"time_range","question":"最近具体指多长时间？"},
    {"id":"hours_threshold","question":"工时超过多少算太多？"}
  ],
  "plan":null
}
```

主管回答“本月，超过 220 小时”后，才生成可执行计划。当前规则 planner 已覆盖部分通用时间和“大客户”歧义；任意业务阈值更依赖 LLM planner 或新增领域规则。

代码：[query_plan_service.py](../../src/minibkn/application/query_plan_service.py)、[query_planner.py](../../src/minibkn/adapters/llm/query_planner.py)。

## 12. 第九步：主管查询与组织范围

主管 M001 问：

> 我团队里还有哪些 8 月工时记录没有审批？

理想流程：

1. 认证得到 M001；
2. 行级授权服务取得管理范围 `[E001, E002]`；
3. 查询 timesheet；
4. 强制加入 `employee_id in [E001,E002]`；
5. 再加入 `status != approved` 和 8 月日期范围；
6. 返回 E002 的 submitted 记录；
7. 不返回 M002 团队的 E003，即使向量检索认为相关。

这里“管理范围”是安全约束，不应该由 LLM 自己生成或删除。正确实现是在 planner 计划之外，由策略层注入 mandatory filters，且执行器禁止客户端覆盖。

当前项目尚未实现这种 mandatory row filter，但已有 Principal、资源过滤、QueryPlan 校验和确定性执行器，可作为扩展落点。

## 13. 第十步：制度文档与混合问题

员工问：

> 制度说加班怎样计算？我的 8 月 4 日为什么有 1 小时加班？

这是典型 hybrid 问题：

- 子问题一“制度说加班怎样计算” → document → LightRAG；
- 子问题二“我的 8 月 4 日记录” → structured → QueryPlan；
- 最后按引用合并。

可能返回：

> 《2026 年工时与加班管理制度》第 X 段规定，经审批且超过标准班次的部分记为加班。你的 2026-08-04 工时记录为普通工时 8 小时、加班 1 小时，状态为 approved。

引用同时包括：

```text
document://payroll-policy/工时与加班管理制度.md#chunk=...
resource://timesheets_csv#row=3
```

当前 `/ask-routed` 已能执行 structured/document/hybrid 并统一证据，但 `auto` 只是关键词规则；当前不会自动给每个子问题安排不同分支。要完整实现上述效果，需要把 QueryAnalysis 与 KnowledgeRouter 合成总编排器。

代码：[knowledge_router_service.py](../../src/minibkn/application/knowledge_router_service.py)。

## 14. 第十一步：从自然语言识别修改动作

行政人员 HR001 说：

> 把 E001 在 8 月 3 日的焊工工时从 7 改成 8 小时。

LLM planner 不能直接改表，而是只能产生候选：

```json
{
  "intent":"action",
  "action_request":{
    "action_type_id":"adjust_timesheet",
    "object_type_id":"timesheet",
    "instance_id":"E001|2026-08-03|WELDER",
    "parameters":{"new_hours":8,"expected_version":1}
  }
}
```

随后 `/ask-intelligent` 返回：

```json
{
  "requires_action_confirmation":true,
  "answer":"动作请求已识别，但尚未执行。"
}
```

这只表示要进入动作安全流程，并不是风险引擎已经决定必须人工审批。

代码：[QueryPlanService.ask_intelligently](../../src/minibkn/application/query_plan_service.py)。

## 15. 第十二步：动作权限、参数和风险

### 15.1 动作权限

系统检查 HR001：

- 有 `execute`；
- 能进入 payroll；
- actions 包含 `adjust_timesheet`；
- 能访问目标 timesheet 实例。

任何一项失败都拒绝。

### 15.2 参数绑定

动作只允许：

- 从对象绑定 employee_id、work_date、job_code、old_hours、version；
- 用户提交 new_hours 和 reason；
- 拒绝未声明参数；
- 缺少必填参数时拒绝。

### 15.3 风险规则

案例可以定义：

1. `new_hours < 0 or new_hours > 24` → deny；
2. 记录已月结 → deny；
3. `abs(new_hours - old_hours) > 2` → confirm；
4. 修改者不是记录本人且角色不是 hr_clerk → deny；
5. 修改已 approved 记录 → confirm；
6. ActionType 本身 `requires_approval=true` → confirm。

当前 Risk DSL 支持 object/action/subject 引用、比较、逻辑和安全算术，足以表达第 1、3、5、6 类规则。月结状态和组织授权仍需先提供可信数据。

策略求值失败时不是默认放行，而是 fail closed 为 deny。

代码：[policy.py](../../src/minibkn/domain/policy.py)、[action_service.py](../../src/minibkn/application/action_service.py)。

## 16. 第十三步：审批、白名单工具和审计

该记录已 approved，所以动作进入：

```text
pending_confirmation
```

具有 `approve` 权限的主管或财务经理查看：

- 谁提出修改；
- 原值 7；
- 新值 8；
- 命中了哪些风险；
- 数据来源和目标实例；
- trace_id。

批准后才调用白名单 `payroll/adjust_timesheet` 工具。

真实工具应：

1. 再验证 expected_version=1，避免他人已经修改；
2. 在考勤系统事务中更新；
3. version 增加到 2；
4. 写数据变更审计；
5. 返回标准化结果；
6. 触发 MiniBKN 增量构建或事件更新索引。

当前仓库没有这个工资工具，只有安全的本地补货预警演示工具。但 ToolRegistry、动作状态机、审批、幂等和 trace 已实现。

事件可能是：

```text
action.requested
risk.evaluated
action.awaiting_confirmation
action.confirmation_approved
tool.started
tool.succeeded
```

代码：[工具白名单](../../src/minibkn/adapters/tools/registry.py)、[动作服务](../../src/minibkn/application/action_service.py)。

## 17. 这个案例中 AI 到底在哪里参与

| 环节 | AI 可以做什么 | AI 不能做什么 |
| --- | --- | --- |
| 数据建模 | 解释字段、提出对象/关系/动作/风险候选 | 跳过人工审核发布 Schema |
| 查询理解 | 改写、同义词、子问题、歧义、QueryPlan 候选 | 发明不存在字段或运行 SQL |
| 知识路由 | 后续可提出结构化/文档/混合路线 | 绕过 collection 权限 |
| 回答 | 基于证据组织自然语言 | 在无证据时编工资数字 |
| 动作识别 | 生成 action_request 候选 | 直接调用写工具 |
| 风险辅助 | 推荐规则草案、解释命中原因 | 代替确定性策略引擎和审批人 |

项目的核心思想不是“让 AI 控制一切”，而是：AI 负责理解和提议，确定性代码负责校验、权限、计算、风险和执行。

## 18. 当前版本可以怎样演示这个思路

仓库尚未提供 payroll 样例文件，因此不能直接声称上述场景已经全部运行。当前最接近的可运行演示是：

1. 用 CRM 示例演示跨表对象关系、QueryPlan 和聚合；
2. 用供应链示例演示风险、审批、白名单工具和 trace；
3. 用 LightRAG 测试文档演示制度文档的入库、检索和混合证据；
4. 用 RBAC 示例演示不同角色对文件、集合和动作的拒绝；
5. 把本案例作为“如何把通用内核迁移到财务工时领域”的架构设计。

启动和测试命令见 [02：启动与测试](02_STARTUP_AND_FUNCTIONAL_TEST_CASES.md)。

## 19. 如果要把案例真正开发出来，建议顺序

### P0：可演示 payroll MVP

1. 增加四张样例 CSV 与 50–200 名模拟员工；
2. 编写 payroll BKN：employee、timesheet、job_rate、bonus；
3. 增加等值关系和基本 QueryPlan 测试；
4. 增加三份制度 Markdown 并接入 LightRAG；
5. 增加员工、主管、HR、财务经理示例策略；
6. UI 增加 `/ask-intelligent` 的追问展示。

### P1：安全可用

1. Principal 增加可信 employee_id、department_id、manager_scope；
2. 实现行级与字段级策略；
3. 权限过滤覆盖 search、QueryPlan、subgraph、action 和 document；
4. 增加权限矩阵与越权回归测试；
5. 对回答前后的证据做敏感字段审计。

### P2：动作闭环

1. 定义 `adjust_timesheet` BKN；
2. 实现只写模拟数据库的白名单工具；
3. 加入 expected_version、月结锁、幂等和审批；
4. 动作成功后触发增量索引；
5. UI 增加动作预览、风险说明和审批页。

### P3：企业化

1. 对接 OIDC/SSO 和企业人员目录；
2. 对接真实考勤/薪酬服务，而不是写 CSV；
3. 引入密钥管理、HTTPS、审计归档；
4. 将 QueryPlan 与知识路由统一为多子问题编排器；
5. 构建真实财务问答、权限和动作评测集。

## 20. 应设计的测试集合

### 数据与图

- 单字段、组合主键正确；
- 外键候选可解释；
- 重复工时行被发现；
- employee/timesheet/bonus 关系正确；
- 费率日期区间不会被错误当成简单等值关系。

### 查询

- 员工本人总工时；
- 主管团队聚合；
- submitted 状态筛选；
- 多跳 employee → timesheet → job_rate；
- 模糊时间自动追问；
- 不存在状态值要求澄清；
- 制度文档、结构化数据、hybrid 三种问题。

### 权限

- E001 不得读取 E002 行；
- M001 不得读取 M002 团队；
- HR 可以改工时但不能查看奖金金额；
- finance 可以看工价与奖金但不能改工时；
- 无权限 collection 不进入 LightRAG 查询；
- 无权限证据不会出现在回答和 trace 中。

### 动作

- 非授权角色 403；
- 负数或超过 24 小时 deny；
- 已月结 deny；
- 修改 approved 记录 confirm；
- 拒绝审批后工具调用次数为 0；
- 重复 idempotency key 不重复修改；
- version 冲突返回 409；
- 每次结果都有 trace。

### AI 安全

- LLM 发明字段时被 Schema 校验拒绝；
- LLM 输出 SQL/额外字段时被合同拒绝；
- “帮我处理一下”不会猜测批量执行；
- action intent 只返回候选，不产生副作用；
- LLM 或 Embedding 服务失败时安全降级或明确失败。

## 21. 用这个案例总结整个项目

MiniBKN 在这个案例中不是一个简单“把 Excel 丢给聊天机器人”的系统。它把公司数据转换成带业务语义的对象、关系、动作和风险定义：

1. 表格提供事实；
2. BKN 说明事实的业务含义和关系；
3. Embedding 与 BM25 帮助找到相关对象；
4. QueryPlan 负责精确筛选、遍历和聚合；
5. LightRAG 负责制度、手册等非结构化证据；
6. RBAC/未来 ABAC 决定谁能看到什么；
7. LLM 负责理解自然语言和提出候选；
8. 风险 DSL、审批和工具白名单决定动作能否执行；
9. citation 与 trace 让结果可追溯。

这个案例也揭示了项目最重要的工程边界：如果没有可信身份、行级权限、权威工资计算和真实写回工具，它只能作为架构与主流程演示，不能直接承载真实工资业务。把这些限制讲清楚，本身就是系统设计能力的一部分。
