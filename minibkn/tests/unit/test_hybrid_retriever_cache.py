from minibkn.adapters.search import HybridRetriever, TokenHashingEmbedder
from minibkn.domain.models import SearchDocument, SearchLevel, SearchMode


class CountingEmbedder(TokenHashingEmbedder):
    def __init__(self) -> None:
        super().__init__(32)
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return super().embed(text)


def test_bm25_corpus_statistics_are_reused_and_versioned() -> None:
    embedder = TokenHashingEmbedder(32)
    documents = [
        SearchDocument(
            id="customer-1",
            network_id="crm",
            level=SearchLevel.INSTANCE,
            entity_type="customer",
            entity_id="C-1",
            title="星河科技",
            content="客户 星河科技 上海 enterprise",
            citation="resource://customers#row=2",
            vector=embedder.embed("客户 星河科技 上海 enterprise"),
        ),
        SearchDocument(
            id="customer-2",
            network_id="crm",
            level=SearchLevel.INSTANCE,
            entity_type="customer",
            entity_id="C-2",
            title="远航零售",
            content="客户 远航零售 杭州 retail",
            citation="resource://customers#row=3",
            vector=embedder.embed("客户 远航零售 杭州 retail"),
        ),
    ]
    retriever = HybridRetriever(embedder=embedder, bm25_cache_entries=2)

    first = retriever.search("上海客户", documents, mode=SearchMode.BM25, corpus_key="crm:v1")
    second = retriever.search("杭州客户", documents, mode=SearchMode.BM25, corpus_key="crm:v1")
    retriever.search("杭州客户", documents, mode=SearchMode.BM25, corpus_key="crm:v2")

    assert first[0].document.id == "customer-1"
    assert second[0].document.id == "customer-2"
    assert retriever.bm25_cache_info == {"entries": 2, "hits": 1, "misses": 2}


def test_bm25_does_not_call_embedding_provider() -> None:
    embedder = CountingEmbedder()
    documents = [
        SearchDocument(
            id="one",
            network_id="test",
            level=SearchLevel.INSTANCE,
            entity_type="customer",
            entity_id="C-1",
            title="客户",
            content="上海客户",
            citation="test://one",
            vector=[0.0] * 32,
        )
    ]

    HybridRetriever(embedder=embedder).search("上海", documents, mode=SearchMode.BM25)

    assert embedder.calls == 0


def test_exact_business_identifier_outranks_repeated_domain_words() -> None:
    embedder = TokenHashingEmbedder(32)
    documents = [
        SearchDocument(
            id="buyer",
            network_id="test",
            level=SearchLevel.INSTANCE,
            entity_type="buyer",
            entity_id="BUY-001",
            title="采购员",
            content="采购员 采购部门 采购业务",
            citation="test://buyer",
            vector=[0.0] * 32,
        ),
        SearchDocument(
            id="order",
            network_id="test",
            level=SearchLevel.INSTANCE,
            entity_type="purchase_order",
            entity_id="PO-00398",
            title="PO-00398",
            content="purchase_order PO-00398 amount 106962 status received",
            citation="test://order",
            vector=[0.0] * 32,
        ),
    ]

    hits = HybridRetriever(embedder=embedder).search(
        "采购单 PO-00398 的金额和状态", documents, mode=SearchMode.BM25
    )

    assert hits[0].document.id == "order"
