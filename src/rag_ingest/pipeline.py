"""The ingest run: detect what changed, and do only that work.

    read docs -> diff against state -> chunk changed docs -> quality gates
              -> embed only texts not in the cache -> upsert -> delete stale chunks -> commit

Properties this is built to have (each is covered by a test):

  incremental   unchanged documents are skipped by content hash, not by timestamp
  minimal       inside a changed document, unchanged chunks reuse their cached embedding
  idempotent    running twice in a row changes nothing the second time
  consistent    deletes and edits remove their old chunks, so search never returns stale text
  restartable   state is committed per document after the vector store accepted it; a crash
                mid-run leaves at most one document to redo, and redoing it is harmless
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from .chunking import Chunk, chunk_document, read_documents, sha
from .config import Settings
from .embeddings import Embedder, get_embedder
from .quality import apply_gates
from .state import StateStore
from .store import VectorStore


class IndexConfigChanged(RuntimeError):
    pass


def index_signature(settings: Settings, embedder: Embedder) -> str:
    return (f"{embedder.name}|{settings.chunker}|{settings.max_tokens}|{settings.overlap_tokens}"
            f"|pii={int(settings.redact_pii)}")


def run_ingest(settings: Settings, embedder: Embedder | None = None, rebuild: bool = False,
               store: VectorStore | None = None) -> dict:
    started = datetime.now(UTC)
    clock = time.perf_counter()
    run_id = uuid.uuid4().hex[:10]
    embedder = embedder or get_embedder(settings.embed_provider, settings.embed_model)
    state = StateStore(settings.state_path)
    own_store = store is None
    store = store or VectorStore(settings, embedder.dim)
    try:
        signature = index_signature(settings, embedder)
        previous = state.get_setting("index_signature")
        if previous and previous != signature and not rebuild:
            raise IndexConfigChanged(
                f"The index was built with [{previous}] but the current settings are [{signature}]. "
                "Mixing them would corrupt search results. Re-run with --rebuild."
            )
        if rebuild:
            for doc_id in list(state.document_hashes()):
                state.delete_document(doc_id)
        store.ensure_collection(recreate=rebuild)
        state.set_setting("index_signature", signature)

        documents = read_documents(settings.docs_dir)
        known = state.document_hashes()
        current = {d.doc_id: d for d in documents}
        new = [d for d in documents if d.doc_id not in known]
        changed = [d for d in documents if d.doc_id in known and known[d.doc_id] != d.content_hash]
        deleted = [doc_id for doc_id in known if doc_id not in current]

        # Phase 1: chunk and gate every new or changed document.
        prepared: list[tuple] = []
        rejected_total = redactions = 0
        reasons: dict[str, int] = {}
        for doc in new + changed:
            chunks = chunk_document(doc, settings.chunker, settings.max_tokens, settings.overlap_tokens)
            gate = apply_gates(chunks, settings.min_tokens, settings.max_tokens, settings.redact_pii)
            state.record_rejections(run_id, gate.rejected)
            rejected_total += len(gate.rejected)
            redactions += gate.redactions
            for _, reason in gate.rejected:
                reasons[reason] = reasons.get(reason, 0) + 1
            prepared.append((doc, gate.accepted))

        # Phase 2: embed each distinct text at most once, and only if it is not cached.
        text_by_hash: dict[str, str] = {}
        for _, chunks in prepared:
            for chunk in chunks:
                text_by_hash.setdefault(sha(chunk.embed_text, 32), chunk.embed_text)
        vectors = state.cached_vectors(list(text_by_hash), embedder.name)
        cache_hits = len(vectors)
        missing = [h for h in text_by_hash if h not in vectors]
        if missing:
            fresh = embedder.embed([text_by_hash[h] for h in missing])
            if fresh.shape != (len(missing), embedder.dim) or not _finite(fresh):
                raise RuntimeError("Embedder returned vectors of the wrong shape or with NaN/inf values")
            new_vectors = dict(zip(missing, fresh, strict=True))
            state.cache_vectors(new_vectors, embedder.name)
            vectors.update(new_vectors)

        # Phase 3: load per document. Upsert first, then remove stale chunks, then commit state.
        upserted = removed = 0
        for doc, chunks in prepared:
            old_ids = state.chunk_ids(doc.doc_id)
            meta = {"title": doc.title, "category": doc.doc_id.split("/")[0] if "/" in doc.doc_id else "",
                    "doc_hash": doc.content_hash, "ingested_at": started.isoformat(timespec="seconds")}
            store.upsert(chunks, [vectors[sha(c.embed_text, 32)] for c in chunks], meta)
            stale = old_ids - {c.chunk_id for c in chunks}
            store.delete(stale)
            state.save_document(doc, chunks, run_id)
            upserted += len(chunks)
            removed += len(stale)
        for doc_id in deleted:
            stale = state.chunk_ids(doc_id)
            store.delete(stale)
            state.delete_document(doc_id)
            removed += len(stale)

        stats = {
            "run_id": run_id,
            "docs_seen": len(documents),
            "docs_new": len(new),
            "docs_changed": len(changed),
            "docs_unchanged": len(documents) - len(new) - len(changed),
            "docs_deleted": len(deleted),
            "chunks_upserted": upserted,
            "chunks_removed": removed,
            "chunks_rejected": rejected_total,
            "rejection_reasons": reasons,
            "pii_redactions": redactions,
            "embeddings_computed": len(missing),
            "embeddings_from_cache": cache_hits,
            "points_in_store": store.count(),
            "embedder": embedder.name,
            "seconds": round(time.perf_counter() - clock, 3),
        }
        state.record_run(run_id, started, stats)
        return stats
    finally:
        state.close()
        if own_store:
            store.close()


def _finite(array) -> bool:
    import numpy as np

    return bool(np.isfinite(array).all())


def pending_changes(settings: Settings) -> dict:
    """What an ingest run would do right now, without doing it (freshness check)."""
    state = StateStore(settings.state_path)
    try:
        known = state.document_hashes()
        summary = state.summary()
    finally:
        state.close()
    documents = read_documents(settings.docs_dir)
    current = {d.doc_id: d.content_hash for d in documents}
    stale = sorted(d for d, h in current.items() if d in known and known[d] != h)
    new = sorted(d for d in current if d not in known)
    deleted = sorted(d for d in known if d not in current)
    return {**summary, "pending": {"new": new, "changed": stale, "deleted": deleted},
            "fresh": not (stale or new or deleted)}


__all__ = ["Chunk", "IndexConfigChanged", "index_signature", "pending_changes", "run_ingest"]
