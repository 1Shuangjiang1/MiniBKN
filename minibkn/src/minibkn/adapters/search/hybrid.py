"""Dependency-free BM25, deterministic vector similarity, and RRF fusion."""

import math
import re
import zlib
from collections import Counter, OrderedDict
from dataclasses import dataclass
from threading import RLock

import numpy as np
import numpy.typing as npt

from minibkn.domain.models import SearchDocument, SearchHit, SearchMode
from minibkn.ports.search import Embedder

_WORD = re.compile(r"[a-zA-Z0-9_\-.]+|[\u4e00-\u9fff]")
_BUSINESS_IDENTIFIER = re.compile(r"(?=.*\d)[a-z0-9]+(?:[-_.][a-z0-9]+)+$")


@dataclass(frozen=True, slots=True)
class _Bm25Corpus:
    tokenized: list[list[str]]
    average_length: float
    document_frequency: Counter[str]


@dataclass(frozen=True, slots=True)
class _VectorCorpus:
    ids: list[str]
    matrix: npt.NDArray[np.float32]


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _WORD.findall(text)]


class TokenHashingEmbedder:
    """Small offline embedding baseline; replaceable by a semantic model adapter later."""

    def __init__(self, dimensions: int = 128) -> None:
        self._dimensions = dimensions

    @property
    def version(self) -> str:
        return f"token_hashing:v1:{self.dimensions}"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = zlib.crc32(token.encode("utf-8"))
            index = digest % self.dimensions
            sign = 1.0 if digest & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


class HybridRetriever:
    def __init__(
        self,
        embedder: Embedder | None = None,
        rrf_k: int = 60,
        bm25_cache_entries: int = 8,
    ) -> None:
        self.embedder = embedder or TokenHashingEmbedder()
        self.rrf_k = rrf_k
        self._bm25_cache_entries = bm25_cache_entries
        self._bm25_cache: OrderedDict[str, _Bm25Corpus] = OrderedDict()
        self._vector_cache: OrderedDict[str, _VectorCorpus] = OrderedDict()
        self._bm25_cache_hits = 0
        self._bm25_cache_misses = 0
        self._bm25_cache_lock = RLock()

    @property
    def bm25_cache_info(self) -> dict[str, int]:
        with self._bm25_cache_lock:
            return {
                "entries": len(self._bm25_cache),
                "hits": self._bm25_cache_hits,
                "misses": self._bm25_cache_misses,
            }

    def search(
        self,
        query: str,
        documents: list[SearchDocument],
        limit: int = 10,
        mode: SearchMode = SearchMode.HYBRID,
        corpus_key: str = "",
    ) -> list[SearchHit]:
        if not documents:
            return []
        bm25 = self._bm25(query, documents, corpus_key)
        bm25_ranked = sorted(bm25, key=lambda item: (-item[1], item[0]))
        bm25_ranks = {document_id: rank for rank, (document_id, _) in enumerate(bm25_ranked, 1)}
        documents_by_id = {document.id: document for document in documents}
        if mode == SearchMode.BM25:
            return [
                SearchHit(
                    document=documents_by_id[document_id],
                    score=score,
                    bm25_rank=rank,
                )
                for rank, (document_id, score) in enumerate(bm25_ranked[:limit], 1)
            ]
        query_vector = self.embedder.embed(query)
        vector_corpus = self._vector_corpus(documents, corpus_key)
        query_array = np.asarray(query_vector, dtype=np.float32)
        if vector_corpus.matrix.shape[1] != query_array.shape[0]:
            vector = [(document.id, 0.0) for document in documents]
        else:
            vector_scores = vector_corpus.matrix @ query_array
            vector = list(zip(vector_corpus.ids, map(float, vector_scores), strict=True))
        vector_ranked = sorted(vector, key=lambda item: (-item[1], item[0]))
        vector_ranks = {document_id: rank for rank, (document_id, _) in enumerate(vector_ranked, 1)}
        if mode == SearchMode.VECTOR:
            return [
                SearchHit(
                    document=documents_by_id[document_id],
                    score=score,
                    vector_rank=rank,
                )
                for rank, (document_id, score) in enumerate(vector_ranked[:limit], 1)
            ]
        scores = {
            document.id: 1 / (self.rrf_k + bm25_ranks[document.id])
            + 1 / (self.rrf_k + vector_ranks[document.id])
            for document in documents
        }
        ranked_ids = sorted(scores, key=lambda document_id: (-scores[document_id], document_id))
        return [
            SearchHit(
                document=documents_by_id[document_id],
                score=scores[document_id],
                bm25_rank=bm25_ranks[document_id],
                vector_rank=vector_ranks[document_id],
            )
            for document_id in ranked_ids[:limit]
        ]

    def _bm25(
        self, query: str, documents: list[SearchDocument], corpus_key: str
    ) -> list[tuple[str, float]]:
        key = corpus_key or self._corpus_key(documents)
        with self._bm25_cache_lock:
            corpus = self._bm25_cache.get(key)
            if corpus is None:
                tokenized = [tokenize(document.content) for document in documents]
                average_length = sum(map(len, tokenized)) / len(tokenized) or 1.0
                corpus = _Bm25Corpus(
                    tokenized=tokenized,
                    average_length=average_length,
                    document_frequency=Counter(
                        token for tokens in tokenized for token in set(tokens)
                    ),
                )
                self._bm25_cache[key] = corpus
                self._bm25_cache_misses += 1
                while len(self._bm25_cache) > self._bm25_cache_entries:
                    self._bm25_cache.popitem(last=False)
            else:
                self._bm25_cache.move_to_end(key)
                self._bm25_cache_hits += 1
        query_tokens = tokenize(query)
        result: list[tuple[str, float]] = []
        for document, tokens in zip(documents, corpus.tokenized, strict=True):
            frequencies = Counter(tokens)
            score = 0.0
            for token in query_tokens:
                frequency = frequencies[token]
                if not frequency:
                    continue
                count = corpus.document_frequency[token]
                inverse_frequency = math.log(1 + (len(documents) - count + 0.5) / (count + 0.5))
                denominator = frequency + 1.5 * (
                    1 - 0.75 + 0.75 * len(tokens) / corpus.average_length
                )
                query_weight = 3.0 if _BUSINESS_IDENTIFIER.fullmatch(token) else 1.0
                score += query_weight * inverse_frequency * frequency * 2.5 / denominator
            result.append((document.id, score))
        return result

    @staticmethod
    def _corpus_key(documents: list[SearchDocument]) -> str:
        checksum = 0
        for document in documents:
            checksum = zlib.crc32(document.id.encode("utf-8"), checksum)
            checksum = zlib.crc32(document.content.encode("utf-8"), checksum)
        return f"documents:{len(documents)}:{checksum}"

    def _vector_corpus(self, documents: list[SearchDocument], corpus_key: str) -> _VectorCorpus:
        key = corpus_key or self._corpus_key(documents)
        with self._bm25_cache_lock:
            corpus = self._vector_cache.get(key)
            if corpus is None:
                corpus = _VectorCorpus(
                    ids=[document.id for document in documents],
                    matrix=np.asarray(
                        [document.vector for document in documents], dtype=np.float32
                    ),
                )
                self._vector_cache[key] = corpus
                while len(self._vector_cache) > self._bm25_cache_entries:
                    self._vector_cache.popitem(last=False)
            else:
                self._vector_cache.move_to_end(key)
            return corpus
