from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from rag_ingest import corpus
from rag_ingest.config import Settings
from rag_ingest.embeddings import HashingEmbedder
from rag_ingest.store import VectorStore

SERVICES = ["orders-cdc", "billing-export", "fraud-features", "search-indexer"]


class CountingEmbedder(HashingEmbedder):
    """Hashing embedder that records how many texts it was asked to embed."""

    def __init__(self):
        super().__init__(256)
        self.calls: list[int] = []

    def embed(self, texts):
        self.calls.append(len(texts))
        return super().embed(texts)

    @property
    def total(self) -> int:
        return sum(self.calls)


@pytest.fixture()
def env(tmp_path: Path):
    """(settings, embedder, store) over a small corpus: 4 runbooks and 8 policies."""
    settings = Settings()
    settings.docs_dir = tmp_path / "docs"
    settings.state_path = tmp_path / "state.duckdb"
    settings.collection = "test"
    corpus.write(corpus.generate(seed=3, services=SERVICES), settings.docs_dir)
    embedder = CountingEmbedder()
    store = VectorStore(settings, embedder.dim, client=QdrantClient(":memory:"))
    yield settings, embedder, store
    store.close()
