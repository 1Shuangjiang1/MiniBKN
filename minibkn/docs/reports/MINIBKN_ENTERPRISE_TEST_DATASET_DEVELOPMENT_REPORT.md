> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN 多行业测试数据集产品开发报告

> 日期：2026-08-17\
> 对应计划：[全量测试与评测执行计划](../plans/MINIBKN_COMPREHENSIVE_TEST_AND_EVALUATION_PLAN.md)\
> 前置参考：[P0 查询智能与数据发现报告](MINIBKN_P0_QUERY_INTELLIGENCE_AND_DATA_DISCOVERY_DEVELOPMENT_REPORT.md)

## 1. 本模块完成了什么

这一步为后续测试准备了一座可重复搭建的“模拟公司”。以前主要只有 CRM 和供应链例子，现在增加了采购、财务、人事三个业务域，证明测试不会只围绕某一种表格写死。

新增的一键生成脚本会用固定随机种子创建：

- 采购：供应商、采购员、采购单、采购明细、付款；
- 财务：客户、发票、收款、部门、报销；
- 人事：部门、员工、请假、调岗；
- 数据质量：组合主键、部分孤儿外键、重复值、空值和模式漂移说明；
- 120 道检索盲测题、15 道 QueryPlan 盲测题、6 道对抗题、45 道动作题；
- 每个业务域对应的 Object、Relation、Action 和 Risk BKN 文件。

所有姓名和企业均为合成数据，不包含真实人员或公司信息。

## 2. 测试时发现并修复的问题

多行业数据首次运行时发现两个主外键识别缺陷：

1. 付款表中的 `po_id`、收款表中的 `invoice_id` 恰好唯一时，会和本表主键一起被误判成复合主键；
2. `company_code + department_code` 是合理组合主键，但旧评分没有把 `_code` 当作标识字段，因此置信度不足。

修复后，CSV 适配器只选择一个最符合“本表自身标识”的初始单字段主键，其余候选交给数据剖析器判断；数据剖析器也增加了 `_code` 标识信号。测试还发现 BM25 查询会无意义调用 Embedding，现已改为纯 BM25 模式完全不访问向量服务，避免正式评测浪费 API 额度。

## 3. 生成结果

| 项目 | 数量 |
| --- | ---: |
| 业务域 | 3 |
| 企业测试目录内文件 | 57 |
| 检索盲测题 | 120 |
| QueryPlan 盲测题 | 15 |
| 对抗题 | 6 |
| 动作安全题 | 45 |

数据入口位于 `evals/enterprise/`，冻结题集位于 `evals/datasets/`。总清单记录随机种子 `20260817`，重复运行应生成相同业务数据和题目。

## 4. 已运行测试

```powershell
.venv\Scripts\python.exe scripts\generate_enterprise_test_suite.py
.venv\Scripts\ruff.exe check ...
.venv\Scripts\pytest.exe -q tests\unit\test_enterprise_evaluation_dataset.py tests\unit\test_datasource_adapters.py tests\unit\test_hybrid_retriever_cache.py
```

结果：Ruff 通过，相关 8 项测试全部通过。测试验证了题集数量与 ID 唯一性、三套 BKN 可解析、组合主键、80% 覆盖的外键、噪声字段不误判，以及 BM25 不调用 Embedding。

## 5. 如何复现

在 `minibkn` 目录运行：

```powershell
.venv\Scripts\python.exe scripts\generate_enterprise_test_suite.py
```

生成器会覆盖其负责的合成数据文件，不触碰用户业务数据。

## 6. 当前限制和下一步

- 当前 QueryPlan 盲测每个业务域 5 题，主要用来发现跨领域提示问题；正式运行后若参与调优，必须换新随机种子生成新的 holdout；
- BKN 和表格已准备好，但真实 DeepSeek、BGE-M3、Ragas 和性能数字尚未在本模块产生；
- 下一步先补齐确定性的 API、安全、增量、故障恢复测试，再运行付费模型评测。
