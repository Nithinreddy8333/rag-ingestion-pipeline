# RAG Ingestion Pipeline

The data-engineering half of retrieval-augmented generation: a pipeline that keeps a vector
index **in step with a changing set of documents, doing only the work that changed**, and an
eval suite that measures whether retrieval actually finds the right passage.

```
docs folder ──> change detection ──> chunking ──> quality gates ──> embed (cached) ──> Qdrant
   (md, txt)     content hashes      by heading    PII, junk,        only new text     dense +
                 in DuckDB           or fixed      duplicates                          sparse
                                                                                          │
                              retrieval evals  <──  dense / keyword / hybrid search  <────┘
```

It runs on a laptop with no API key, no model download and no server: an embedded Qdrant
and an offline embedder are the defaults. One environment variable switches to a Qdrant
server, OpenAI embeddings or a local sentence-transformers model.

## Why this exists

Most RAG demos index a folder once and stop. In production the documents keep changing,
and that is where the cost and the bugs are:

| What goes wrong | What this pipeline does |
|---|---|
| Re-embedding everything on every run is slow and costs money | Documents are skipped by content hash; inside a changed document, unchanged chunks reuse their cached embedding |
| An edited or deleted document leaves old chunks behind, and search returns stale answers | Each run removes the chunk ids a document no longer has |
| A crash halfway leaves the index and the bookkeeping out of sync | State is committed per document only after the vector store accepted it; re-running repairs it |
| Someone changes the embedding model or chunk size and mixes incompatible vectors | The index configuration is fingerprinted; a mismatch is refused until `--rebuild` |
| Emails and phone numbers get shipped to an embedding API | PII is redacted before embedding |
| "Retrieval seems fine" | Gold questions with known answers; recall and MRR per chunking strategy and search mode, gated in CI |

## Quick start

```bash
git clone https://github.com/Nithinreddy8333/rag-ingestion-pipeline
cd rag-ingestion-pipeline
python -m venv .venv && source .venv/bin/activate
make install
make demo
```

`make demo` writes a sample handbook (24 service runbooks, 8 policies), ingests it, runs
again to show a no-op, simulates a week of edits, and ingests incrementally. Real output:

```
first run     32 new                                   144 embeddings computed
second run    32 unchanged                               0 computed
(4 documents edited, 2 deleted, 2 added)
third run     2 new, 4 changed, 26 unchanged, 2 deleted   14 computed, 16 reused from cache
              30 chunks upserted, 14 stale chunks removed, index still 144 chunks
```

The four edited runbooks have five sections each and one sentence changed in each, so only
4 of their 20 chunks were re-embedded.

Other entry points:

```bash
rag-ingest search "what to do when the checkpoint store fills up" -k 3 --mode hybrid
rag-ingest status --fail-if-stale     # what would the next run change? (freshness check)
make serve                            # search API with docs at http://localhost:8000/docs
make evals                            # retrieval quality and incremental efficiency
make test                             # 28 tests
make dagster                          # scheduled refresh with a freshness check
```

Use real embeddings or a Qdrant server:

```bash
pip install -e ".[openai]"
export EMBED_PROVIDER=openai EMBED_MODEL=<embedding model> OPENAI_API_KEY=...
export QDRANT_URL=http://localhost:6333      # optional; docker compose up qdrant
rag-ingest ingest --rebuild                  # required: the embedding model changed
```

## How it works

**Change detection** (`pipeline.py`, `state.py`). Every document's content hash is stored in
DuckDB. A run compares the folder with that state and sorts documents into new, changed,
unchanged and deleted. Hashes are used rather than modification times because timestamps
change on checkout, copy and sync without the content changing.

**Chunking** (`chunking.py`). The default splits on Markdown headings, keeps paragraphs
whole where it can, splits long sections by sentence with a word overlap, and prefixes each
chunk with its path (`orders-cdc runbook > Contacts`) so a chunk still makes sense alone.
A naive fixed-window chunker is included as a comparison baseline.

**Stable chunk ids.** A chunk's id is a hash of its document id and content, not of its
position. An untouched section keeps its id, and its cached vector, when text around it
changes. This is what makes the incremental run above cheap.

**Quality gates** (`quality.py`). Chunks that are too short, mostly symbols, or duplicates
within a document are rejected and recorded with a reason. Emails and phone numbers are
replaced with placeholders before embedding.

**Embedding cache** (`state.py`). Vectors are cached by (text hash, model). Identical text in
two documents is embedded once, and a `--rebuild` with the same model computes nothing.

**Load** (`store.py`). Each chunk is stored in Qdrant with a dense vector and a sparse
keyword vector (BM25-style term weights, with IDF applied by Qdrant). For each document the
order is: upsert new chunks, delete stale chunks, commit state. Upserts are idempotent, so
repeating a half-finished document is harmless.

**Search.** Dense, keyword, or hybrid (both result lists fused with reciprocal rank fusion),
with an optional metadata filter. Exposed through the CLI and a small FastAPI service.

**Orchestration** (`orchestration/definitions.py`). A Dagster asset runs the ingest hourly,
with an asset check that fails if the index is behind the documents or its size disagrees
with the state store.

## Evals

`evals/gold/v1/` holds the handbook and 88 questions. Each question is generated from a fact
in one specific section and is labelled with that document and section. Questions are worded
differently from the documents on purpose (the runbook says "Restart procedure"; the question
asks how to "safely bring it back up").

Results with the **offline hashing embedder** (`make evals`):

| chunking | mode | chunks | doc@1 | sec@1 | sec@5 | mrr@10 | tokens@1 |
|---|---|---|---|---|---|---|---|
| heading-aware (180) | dense | 144 | 0.966 | 0.466 | 0.886 | 0.615 | 25.4 |
| heading-aware (180) | sparse | 144 | 0.955 | 0.432 | 0.898 | 0.604 | 25.4 |
| heading-aware (180) | hybrid | 144 | 0.955 | 0.466 | 0.920 | 0.622 | 25.1 |
| fixed window (60) | dense | 112 | 0.841 | 0.545 | 0.727 | 0.632 | 57.5 |
| fixed window (60) | sparse | 112 | 0.875 | 0.534 | 0.864 | 0.659 | 57.6 |
| fixed window (60) | hybrid | 112 | 0.886 | 0.568 | 0.864 | 0.681 | 57.1 |
| fixed window (180) | dense | 39 | 0.920 | 0.920 | 0.977 | 0.939 | 162.8 |
| fixed window (180) | sparse | 39 | 0.955 | 0.955 | 0.966 | 0.958 | 158.9 |
| fixed window (180) | hybrid | 39 | 0.943 | 0.943 | 0.977 | 0.960 | 159.0 |

- `doc@1`: the top result is from the right document.
- `sec@1`, `sec@5`: a chunk containing the answering section is ranked first, or in the top five.
- `mrr@10`: mean reciprocal rank of the first such chunk.
- `tokens@1`: average size of the top chunk, a proxy for what it costs to send to an LLM.

| incremental ingest | value |
|---|---|
| embeddings on first run | 144 |
| embeddings on a repeat run with no changes | 0 |
| embeddings after 4 edits, 2 deletes, 2 adds | 14 |
| embeddings a full re-index would need | 144 |
| embedding work saved | 90.3% |

### What these numbers do and do not show

- **Finding the document is easy; finding the section is not.** With heading-aware chunks the
  right document is first about 96% of the time, but the right section is first under half
  the time. Sections of one runbook all mention the same service, and the offline embedder
  only measures word overlap, so it cannot tell that "bring it back up" means "Restart
  procedure". That is the gap a real embedding model or a reranker is for, and this eval is
  how to measure whether one closes it.
- **On this corpus, big chunks win on accuracy.** The 180-word fixed window scores highest
  because the documents are short: one chunk is nearly a whole runbook, so the answer is
  almost always inside it. It pays for that with chunks about six times larger. Top-five
  heading-aware chunks reach 92% at roughly 125 words of context, against 92 to 96% for one
  160-word chunk. This is a fair result, not a win for the default: structure-aware chunking
  should matter more on long documents, and this corpus does not test that.
- **Hybrid helps a little.** It has the best or joint-best `sec@5` and `mrr@10` in every
  chunking group, by small margins.
- **Chunk boundaries matter.** The 60-word window, which cuts through sections, has the
  worst document accuracy.

`evals/thresholds.yaml` sets minimums just under these baseline numbers, plus a floor on
embedding work saved. CI fails if a change makes them worse.

### Limits

- **No semantic model was measured.** The OpenAI and sentence-transformers adapters are
  implemented but were not run while building this (no key, no model download), so every
  number above is for a word-overlap baseline.
- **The corpus is synthetic and small** (32 short documents rendered from templates). It
  gives exact labels, but it is not evidence about real document collections.
- **Token counts are word counts**, not model tokens.
- **The Qdrant server path and the Docker files are untested here.** All runs used the
  embedded Qdrant. The embedded mode allows one process at a time, so stop the API while
  ingesting or use a server.
- **Sources are local Markdown and text files.** PDFs, HTML, and connectors to wikis or
  object stores are not implemented.
- **PII redaction is two regular expressions** (emails, phone numbers), not a full scanner.

## Project layout

```
src/rag_ingest/
  pipeline.py    the ingest run: diff, chunk, gate, embed, load, commit
  chunking.py    document reading, heading-aware and fixed chunkers, stable chunk ids
  quality.py     quality gates and PII redaction
  embeddings.py  hashing / OpenAI / sentence-transformers embedders, sparse vectors
  state.py       DuckDB state: documents, chunks, embedding cache, rejections, runs
  store.py       Qdrant collection, upserts, deletes, dense / sparse / hybrid search
  api.py         FastAPI search service
  corpus.py      sample handbook, gold questions, simulated edits
  cli.py         rag-ingest command
evals/           gold documents and questions, scorer, thresholds, results
orchestration/   Dagster asset, freshness check, hourly schedule
tests/           28 tests: chunking, gates, incremental behaviour, crash recovery, search, API
```

## What I would do next

- Run the evals with a real embedding model and a reranker, and publish the comparison.
- Add a long-document gold set, where chunking strategy should matter more.
- Change data capture from a real source (object store events or a wiki API) instead of
  scanning a folder.
- Batch and retry embedding calls with backoff, and record cost per run.
- Per-document access control carried into the index and enforced at query time.

## License

MIT
