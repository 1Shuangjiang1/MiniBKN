"""Optional sentence-transformers semantic embedding adapter."""

from typing import Any


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed; run uv sync --extra semantic"
            ) from exc
        self._model: Any = SentenceTransformer(model_name)
        self._model_name = model_name

    @property
    def version(self) -> str:
        return f"sentence_transformers:{self._model_name}:{self.dimensions}"

    @property
    def dimensions(self) -> int:
        return int(self._model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(value) for value in vector.tolist()]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [[float(value) for value in vector.tolist()] for vector in vectors]
