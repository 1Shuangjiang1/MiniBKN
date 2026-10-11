> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# 03：数据导入、索引构建与工时薪酬现实案例

## 先区分两类“文档”

项目里有两条不同的知识进入路径：

1. **结构化数据**：CSV/SQLite → 字段发现 → BKN Schema → 对象/关系 → 检索索引。
2. **非结构化文档**：制度、合同、手册文本 → MiniBKN 权限检查 → LightRAG 切块、实体关系和向量索引。

结构化分支以数据库中的“对象实例和关系”为事实；LightRAG 分支以文档片段为证据。它们在 `/ask-routed` 中统一成 `EvidenceItem`，但底层索引不是同一个。

## 结构化数据如何导入

### 第一步：登记数据源

用户提供 CSV 文件/目录或 SQLite 文件路径。系统只保存来源描述，尚未生成知识图。

代码：[数据源适配器](../../src/minibkn/adapters/datasource/local.py)、[register_source](../../src/minibkn/application/graph_service.py)。

### 第二步：字段发现与关系候选

系统读取表头和样本数据，识别类型、空值、唯一率；寻找单字段或组合主键；再通过字段名、类型兼容和取值重叠率生成外键候选。候选带置信度和原因，不应把猜测直接当业务真相。

代码：[data_profiling.py](../../src/minibkn/application/data_profiling.py)。

### 第三步：形成 BKN Schema

可以导入人工编写的 `.bkn`，也可以从发现结果生成初始网络。BKN 定义：有哪些对象、字段如何映射、主键是什么、两个对象怎样关联、可执行什么动作、哪些风险条件适用。

AI 建模只生成待审核提案；必须逐条接受/拒绝后发布。当前 Schema AI 被限制为增强名称和说明，不能任意修改字段 ID、主键或映射。

代码：[schema_generation_service.py](../../src/minibkn/application/schema_generation_service.py)、[modeling_service.py](../../src/minibkn/application/modeling_service.py)。

### 第四步：物化为图

每一行按 ObjectType 映射为 `ObjectInstance`，主键组合成 `instance_id`。关系通过 BKN 中声明的字段映射连接：源对象字段值等于目标对象字段值，就生成 `RelationInstance`。

代码：[graph_service.py](../../src/minibkn/application/graph_service.py)。

### 第五步：建立检索索引

系统把三类内容转成统一搜索文档：

- Schema 文档：对象、字段、关系的含义；
- Instance 文档：每个业务数据行；
- Action 文档：可用动作的名称、说明和绑定对象。

然后批量生成向量，保存索引清单（模型版本、维度、文档数）。查询时 BM25 与向量相似度各自产生排名，再用 RRF 融合。增量构建会比较对象和搜索文档，只有新增/修改项重新 Embedding；失败会恢复旧图和旧索引。

代码：[retrieval_service.py](../../src/minibkn/application/retrieval_service.py)、[hybrid.py](../../src/minibkn/adapters/search/hybrid.py)、[build_service.py](../../src/minibkn/application/build_service.py)。

## 非结构化文档如何导入

启用 LightRAG 后，`POST /documents/text` 首先检查用户是否允许访问目标 collection，再把文本送到对应的独立 LightRAG endpoint/workspace。LightRAG 异步完成切块、实体/关系提取和向量索引，返回 `track_id`；MiniBKN 可轮询状态。查询使用 LightRAG `/query/data` 取回原始 chunks，最终答案仍由 MiniBKN 统一生成。

代码：[document_knowledge.py](../../src/minibkn/adapters/document_knowledge.py)、[knowledge_router_service.py](../../src/minibkn/application/knowledge_router_service.py)。

当前 MiniBKN 包装接口只直接接收文本；PDF/DOCX 上传解析尚未在 UI/API 中产品化。

## 工时、工价、奖金三表案例

假设财务员有：

### `timesheets.csv`

| employee_id | work_date | job_code | hours | status | supervisor_id |
| --- | --- | --- | ---: | --- | --- |
| E001 | 2026-08-01 | WELDER | 8 | approved | M001 |

建议组合主键是 `(employee_id, work_date, job_code)`，因为同一个员工跨日期、跨工种会有多行。

### `job_rates.csv`

| job_code | hourly_rate | effective_from | effective_to |
| --- | ---: | --- | --- |
| WELDER | 80 | 2026-01-01 | 2026-12-31 |

主键在现实中最好是 `(job_code, effective_from)`，因为费率可能随时间变化。

### `bonuses.csv`

| employee_id | bonus_month | amount | reason | status |
| --- | --- | ---: | --- | --- |
| E001 | 2026-08 | 1000 | 项目奖 | approved |

建议组合主键是 `(employee_id, bonus_month, reason)` 或单独增加 `bonus_id`。

### BKN 中的对象和关系

可以定义：

- `timesheet`：映射工时表；
- `job_rate`：映射工价表；
- `bonus`：映射奖金表；
- `uses_rate`：`timesheet.job_code -> job_rate.job_code`；
- `has_bonus`：通过 `employee_id` 关联工时和奖金。

但三张表缺少权威人员目录。为了安全地知道“当前登录者 E001”“M001 管理哪些员工”，生产设计应增加 `employees`/企业身份目录，至少包含 `employee_id`、`manager_id`、部门和在职状态，并把认证身份稳定映射到 employee_id。不能让大模型从姓名猜身份。

## 查询会怎样工作

员工问：“我 8 月有多少工时和奖金？”

理想 QueryPlan 是：用认证上下文强制加 `employee_id=E001`；筛选 8 月工时并求和；筛选 E001 的 8 月奖金并求和；返回两项计算证据。主管问“我团队中谁本月加班超过 20 小时”，系统应先从组织关系得到下属范围，再聚合筛选。

行政人员说：“把 E001 8 月 3 日的焊工工时从 7 改成 8”，应识别为 `adjust_timesheet` 动作，绑定唯一实例和新工时，经过权限、状态、改动幅度、月结状态和审批规则，再调用白名单 HR/考勤接口。

## 当前代码能做到什么，不能做到什么

**已实现：** CSV 发现、组合键/外键候选、BKN 关系、图与索引、查询过滤/遍历/聚合、文件级 RBAC、动作级 RBAC、风险 DSL、审批与审计。

**尚未实现的关键生产能力：**

- 行级 ABAC：员工只能看 `employee_id == principal.employee_id`；
- 主管组织范围：只能看其组织树下属；
- 字段级脱敏：普通员工不能看别人工价或奖金原因；
- 工时写回工具：当前唯一注册工具是本地补货预警，不会修改考勤表；
- 事务写回、乐观锁、月结锁定和数据变更审批；
- 统一企业 SSO/员工目录。

因此，这个案例展示的是“现有通用内核如何映射到财务人事场景，以及还需要哪一层企业安全扩展”，不是宣称三张表放进去后已经能安全上线。

## 推荐的权限扩展模型（待增强）

```text
Principal attributes: employee_id, department_id, manager_scope
        ↓
网络级：是否允许进入 payroll 网络
        ↓
资源级：是否允许 timesheets / bonuses / job_rates
        ↓
行级：本人、直属/递归下属、授权部门
        ↓
字段级：奖金、费率、审计字段是否可见
        ↓
动作级：是否允许 adjust_timesheet
        ↓
风险级：已月结/跨度过大/改他人记录 → confirm 或 deny
```

行级过滤必须发生在检索、QueryPlan、子图和动作取实例之前，而不是答案生成之后“删掉敏感文字”。否则敏感数据已经进入检索上下文，属于安全漏洞。
