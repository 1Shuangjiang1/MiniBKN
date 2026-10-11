> Archive / 历史文档：保留当时的设计与评测记录；功能现状、启动命令和边界以根目录 [README](../../README.zh.md) 为准。本机路径已去标识，历史命令不保证适用于当前版本。

# MiniBKN Architecture

MiniBKN uses a modular monolith with ports and adapters. FastAPI is the delivery layer; use-case
services own orchestration; domain models contain immutable contracts; adapters own SQLite, local
files, search, and tools.

```text
REST / Swagger / React / MCP
          |
          v
Identity + RBAC | Query understanding | Knowledge router
          |
          v
Structured BKN + QueryPlan | LightRAG REST sidecar | Action gate
          |
          v
SQLite/CSV | BM25/BGE-M3/RRF | isolated document workspaces | allowlisted tools
```

## Read path

1. Discover CSV files or SQLite tables as Resources.
2. Use ObjectType field mappings to create ObjectInstances.
3. Use RelationType mappings to create persisted RelationInstances.
4. Build Schema, instance, and action SearchDocuments.
5. Retrieve with BM25 and vector cosine, then fuse with RRF.
6. Expand retrieved instances through graph edges.
7. Normalize Schema, instance, relation, and action results into provider-neutral EvidenceItems.
8. Return a domain-neutral evidence-driven answer, three context levels, citations, and structured
   evidence. The fallback answer generator never contains supply-chain-specific field rules.

Authorization runs before retrieval and QueryPlan execution. Resource-scoped principals cannot load
restricted instance documents, objects, or graph edges into the answer context.

## Document path

1. Authenticate the principal and resolve authorized document collections.
2. Route the question to structured, document, or hybrid retrieval.
3. Call one fixed LightRAG REST endpoint/workspace per security collection.
4. Prefer `/query/data`, normalize chunks to EvidenceItems, and retain source citations.
5. Merge and deduplicate authorized structured and document evidence.
6. Degrade to structured evidence when an optional sidecar fails and configuration allows it.

Separate workspaces are a security boundary: post-filtering references from a shared LightRAG graph
cannot guarantee that restricted information did not affect entity summaries.

## Action path

1. Resolve the ActionType and target instance.
2. Bind and validate parameters.
3. Evaluate RiskTypes and choose allow, confirm, or deny.
4. Resolve only an explicitly registered tool.
5. Persist normalized execution state and append TraceEvents.

The authenticated principal, not caller-supplied subject fields, supplies trusted role attributes to
risk policies. Execute and approve are separate permissions.

The process boundary can later be split at each port without changing the domain or API use cases.
