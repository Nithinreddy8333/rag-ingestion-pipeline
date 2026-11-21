"""Quality gates that run between chunking and embedding.

Bad chunks cost money to embed and then pollute search results for as long as they stay
indexed, so they are stopped here and recorded with a reason. PII is redacted before the
text leaves the pipeline (an embedding API call is a data export).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .chunking import Chunk, n_tokens, sha

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]\d{3,4}[\s.-]\d{3,4}(?!\w)")


@dataclass
class GateResult:
    accepted: list[Chunk]
    rejected: list[tuple[Chunk, str]]
    redactions: int


def redact(text: str) -> tuple[str, int]:
    text, emails = EMAIL.subn("[EMAIL]", text)
    text, phones = PHONE.subn("[PHONE]", text)
    return text, emails + phones


def _symbol_ratio(text: str) -> float:
    visible = [c for c in text if not c.isspace()]
    if not visible:
        return 1.0
    return sum(not c.isalnum() for c in visible) / len(visible)


def apply_gates(chunks: list[Chunk], min_tokens: int, max_tokens: int, redact_pii: bool) -> GateResult:
    accepted: list[Chunk] = []
    rejected: list[tuple[Chunk, str]] = []
    seen: set[str] = set()
    redactions = 0
    for chunk in chunks:
        if redact_pii:
            text, n_text = redact(chunk.text)
            embed_text, _ = redact(chunk.embed_text)
            if n_text:
                redactions += n_text
                # Redaction changes the content, so the id (and cache key) must change too.
                chunk = replace(chunk, text=text, embed_text=embed_text, n_tokens=n_tokens(text),
                                chunk_id=sha(f"{chunk.doc_id}\x1f{embed_text}", 24))
        normalized = sha(" ".join(chunk.text.lower().split()))
        if chunk.n_tokens < min_tokens:
            rejected.append((chunk, "too_short"))
        elif chunk.n_tokens > max_tokens * 2:
            rejected.append((chunk, "too_long"))
        elif _symbol_ratio(chunk.text) > 0.5:
            rejected.append((chunk, "mostly_symbols"))
        elif normalized in seen:
            rejected.append((chunk, "duplicate_in_document"))
        else:
            seen.add(normalized)
            accepted.append(chunk)
    return GateResult(accepted, rejected, redactions)
