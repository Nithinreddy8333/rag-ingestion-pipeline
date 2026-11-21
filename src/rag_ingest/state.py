"""The pipeline's memory, in DuckDB.

  documents        what was ingested, with the content hash used for change detection
  chunks           which chunk ids each document currently owns in the vector store
  embedding_cache  vectors keyed by (text hash, model): identical text is never embedded twice
  rejected_chunks  chunks stopped by a quality gate, with the reason
  runs             one row per ingest run with its statistics
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import numpy as np

SCHEMA = """
create table if not exists documents (
    doc_id varchar primary key, content_hash varchar, title varchar, n_chunks integer,
    source_mtime double, ingested_at timestamp, run_id varchar
);
create table if not exists chunks (
    chunk_id varchar primary key, doc_id varchar, ordinal integer, heading_path varchar,
    n_tokens integer
);
create table if not exists embedding_cache (
    text_hash varchar, model varchar, vector blob, primary key (text_hash, model)
);
create table if not exists rejected_chunks (
    run_id varchar, doc_id varchar, heading_path varchar, reason varchar, preview varchar
);
create table if not exists runs (
    run_id varchar primary key, started_at timestamp, finished_at timestamp, stats json
);
create table if not exists settings (key varchar primary key, value varchar);
"""


class StateStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute(SCHEMA)

    def close(self) -> None:
        self.con.close()

    # ---- settings: guard against silently mixing incompatible index configurations -----
    def get_setting(self, key: str) -> str | None:
        row = self.con.execute("select value from settings where key = ?", [key]).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.con.execute("insert or replace into settings values (?, ?)", [key, value])

    # ---- documents and chunks -------------------------------------------------------------
    def document_hashes(self) -> dict[str, str]:
        return dict(self.con.execute("select doc_id, content_hash from documents").fetchall())

    def chunk_ids(self, doc_id: str) -> set[str]:
        rows = self.con.execute("select chunk_id from chunks where doc_id = ?", [doc_id]).fetchall()
        return {r[0] for r in rows}

    def save_document(self, doc, chunks: list, run_id: str) -> None:
        """Record a document and its chunk ids atomically."""
        self.con.execute("begin")
        try:
            self.con.execute("delete from chunks where doc_id = ?", [doc.doc_id])
            if chunks:
                self.con.executemany(
                    "insert into chunks values (?, ?, ?, ?, ?)",
                    [(c.chunk_id, c.doc_id, c.ordinal, c.heading_path, c.n_tokens) for c in chunks],
                )
            self.con.execute(
                "insert or replace into documents values (?, ?, ?, ?, ?, ?, ?)",
                [doc.doc_id, doc.content_hash, doc.title, len(chunks), doc.source_mtime,
                 datetime.now(UTC).replace(tzinfo=None), run_id],
            )
            self.con.execute("commit")
        except Exception:
            self.con.execute("rollback")
            raise

    def delete_document(self, doc_id: str) -> None:
        self.con.execute("begin")
        self.con.execute("delete from chunks where doc_id = ?", [doc_id])
        self.con.execute("delete from documents where doc_id = ?", [doc_id])
        self.con.execute("commit")

    def record_rejections(self, run_id: str, rejected: list) -> None:
        if rejected:
            self.con.executemany(
                "insert into rejected_chunks values (?, ?, ?, ?, ?)",
                [(run_id, c.doc_id, c.heading_path, reason, c.text[:80]) for c, reason in rejected],
            )

    # ---- embedding cache ------------------------------------------------------------------
    def cached_vectors(self, text_hashes: list[str], model: str) -> dict[str, np.ndarray]:
        if not text_hashes:
            return {}
        rows = self.con.execute(
            "select text_hash, vector from embedding_cache where model = ? and text_hash in "
            "(select unnest(?))",
            [model, text_hashes],
        ).fetchall()
        return {h: np.frombuffer(blob, dtype=np.float32) for h, blob in rows}

    def cache_vectors(self, vectors: dict[str, np.ndarray], model: str) -> None:
        if vectors:
            self.con.executemany(
                "insert or replace into embedding_cache values (?, ?, ?)",
                [(h, model, v.astype(np.float32).tobytes()) for h, v in vectors.items()],
            )

    # ---- runs and reporting ---------------------------------------------------------------
    def record_run(self, run_id: str, started_at: datetime, stats: dict) -> None:
        self.con.execute(
            "insert or replace into runs values (?, ?, ?, ?)",
            [run_id, started_at.replace(tzinfo=None), datetime.now(UTC).replace(tzinfo=None),
             json.dumps(stats)],
        )

    def summary(self) -> dict:
        docs, chunks = self.con.execute(
            "select (select count(*) from documents), (select count(*) from chunks)"
        ).fetchone()
        cache = self.con.execute("select count(*) from embedding_cache").fetchone()[0]
        last = self.con.execute(
            "select run_id, finished_at, stats from runs order by finished_at desc limit 1"
        ).fetchone()
        return {
            "documents": docs,
            "chunks": chunks,
            "cached_embeddings": cache,
            "last_run": {"run_id": last[0], "finished_at": str(last[1]), **json.loads(last[2])}
            if last else None,
        }

    def ingested_mtimes(self) -> dict[str, float]:
        return dict(self.con.execute("select doc_id, source_mtime from documents").fetchall())
