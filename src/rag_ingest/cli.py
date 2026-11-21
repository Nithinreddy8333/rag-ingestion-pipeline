"""Command line interface: `rag-ingest --help`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import corpus
from .config import Settings
from .embeddings import get_embedder
from .pipeline import IndexConfigChanged, pending_changes, run_ingest
from .store import VectorStore

app = typer.Typer(add_completion=False, help="Incremental document ingestion and search for RAG.")
console = Console()


@app.command("generate-corpus")
def generate_corpus(out: Path = typer.Option(None, help="Docs folder (default: DOCS_DIR)"),
                    seed: int = 7) -> None:
    """Write the sample handbook (24 runbooks, 8 policies) as Markdown."""
    out = out or Settings().docs_dir
    data = corpus.generate(seed)
    corpus.write(data, out)
    console.print(f"Wrote {len(data['docs'])} documents to {out}")


@app.command("simulate-changes")
def simulate_changes(seed: int = 1) -> None:
    """Edit, delete and add a few documents, to try incremental ingestion."""
    changes = corpus.mutate(Settings().docs_dir, seed)
    for kind, paths in changes.items():
        for path in paths:
            console.print(f"{kind:8} {path}")


@app.command()
def ingest(rebuild: bool = typer.Option(False, help="Drop the index and re-ingest everything")) -> None:
    """Bring the index in line with the docs folder, doing only the work that is needed."""
    try:
        stats = run_ingest(Settings(), rebuild=rebuild)
    except IndexConfigChanged as err:
        console.print(f"[red]{err}[/red]")
        raise typer.Exit(code=2) from err
    table = Table(show_header=False, title=f"Ingest run {stats['run_id']} ({stats['embedder']})")
    rows = [
        ("documents", f"{stats['docs_new']} new, {stats['docs_changed']} changed, "
                      f"{stats['docs_unchanged']} unchanged, {stats['docs_deleted']} deleted"),
        ("chunks", f"{stats['chunks_upserted']} upserted, {stats['chunks_removed']} removed, "
                   f"{stats['chunks_rejected']} rejected {stats['rejection_reasons'] or ''}"),
        ("embeddings", f"{stats['embeddings_computed']} computed, "
                       f"{stats['embeddings_from_cache']} reused from cache"),
        ("PII redactions", str(stats["pii_redactions"])),
        ("index size", f"{stats['points_in_store']} chunks"),
        ("time", f"{stats['seconds']} s"),
    ]
    for row in rows:
        table.add_row(*row)
    console.print(table)


@app.command()
def search(query: str, mode: str = "hybrid", k: int = typer.Option(5, "-k", "--top-k"),
           category: str = typer.Option(None)) -> None:
    """Search the index. Modes: dense, sparse, hybrid."""
    settings = Settings()
    embedder = get_embedder(settings.embed_provider, settings.embed_model)
    store = VectorStore(settings, embedder.dim)
    try:
        hits = store.search(query, embedder, mode=mode, k=k, category=category)
    finally:
        store.close()
    for rank, hit in enumerate(hits, 1):
        console.print(f"[bold]{rank}. {hit.heading_path}[/bold]  [dim]{hit.doc_id}  score {hit.score:.3f}[/dim]")
        console.print(f"   {hit.text[:220]}")


@app.command()
def status(fail_if_stale: bool = typer.Option(False, help="Exit 1 if the index is behind the docs")) -> None:
    """Show index size, the last run, and what the next run would change."""
    report = pending_changes(Settings())
    console.print_json(json.dumps(report, default=str))
    if fail_if_stale and not report["fresh"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
