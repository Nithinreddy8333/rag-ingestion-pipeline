"""Runtime settings, read from environment variables with local defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default))


@dataclass
class Settings:
    docs_dir: Path = field(default_factory=lambda: _path("DOCS_DIR", "data/docs"))
    state_path: Path = field(default_factory=lambda: _path("STATE_PATH", "state/ingest.duckdb"))
    # Vector store: a Qdrant server if QDRANT_URL is set, otherwise an on-disk local instance.
    qdrant_url: str | None = field(default_factory=lambda: os.environ.get("QDRANT_URL") or None)
    qdrant_path: Path = field(default_factory=lambda: _path("QDRANT_PATH", "state/qdrant"))
    collection: str = field(default_factory=lambda: os.environ.get("COLLECTION", "docs"))

    embed_provider: str = field(default_factory=lambda: os.environ.get("EMBED_PROVIDER", "hashing"))
    embed_model: str | None = field(default_factory=lambda: os.environ.get("EMBED_MODEL") or None)

    chunker: str = field(default_factory=lambda: os.environ.get("CHUNKER", "heading"))
    max_tokens: int = field(default_factory=lambda: int(os.environ.get("CHUNK_MAX_TOKENS", "180")))
    overlap_tokens: int = field(default_factory=lambda: int(os.environ.get("CHUNK_OVERLAP_TOKENS", "30")))
    min_tokens: int = field(default_factory=lambda: int(os.environ.get("CHUNK_MIN_TOKENS", "5")))
    redact_pii: bool = field(default_factory=lambda: os.environ.get("REDACT_PII", "1") == "1")
