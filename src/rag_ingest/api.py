"""A small read-only search API over the index.

    uvicorn rag_ingest.api:app --port 8000
    GET /health
    GET /search?q=...&mode=hybrid&k=5&category=runbooks
    GET /status     freshness: what the next ingest run would change

With the embedded (on-disk) Qdrant only one process can open the index at a time, so stop
the API while ingesting, or point both at a Qdrant server with QDRANT_URL.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from .config import Settings
from .embeddings import get_embedder
from .pipeline import pending_changes
from .store import MODES, VectorStore


def create_app(settings: Settings | None = None, store: VectorStore | None = None) -> FastAPI:
    settings = settings or Settings()
    resources: dict = {}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        embedder = get_embedder(settings.embed_provider, settings.embed_model)
        resources["embedder"] = embedder
        resources["store"] = store or VectorStore(settings, embedder.dim)
        yield
        if store is None:
            resources["store"].close()

    app = FastAPI(title="RAG ingestion pipeline: search", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "points": resources["store"].count(), "embedder": resources["embedder"].name}

    @app.get("/search")
    def search(q: str = Query(min_length=1, max_length=500), mode: str = "hybrid",
               k: int = Query(5, ge=1, le=50), category: str | None = None) -> dict:
        if mode not in MODES:
            raise HTTPException(status_code=422, detail=f"mode must be one of {list(MODES)}")
        hits = resources["store"].search(q, resources["embedder"], mode=mode, k=k, category=category)
        return {"query": q, "mode": mode, "hits": [h.as_dict() for h in hits]}

    @app.get("/status")
    def status() -> dict:
        return pending_changes(settings)

    return app


app = create_app()
