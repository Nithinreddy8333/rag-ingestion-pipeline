"""Embedding providers behind one interface, plus the sparse (keyword) vectors.

  hashing   offline, deterministic feature hashing. No model download, no API key. It
            captures word and character overlap, not meaning: a baseline that makes the
            pipeline runnable and testable anywhere, not a substitute for a real model.
  openai    OpenAI embeddings API                  (pip install '.[openai]', EMBED_MODEL)
  local     a sentence-transformers model on disk  (pip install '.[local-models]', EMBED_MODEL)
"""

from __future__ import annotations

import math
import re
import zlib
from collections import Counter
from typing import Protocol

import numpy as np

WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by do does for from how i if in is it its of on or so that the "
    "this to was what when where which who with".split()
)


def tokenize(text: str) -> list[str]:
    return WORD.findall(text.lower())


def _bucket(feature: str, dim: int) -> tuple[int, float]:
    h = zlib.crc32(feature.encode("utf-8"))
    return h % dim, 1.0 if (h >> 31) & 1 else -1.0


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


class HashingEmbedder:
    def __init__(self, dim: int = 512):
        self.dim = dim
        self.name = f"hashing-{dim}"

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = [t for t in tokenize(text) if t not in STOPWORDS]
            features = Counter(tokens)
            features.update(f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False))
            for token in tokens:  # character trigrams give some tolerance to word forms
                padded = f"<{token}>"
                features.update(f"#{padded[i:i + 3]}" for i in range(len(padded) - 2))
            for feature, count in features.items():
                index, sign = _bucket(feature, self.dim)
                out[row, index] += sign * (1.0 + math.log(count))
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


class OpenAIEmbedder:
    def __init__(self, model: str | None):
        import openai  # optional dependency

        if not model:
            raise ValueError("Set EMBED_MODEL to an OpenAI embedding model name")
        self._client = openai.OpenAI()
        self.name = f"openai-{model}"
        self._model = model
        self.dim = len(self._client.embeddings.create(model=model, input=["dimension probe"]).data[0].embedding)

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), 128):
            reply = self._client.embeddings.create(model=self._model, input=texts[start:start + 128])
            vectors += [item.embedding for item in reply.data]
        return np.asarray(vectors, dtype=np.float32)


class LocalModelEmbedder:
    def __init__(self, model: str | None):
        from sentence_transformers import SentenceTransformer  # optional dependency

        if not model:
            raise ValueError("Set EMBED_MODEL to a sentence-transformers model name or path")
        self._model = SentenceTransformer(model)
        self.name = f"local-{model}"
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(texts, normalize_embeddings=True), dtype=np.float32)


def get_embedder(provider: str, model: str | None = None) -> Embedder:
    provider = provider.lower()
    if provider == "hashing":
        return HashingEmbedder(int(model) if model else 512)
    if provider == "openai":
        return OpenAIEmbedder(model)
    if provider == "local":
        return LocalModelEmbedder(model)
    raise ValueError(f"Unknown EMBED_PROVIDER '{provider}'. Use hashing, openai or local.")


def sparse_vector(text: str, is_query: bool = False, k1: float = 1.2, b: float = 0.75,
                  avg_len: float = 60.0) -> tuple[list[int], list[float]]:
    """BM25-style term weights as a sparse vector. The IDF part is applied by the vector
    store (Qdrant's IDF modifier), so only term frequency and length are handled here."""
    tokens = [t for t in tokenize(text) if t not in STOPWORDS]
    counts = Counter(tokens)
    weights: dict[int, float] = {}
    for token, tf in counts.items():
        index = zlib.crc32(token.encode("utf-8"))
        value = 1.0 if is_query else tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(tokens) / avg_len))
        weights[index] = max(weights.get(index, 0.0), value)
    indices = sorted(weights)
    return indices, [weights[i] for i in indices]
