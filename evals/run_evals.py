"""Measure retrieval quality and incremental-ingest efficiency on a versioned gold set.

evals/gold/v1/ holds the handbook documents and queries.jsonl, where every query is
labelled with the document and section that answer it.

Part 1, retrieval: for each chunking strategy and each search mode, index the corpus and
run every query.
  doc@1     the top result comes from the right document
  sec@1/@5  a chunk containing the answering section is ranked first / in the top five
  mrr@10    mean reciprocal rank of the first chunk containing the answering section
  tokens@1  average size of the top chunk (what you would pay to send it to an LLM)

Part 2, incremental: ingest, apply a batch of edits/deletes/adds, ingest again, and report
how many embeddings had to be computed compared with re-embedding everything.

Usage:
  python evals/run_evals.py                 # run and enforce evals/thresholds.yaml
  python evals/run_evals.py --no-gate
  python evals/run_evals.py --regenerate-gold
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml
from qdrant_client import QdrantClient

from rag_ingest import corpus
from rag_ingest.chunking import HEADING
from rag_ingest.config import Settings
from rag_ingest.embeddings import STOPWORDS, get_embedder, tokenize
from rag_ingest.pipeline import run_ingest
from rag_ingest.quality import redact
from rag_ingest.store import MODES, VectorStore

HERE = Path(__file__).parent
GOLD = HERE / "gold" / "v1"
CONFIGS = [
    {"name": "heading-aware (180)", "chunker": "heading", "max_tokens": 180, "overlap_tokens": 30},
    {"name": "fixed window (60)", "chunker": "fixed", "max_tokens": 60, "overlap_tokens": 10},
    {"name": "fixed window (180)", "chunker": "fixed", "max_tokens": 180, "overlap_tokens": 30},
]


def section_tokens(doc_text: str, heading: str) -> set[str]:
    """Content words of the section under `heading`."""
    lines, inside = [], False
    for line in doc_text.splitlines():
        match = HEADING.match(line)
        if match:
            inside = match.group(2) == heading
        elif inside:
            lines.append(line)
    text, _ = redact(" ".join(lines))
    return {t for t in tokenize(text) if t not in STOPWORDS}


def contains_section(hit, query: dict, gold_tokens: set[str]) -> bool:
    if hit.doc_id != query["doc_id"] or not gold_tokens:
        return False
    chunk_tokens = set(tokenize(hit.text))
    return len(gold_tokens & chunk_tokens) / len(gold_tokens) >= 0.8


def make_settings(tmp: Path, docs_dir: Path, config: dict) -> Settings:
    settings = Settings()
    settings.docs_dir = docs_dir
    settings.state_path = tmp / "state.duckdb"
    settings.chunker = config["chunker"]
    settings.max_tokens = config["max_tokens"]
    settings.overlap_tokens = config["overlap_tokens"]
    return settings


def eval_retrieval(embedder) -> list[dict]:
    queries = [json.loads(line) for line in (GOLD / "queries.jsonl").read_text().splitlines()]
    docs = {q["doc_id"]: (GOLD / "docs" / q["doc_id"]).read_text() for q in queries}
    gold = {q["id"]: section_tokens(docs[q["doc_id"]], q["heading"]) for q in queries}
    rows = []
    for config in CONFIGS:
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp), GOLD / "docs", config)
            store = VectorStore(settings, embedder.dim, client=QdrantClient(":memory:"))
            stats = run_ingest(settings, embedder=embedder, store=store)
            for mode in MODES:
                doc1 = sec1 = sec5 = 0
                rr = tokens = 0.0
                for q in queries:
                    hits = store.search(q["query"], embedder, mode=mode, k=10)
                    relevant = [contains_section(h, q, gold[q["id"]]) for h in hits]
                    doc1 += bool(hits) and hits[0].doc_id == q["doc_id"]
                    sec1 += bool(relevant[:1]) and relevant[0]
                    sec5 += any(relevant[:5])
                    rr += next((1 / (i + 1) for i, ok in enumerate(relevant) if ok), 0.0)
                    tokens += len(hits[0].text.split()) if hits else 0
                n = len(queries)
                rows.append({
                    "chunking": config["name"], "mode": mode, "chunks": stats["points_in_store"],
                    "doc@1": round(doc1 / n, 3), "sec@1": round(sec1 / n, 3), "sec@5": round(sec5 / n, 3),
                    "mrr@10": round(rr / n, 3), "tokens@1": round(tokens / n, 1),
                })
            store.close()
    return rows


def eval_incremental(embedder) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        docs_dir = Path(tmp) / "docs"
        shutil.copytree(GOLD / "docs", docs_dir)
        settings = make_settings(Path(tmp), docs_dir, CONFIGS[0])
        store = VectorStore(settings, embedder.dim, client=QdrantClient(":memory:"))
        first = run_ingest(settings, embedder=embedder, store=store)
        repeat = run_ingest(settings, embedder=embedder, store=store)
        changes = corpus.mutate(docs_dir, seed=1)
        second = run_ingest(settings, embedder=embedder, store=store)
        store.close()
    full = second["points_in_store"]
    return {
        "first_run_embeddings": first["embeddings_computed"],
        "repeat_run_embeddings": repeat["embeddings_computed"],
        "docs_edited": len(changes["edited"]), "docs_deleted": len(changes["deleted"]),
        "docs_added": len(changes["added"]),
        "incremental_embeddings": second["embeddings_computed"],
        "full_reindex_embeddings": full,
        "embedding_work_saved": round(1 - second["embeddings_computed"] / full, 3),
        "chunks_removed": second["chunks_removed"],
    }


def render(report: dict) -> str:
    head = ["chunking", "mode", "chunks", "doc@1", "sec@1", "sec@5", "mrr@10", "tokens@1"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in report["retrieval"]:
        lines.append("| " + " | ".join(str(r[h]) for h in head) + " |")
    inc = report["incremental"]
    lines += ["", "| incremental ingest | value |", "|---|---|"]
    lines += [f"| {k.replace('_', ' ')} | {v} |" for k, v in inc.items()]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--regenerate-gold", action="store_true")
    parser.add_argument("--no-gate", action="store_true")
    args = parser.parse_args()
    if args.regenerate_gold:
        shutil.rmtree(GOLD, ignore_errors=True)
        corpus.write(corpus.generate(seed=7), GOLD / "docs", GOLD / "queries.jsonl")
        print(f"wrote {GOLD}")
        return 0

    settings = Settings()
    embedder = get_embedder(settings.embed_provider, settings.embed_model)
    report = {
        "gold_version": "v1", "embedder": embedder.name,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "queries": sum(1 for _ in (GOLD / "queries.jsonl").open()),
        "retrieval": eval_retrieval(embedder), "incremental": eval_incremental(embedder),
    }
    out = HERE / "results"
    out.mkdir(exist_ok=True)
    stem = embedder.name.replace("/", "_")
    (out / f"{stem}.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / f"{stem}.md").write_text(render(report))
    print(render(report))
    if args.no_gate:
        return 0

    thresholds = yaml.safe_load((HERE / "thresholds.yaml").read_text())
    failures = []
    for rule in thresholds["retrieval_minimums"]:
        row = next(r for r in report["retrieval"]
                   if r["chunking"] == rule["chunking"] and r["mode"] == rule["mode"])
        for metric, minimum in rule["metrics"].items():
            if row[metric] < minimum:
                failures.append(f"{rule['chunking']} / {rule['mode']} {metric}: {row[metric]} < {minimum}")
    inc = report["incremental"]
    if inc["repeat_run_embeddings"] != 0:
        failures.append("a repeat run with no changes computed embeddings")
    if inc["embedding_work_saved"] < thresholds["incremental"]["min_embedding_work_saved"]:
        failures.append(f"embedding work saved {inc['embedding_work_saved']} is below the minimum")
    if failures:
        print("REGRESSION:\n  " + "\n  ".join(failures))
        return 1
    print("All metrics meet their thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
