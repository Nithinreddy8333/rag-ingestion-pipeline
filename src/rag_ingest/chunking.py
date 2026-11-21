"""Read documents and split them into chunks.

Two strategies, so their effect on retrieval can be measured (see evals/):

  heading  structure-aware: split on Markdown headings, keep paragraphs whole where
           possible, and prefix every chunk with "Title > Section" so it still makes
           sense when retrieved on its own
  fixed    naive baseline: sliding window of N words with overlap, no structure

Token counts are approximated by whitespace-separated words. That is a simplification:
swap in the tokenizer of your embedding model if you need exact budgets.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Document:
    doc_id: str  # path relative to the docs folder, with forward slashes
    title: str
    text: str
    content_hash: str
    source_mtime: float


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    doc_id: str
    ordinal: int
    heading_path: str  # "Title > Section > Subsection"
    heading: str  # innermost heading, used for section-level evaluation
    text: str  # what is stored and shown
    embed_text: str  # what is embedded (text plus context header)
    n_tokens: int


def sha(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def n_tokens(text: str) -> int:
    return len(text.split())


def read_documents(docs_dir: Path) -> list[Document]:
    docs = []
    for path in sorted(docs_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".md", ".txt"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        first_heading = next((m.group(2) for line in text.splitlines() if (m := HEADING.match(line))), None)
        docs.append(Document(
            doc_id=path.relative_to(docs_dir).as_posix(),
            title=first_heading or path.stem,
            text=text,
            content_hash=sha(text, 32),
            source_mtime=path.stat().st_mtime,
        ))
    return docs


def _sections(doc: Document) -> list[tuple[list[str], str]]:
    """Split Markdown into (heading path, body) pairs."""
    path: list[str] = []
    body: list[str] = []
    out: list[tuple[list[str], str]] = []

    def flush() -> None:
        text = "\n".join(body).strip()
        if text:
            out.append((list(path), text))
        body.clear()

    in_code = False
    for line in doc.text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        match = None if in_code else HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            del path[level - 1:]
            while len(path) < level - 1:
                path.append("")
            path.append(match.group(2))
        else:
            body.append(line)
    flush()
    return out


def _pack(units: list[str], max_tokens: int, overlap_tokens: int) -> list[str]:
    """Greedily pack text units into windows of at most max_tokens, with a word overlap."""
    windows: list[str] = []
    current: list[str] = []
    size = 0
    for unit in units:
        unit_size = n_tokens(unit)
        if current and size + unit_size > max_tokens:
            windows.append(" ".join(current))
            tail = " ".join(current).split()[-overlap_tokens:] if overlap_tokens else []
            current, size = ([" ".join(tail)] if tail else []), len(tail)
        current.append(unit)
        size += unit_size
    if current:
        windows.append(" ".join(current))
    return windows


def _split_long(text: str, max_tokens: int) -> list[str]:
    """Break a paragraph into sentences, and an oversized sentence into word windows."""
    units: list[str] = []
    for sentence in SENTENCE_END.split(text):
        words = sentence.split()
        if len(words) <= max_tokens:
            units.append(sentence)
        else:
            units += [" ".join(words[i:i + max_tokens]) for i in range(0, len(words), max_tokens)]
    return units


def chunk_by_heading(doc: Document, max_tokens: int = 180, overlap_tokens: int = 30) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path, body in _sections(doc):
        names = [p for p in path if p]
        heading_path = " > ".join(names) if names else doc.title
        if names and names[0] != doc.title:
            heading_path = f"{doc.title} > {heading_path}"
        units: list[str] = []
        for paragraph in re.split(r"\n\s*\n", body):
            paragraph = " ".join(paragraph.split())
            if not paragraph:
                continue
            units += [paragraph] if n_tokens(paragraph) <= max_tokens else _split_long(paragraph, max_tokens)
        for window in _pack(units, max_tokens, overlap_tokens):
            chunks.append(_make(doc, len(chunks), heading_path, names[-1] if names else doc.title,
                                window, f"{heading_path}\n\n{window}"))
    return chunks


def chunk_fixed(doc: Document, max_tokens: int = 180, overlap_tokens: int = 30) -> list[Chunk]:
    words = doc.text.split()
    step = max(1, max_tokens - overlap_tokens)
    chunks: list[Chunk] = []
    for start in range(0, len(words), step):
        window = " ".join(words[start:start + max_tokens])
        chunks.append(_make(doc, len(chunks), doc.title, "", window, window))
        if start + max_tokens >= len(words):
            break
    return chunks


def _make(doc: Document, ordinal: int, heading_path: str, heading: str, text: str, embed_text: str) -> Chunk:
    # The id depends only on the document and the chunk's content, not on its position, so
    # an unchanged section keeps its id (and its cached embedding) when text around it moves.
    return Chunk(
        chunk_id=sha(f"{doc.doc_id}\x1f{embed_text}", 24),
        doc_id=doc.doc_id, ordinal=ordinal, heading_path=heading_path, heading=heading,
        text=text, embed_text=embed_text, n_tokens=n_tokens(text),
    )


CHUNKERS = {"heading": chunk_by_heading, "fixed": chunk_fixed}


def chunk_document(doc: Document, strategy: str, max_tokens: int, overlap_tokens: int) -> list[Chunk]:
    if strategy not in CHUNKERS:
        raise ValueError(f"Unknown chunker '{strategy}'. Use one of {sorted(CHUNKERS)}.")
    return CHUNKERS[strategy](doc, max_tokens, overlap_tokens)
