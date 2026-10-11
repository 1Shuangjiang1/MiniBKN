> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN S3 真实 Embedding 产品开发报告

> 完成日期：2026-08-16\
> 前置报告：[S1 通用核心产品开发报告](MINIBKN_S1_GENERIC_CORE_DEVELOPMENT_REPORT.md)\
> 对应计划：[分步开发计划](../plans/MINIBKN_STEPWISE_DEVELOPMENT_PLAN.md)\
> 状态：已完成

## 1. 与 S1 的衔接

S1 已把问答内容统一为 `EvidenceItem`。S3 不改变证据和回答格式，只替换“如何把文本变成向量”的底层能力，因此供应链、CRM 和未来文档证据都能共用同一套检索接口。

## 2. 已完成的能力

- 新增硅基流动 `/v1/embeddings` 适配器；
- 默认推荐模型为 `BAAI/bge-m3`，维度由配置指定；
- 支持批量请求，建索引不再逐条调用远程 API；
- 验证响应数量、顺序、维度和非有限数值；
- 对 429、5xx 和网络错误做有限重试；
- 增加进程内 LRU 缓存，相同模型和文本不重复请求；
- 远程服务失败后可锁定到同维度 token-hashing 降级；
- 新增搜索索引清单，保存模型版本、维度、文档数量和时间；
- 模型或维度变化时拒绝使用旧索引，提示重建；
- 如果查询时远程模型突然降级，也会拒绝混用两套向量。

## 3. 配置方法

```dotenv
MINIBKN_EMBEDDING_PROVIDER=siliconflow
MINIBKN_EMBEDDING_MODEL=BAAI/bge-m3
MINIBKN_EMBEDDING_DIMENSIONS=1024
MINIBKN_EMBEDDING_API_BASE=https://api.siliconflow.cn/v1
MINIBKN_EMBEDDING_API_KEY=只写在本地.env
MINIBKN_EMBEDDING_BATCH_SIZE=32
MINIBKN_EMBEDDING_TIMEOUT_SECONDS=30
MINIBKN_EMBEDDING_CACHE_ENTRIES=10000
MINIBKN_EMBEDDING_FAILOVER_ENABLED=true
```

没有 Key 或没有选择 `siliconflow` 时，程序仍使用离线 token-hashing，启动不会被可选服务阻塞。

## 4. API 变化

索引构建响应新增：

```json
{
  "embedding_version": "siliconflow:BAAI/bge-m3:1024",
  "embedding_dimensions": 1024
}
```

旧字段全部保留。索引版本不匹配返回 `409 INDEX_VERSION_MISMATCH`。

## 5. 测试结果

```text
S3 定向测试：6 passed
全量测试：28 passed
Ruff：通过
Mypy strict：51 个源文件通过
```

测试覆盖批次拆分、乱序响应恢复、缓存去重、远程失败降级、维度保护和跨进程索引版本不匹配。

## 6. 未验证与限制

- 本阶段没有收到真实硅基流动 API Key，因此没有产生真实费用，也没有声称真实模型效果数字；
- 当前缓存是进程内缓存，重启后失效；持久化向量缓存可在 S6 增量构建中继续增强；
- 同步 HTTP 调用在大规模生产环境应迁移为异步任务；当前批处理已经避免逐条请求，适合本地作品集规模；
- 降级后必须重建索引，系统不会拿哈希查询向量匹配语义模型索引。

## 7. 给 S4 的接口

S4 的 QueryPlan 执行器只通过 `RetrievalService` 获取候选证据，不直接调用具体 Embedding 服务。计划执行必须保留索引版本检查，并把检索模式、Top-K 和证据预算记录到结果中。
