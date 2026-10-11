import sys
from types import ModuleType
from typing import Any

from minibkn.adapters.search.semantic import SentenceTransformerEmbedder


class FakeVector:
    def tolist(self) -> list[float]:
        return [0.25, 0.75]


class FakeSentenceTransformer:
    def __init__(self, model_name: str) -> None:
        assert model_name == "fake-model"

    def encode(self, text: str, normalize_embeddings: bool) -> FakeVector:
        assert text == "业务知识"
        assert normalize_embeddings is True
        return FakeVector()


def test_sentence_transformer_adapter_uses_normalized_vectors(monkeypatch: Any) -> None:
    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)

    embedder = SentenceTransformerEmbedder("fake-model")
    assert embedder.embed("业务知识") == [0.25, 0.75]
