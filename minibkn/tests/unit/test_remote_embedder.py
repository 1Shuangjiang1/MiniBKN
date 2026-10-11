import httpx
import pytest

from minibkn.adapters.search import (
    CachingEmbedder,
    EmbeddingProviderError,
    FailoverEmbedder,
    SiliconFlowEmbedder,
    TokenHashingEmbedder,
)


def test_siliconflow_embedder_batches_and_restores_response_order() -> None:
    requests: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        requests.append(payload["input"])
        assert "dimensions" not in payload
        assert request.headers["authorization"] == "Bearer secret"
        data = [
            {"index": index, "embedding": [float(index + 1), 0.0, 0.0]}
            for index, _ in enumerate(payload["input"])
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    embedder = SiliconFlowEmbedder(
        api_key="secret",
        model="BAAI/bge-m3",
        dimensions=3,
        batch_size=2,
        transport=httpx.MockTransport(handler),
    )

    vectors = embedder.embed_many(["a", "b", "c"])

    assert requests == [["a", "b"], ["c"]]
    assert vectors == [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    assert embedder.version == "siliconflow:BAAI/bge-m3:3"


def test_siliconflow_qwen_embedder_sends_supported_dimensions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        assert payload["dimensions"] == 64
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0] * 64}]})

    embedder = SiliconFlowEmbedder(
        api_key="secret",
        model="Qwen/Qwen3-Embedding-0.6B",
        dimensions=64,
        transport=httpx.MockTransport(handler),
    )

    assert len(embedder.embed("customer")) == 64


def test_siliconflow_retries_rate_limit_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.0, 1.0, 0.0]}]},
        )

    embedder = SiliconFlowEmbedder(
        api_key="secret",
        dimensions=3,
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )

    assert embedder.embed("customer") == [0.0, 1.0, 0.0]
    assert calls == 2


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "no data"),
        ({"data": []}, "count"),
        ({"data": [{"index": 0, "embedding": [0.0]}]}, "dimensions"),
        ({"data": [{"index": 0, "embedding": ["nan"] * 3}]}, "non-finite"),
    ],
)
def test_siliconflow_rejects_malformed_vectors(payload: object, message: str) -> None:
    embedder = SiliconFlowEmbedder(
        api_key="secret",
        dimensions=3,
        max_retries=0,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(EmbeddingProviderError) as error:
        embedder.embed("customer")

    assert message in str(error.value.__cause__)


def test_siliconflow_wraps_transport_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider timeout", request=request)

    embedder = SiliconFlowEmbedder(
        api_key="secret",
        dimensions=3,
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EmbeddingProviderError, match="request failed"):
        embedder.embed("customer")


def test_cache_deduplicates_texts_before_calling_provider() -> None:
    calls: list[list[str]] = []

    class FakeEmbedder:
        version = "fake:v1:2"
        dimensions = 2

        def embed(self, text: str) -> list[float]:
            return self.embed_many([text])[0]

        def embed_many(self, texts: list[str]) -> list[list[float]]:
            calls.append(texts)
            return [[float(len(text)), 0.0] for text in texts]

    embedder = CachingEmbedder(FakeEmbedder())

    assert embedder.embed_many(["crm", "crm", "order"]) == [
        [3.0, 0.0],
        [3.0, 0.0],
        [5.0, 0.0],
    ]
    assert embedder.embed_many(["order"]) == [[5.0, 0.0]]
    assert calls == [["crm", "order"]]


def test_remote_failure_latches_to_same_dimension_offline_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    primary = SiliconFlowEmbedder(
        api_key="secret",
        dimensions=8,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )
    embedder = FailoverEmbedder(primary, TokenHashingEmbedder(8))

    assert len(embedder.embed("customer")) == 8
    assert embedder.using_fallback is True
    assert embedder.version == "token_hashing:v1:8"


def test_failover_rejects_different_vector_dimensions() -> None:
    primary = TokenHashingEmbedder(8)
    with pytest.raises(ValueError, match="dimensions"):
        FailoverEmbedder(primary, TokenHashingEmbedder(16))
