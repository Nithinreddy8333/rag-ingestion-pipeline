"""Vector store access (Qdrant) and search.

The same code talks to an embedded on-disk Qdrant (default, zero setup) or a Qdrant server
(set QDRANT_URL). Each chunk is stored with a dense vector and a sparse keyword vector, so
one collection serves dense, keyword and hybrid search.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass

import numpy as np
from qdrant_client import QdrantClient, models

from .chunking import Chunk
from .config import Settings
from .embeddings import Embedder, sparse_vector

NAMESPACE = uuid.UUID("6f1d2c1e-8a57-4c0b-9c55-3d1a2b7e9f10")
MODES = ("dense", "sparse", "hybrid")


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    heading: str
    heading_path: str
    text: str
    score: float

    def as_dict(self) -> dict:
        return asdict(self)


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE, chunk_id))


class VectorStore:
    def __init__(self, settings: Settings, dim: int, client: QdrantClient | None = None):
        self.collection = settings.collection
        self.dim = dim
        if client is not None:
            self.client = client
        elif settings.qdrant_url:
            self.client = QdrantClient(url=settings.qdrant_url)
        else:
            settings.qdrant_path.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(settings.qdrant_path))

    def close(self) -> None:
        self.client.close()

    def ensure_collection(self, recreate: bool = False) -> None:
        exists = self.client.collection_exists(self.collection)
        if exists and recreate:
            self.client.delete_collection(self.collection)
            exists = False
        if exists:
            size = self.client.get_collection(self.collection).config.params.vectors["dense"].size
            if size != self.dim:
                raise RuntimeError(
                    f"Collection '{self.collection}' holds {size}-dimensional vectors but the "
                    f"embedder produces {self.dim}. Re-run with --rebuild to re-index."
                )
            return
        self.client.create_collection(
            self.collection,
            vectors_config={"dense": models.VectorParams(size=self.dim, distance=models.Distance.COSINE)},
            sparse_vectors_config={"sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )

    def upsert(self, chunks: list[Chunk], vectors: list[np.ndarray], doc_meta: dict) -> None:
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            indices, values = sparse_vector(chunk.embed_text)
            points.append(models.PointStruct(
                id=point_id(chunk.chunk_id),
                vector={"dense": vector.tolist(),
                        "sparse": models.SparseVector(indices=indices, values=values)},
                payload={"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "ordinal": chunk.ordinal,
                         "heading": chunk.heading, "heading_path": chunk.heading_path,
                         "text": chunk.text, **doc_meta},
            ))
        for start in range(0, len(points), 256):
            self.client.upsert(self.collection, points=points[start:start + 256], wait=True)

    def delete(self, chunk_ids: set[str]) -> None:
        if chunk_ids:
            self.client.delete(
                self.collection,
                points_selector=models.PointIdsList(points=[point_id(c) for c in sorted(chunk_ids)]),
                wait=True,
            )

    def count(self) -> int:
        return self.client.count(self.collection, exact=True).count

    def search(self, query: str, embedder: Embedder, mode: str = "hybrid", k: int = 5,
               category: str | None = None) -> list[Hit]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        query_filter = None
        if category:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="category", match=models.MatchValue(value=category))]
            )
        dense = embedder.embed([query])[0].tolist()
        indices, values = sparse_vector(query, is_query=True)
        sparse = models.SparseVector(indices=indices, values=values)
        common = {"limit": k, "with_payload": True, "query_filter": query_filter}
        if mode == "dense":
            result = self.client.query_points(self.collection, query=dense, using="dense", **common)
        elif mode == "sparse":
            result = self.client.query_points(self.collection, query=sparse, using="sparse", **common)
        else:
            depth = max(20, k * 4)
            result = self.client.query_points(
                self.collection,
                prefetch=[
                    models.Prefetch(query=dense, using="dense", limit=depth, filter=query_filter),
                    models.Prefetch(query=sparse, using="sparse", limit=depth, filter=query_filter),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=k, with_payload=True,
            )
        return [
            Hit(chunk_id=p.payload["chunk_id"], doc_id=p.payload["doc_id"], heading=p.payload["heading"],
                heading_path=p.payload["heading_path"], text=p.payload["text"], score=float(p.score))
            for p in result.points
        ]
