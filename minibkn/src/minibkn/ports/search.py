"""Embedding port used by the hybrid retriever."""

from typing import Protocol


class Embedder(Protocol):
    @property
    def version(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...
