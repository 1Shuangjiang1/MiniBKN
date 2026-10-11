# Copyright openbkn.ai
#
# Licensed under the OpenBKN License. See LICENSE-OPENBKN.txt in the project root.

"""Remote embedding, cache, and failover adapters."""

import math
from collections import OrderedDict
from threading import RLock

import httpx

from minibkn.ports.search import Embedder


class EmbeddingProviderError(RuntimeError):
    pass


class SiliconFlowEmbedder:
    def __init__(
        self,
        api_key: str,
        model: str = "BAAI/bge-m3",
        dimensions: int = 1024,
        base_url: str = "https://api.siliconflow.cn/v1",
        batch_size: int = 32,
        timeout: float = 30.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("SiliconFlow API key is required")
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._batch_size = batch_size
        self._timeout = timeout
        self._max_retries = max_retries
        self._transport = transport

    @property
    def version(self) -> str:
        return f"siliconflow:{self._model}:{self.dimensions}"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            for start in range(0, len(texts), self._batch_size):
                vectors.extend(self._request(texts[start : start + self._batch_size], client))
        return vectors

    def _request(self, texts: list[str], client: httpx.Client) -> list[list[float]]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                request_payload: dict[str, object] = {
                    "model": self._model,
                    "input": texts,
                    "encoding_format": "float",
                }
                if self._model.startswith("Qwen/Qwen3-"):
                    request_payload["dimensions"] = self.dimensions
                response = client.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=request_payload,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise EmbeddingProviderError(
                        f"temporary embedding provider error: HTTP {response.status_code}"
                    )
                response.raise_for_status()
                return self._validate_vectors(response.json(), len(texts))
            except (httpx.HTTPError, EmbeddingProviderError, KeyError, TypeError) as exc:
                last_error = exc
                if attempt == self._max_retries:
                    break
        raise EmbeddingProviderError("SiliconFlow embedding request failed") from last_error

    def _validate_vectors(self, payload: object, expected: int) -> list[list[float]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise EmbeddingProviderError("embedding response has no data list")
        ordered = sorted(payload["data"], key=lambda item: item["index"])
        vectors = [[float(value) for value in item["embedding"]] for item in ordered]
        if len(vectors) != expected:
            raise EmbeddingProviderError("embedding response count does not match input")
        if any(len(vector) != self.dimensions for vector in vectors):
            raise EmbeddingProviderError("embedding response dimensions do not match configuration")
        if any(not math.isfinite(value) for vector in vectors for value in vector):
            raise EmbeddingProviderError("embedding response contains non-finite values")
        return vectors


class CachingEmbedder:
    def __init__(self, inner: Embedder, max_entries: int = 10000) -> None:
        self._inner = inner
        self._max_entries = max_entries
        self._cache: OrderedDict[tuple[str, str], list[float]] = OrderedDict()
        self._lock = RLock()

    @property
    def version(self) -> str:
        return self._inner.version

    @property
    def dimensions(self) -> int:
        return self._inner.dimensions

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            missing = list(
                dict.fromkeys(text for text in texts if (self.version, text) not in self._cache)
            )
        if missing:
            fresh = self._inner.embed_many(missing)
            with self._lock:
                for text, vector in zip(missing, fresh, strict=True):
                    self._cache[(self.version, text)] = vector
                    self._cache.move_to_end((self.version, text))
                    while len(self._cache) > self._max_entries:
                        self._cache.popitem(last=False)
        with self._lock:
            return [self._cache[(self.version, text)] for text in texts]


class FailoverEmbedder:
    """Latch to a deterministic fallback after the remote provider fails once."""

    def __init__(self, primary: Embedder, fallback: Embedder) -> None:
        if primary.dimensions != fallback.dimensions:
            raise ValueError("primary and fallback embedding dimensions must match")
        self._primary = primary
        self._fallback = fallback
        self._using_fallback = False

    @property
    def version(self) -> str:
        active = self._fallback if self._using_fallback else self._primary
        return active.version

    @property
    def dimensions(self) -> int:
        return self._primary.dimensions

    @property
    def using_fallback(self) -> bool:
        return self._using_fallback

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if self._using_fallback:
            return self._fallback.embed_many(texts)
        try:
            return self._primary.embed_many(texts)
        except EmbeddingProviderError:
            self._using_fallback = True
            return self._fallback.embed_many(texts)
