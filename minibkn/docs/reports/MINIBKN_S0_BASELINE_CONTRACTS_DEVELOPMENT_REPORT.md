> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S0 基线与领域契约产品开发报告

> 完成日期：2026-08-16\
> 对应计划：[分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)\
> 状态：已完成

## 1. 这一阶段解决了什么

以前的 MiniBKN 已经能跑供应链演示，但后续的 QueryPlan、AI 建模、增量更新和 LightRAG 还没有共同的数据格式。如果直接分别开发，模块之间很容易互不兼容。

S0 先建立一套“公共合同”：后续模块必须用这些明确的数据结构交换信息。它类似于先确定插头标准，再制造电器。

## 2. 已完成的产品能力

### 2.1 统一证据 `EvidenceItem`

Schema、业务实例、关系、动作、计算结果和文档片段都可以转换为同一种证据。证据带来源引用、实体标识、内容、类型、分数和扩展属性，为后续统一回答和 Faithfulness 评测提供基础。

### 2.2 安全 QueryPlan 合同

查询计划可以表达：查询意图、对象、字段、过滤、关系跳转、聚合、分组、排序、结果数量、证据预算和动作请求。合同明确禁止额外字段，因此不能夹带 `raw_sql` 等任意执行内容。

本阶段只定义和验证计划格式，还没有接入 LLM 或执行计划；执行器属于 S4。

### 2.3 可审核的 AI 建模提案

`SchemaProposal` 保存建议类型、内容、置信度、证据、理由和人工审核状态。AI 后续只能提交建议，不能直接发布业务模型。

### 2.4 BKN 版本与构建任务

- BKN 生命周期：草稿、已审核、已批准、已发布；
- BuildJob：待处理、剖析、图构建、索引、校验、发布、失败；
- ChangeSet：新增、修改和删除的记录集合。

它们目前是领域合同，持久化和增量执行将在 S6 完成。

### 2.5 CRM 最小样例

新增客户、订单两张表及 `订单 → 客户` 关系 BKN。样例不是正式 500 客户评测集，而是证明 MiniBKN 的下一步开发不再只围绕供应链字段设计。

## 3. 新增文件

- `src/minibkn/domain/evidence.py`
- `src/minibkn/domain/query.py`
- `src/minibkn/domain/modeling.py`
- `src/minibkn/domain/build.py`
- `examples/crm/bkn/`
- `examples/crm/data/`
- `tests/unit/test_domain_contracts.py`

## 4. 测试结果

开发前基线：`13 passed`。

开发后：

```text
领域契约定向测试：4 passed
全量测试：17 passed
```

额外验证了：禁止未知字段、Action 查询必须带动作请求、非 count 聚合必须带字段、变更集数量计算和提案初始审核状态。

本地项目采用 non-editable 安装，新源码增加后要先执行：

```powershell
uv sync --extra dev --no-editable --reinstall-package minibkn
```

## 5. 尚未实现

- QueryPlan 还不会由 LLM 生成，也不会执行；
- AI 建模提案尚无 API 和数据库表；
- BKN 版本尚无独立版本仓库；
- ChangeSet 尚未连接真实增量更新；
- Evidence 尚未接入当前问答接口。

以上不是遗漏，而是刻意留给后续步骤逐个形成完整链路。

## 6. 给 S1 的明确接口

S1 必须使用 `EvidenceItem` 作为回答依据，并让 `AskResult` 返回结构化证据；不能新建另一套证据格式。当前 BKN 导入行为应明确映射为 `published`，但不得破坏原有 BKN 文件和 `/api/v1` 客户端。
