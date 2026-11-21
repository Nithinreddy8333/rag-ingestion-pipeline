import pytest

from rag_ingest import corpus
from rag_ingest.pipeline import IndexConfigChanged, pending_changes, run_ingest
from rag_ingest.state import StateStore


def ingest(env, **kwargs):
    settings, embedder, store = env
    return run_ingest(settings, embedder=embedder, store=store, **kwargs)


def test_first_run_ingests_everything(env):
    stats = ingest(env)
    assert stats["docs_new"] == 12 and stats["docs_unchanged"] == 0
    assert stats["chunks_upserted"] == stats["points_in_store"] == 4 * 5 + 8 * 3
    assert stats["embeddings_computed"] == stats["points_in_store"]
    assert stats["pii_redactions"] == 8  # one email and one phone number per runbook


def test_second_run_is_a_no_op(env):
    _, embedder, _ = env
    ingest(env)
    calls_after_first = embedder.total
    stats = ingest(env)
    assert stats["docs_unchanged"] == 12
    assert stats["chunks_upserted"] == stats["chunks_removed"] == stats["embeddings_computed"] == 0
    assert embedder.total == calls_after_first


def test_editing_one_section_re_embeds_only_that_chunk_and_removes_the_old_text(env):
    settings, embedder, store = env
    ingest(env)
    path = settings.docs_dir / "runbooks" / "orders-cdc.md"
    path.write_text(path.read_text().replace("Never restart with a full refresh", "Always page the owner before a full refresh"))
    before = embedder.total
    stats = ingest(env)
    assert (stats["docs_changed"], stats["docs_unchanged"]) == (1, 11)
    assert embedder.total - before == 1
    assert stats["embeddings_from_cache"] == 4 and stats["chunks_removed"] == 1
    texts = [h.text for h in store.search("orders-cdc restart full refresh", embedder, mode="sparse", k=20)]
    assert any("Always page the owner" in t for t in texts)
    assert not any("Never restart with a full refresh during" in t and "orders-cdc" in t for t in texts)


def test_deleting_a_document_removes_its_chunks_from_the_index(env):
    settings, embedder, store = env
    first = ingest(env)
    (settings.docs_dir / "runbooks" / "billing-export.md").unlink()
    stats = ingest(env)
    assert stats["docs_deleted"] == 1 and stats["chunks_removed"] == 5
    assert stats["points_in_store"] == first["points_in_store"] - 5
    hits = store.search("billing-export runbook contacts", embedder, k=20)
    assert all(h.doc_id != "runbooks/billing-export.md" for h in hits)


def test_index_and_state_always_agree(env):
    settings, _, store = env
    ingest(env)
    corpus.mutate(settings.docs_dir, seed=5, n_edit=2, n_delete=1, n_add=2)
    ingest(env)
    state = StateStore(settings.state_path)
    try:
        assert state.summary()["chunks"] == store.count()
    finally:
        state.close()


def test_identical_text_in_two_documents_is_embedded_once(env):
    settings, embedder, _ = env
    for name in ("a.md", "b.md"):
        (settings.docs_dir / name).write_text("# Shared\n\n## Notice\n\nThis exact paragraph appears in two separate files.\n")
    stats = ingest(env)
    assert stats["chunks_upserted"] == stats["embeddings_computed"] + 1


def test_changing_the_embedding_setup_is_refused_until_rebuild(env):
    settings, embedder, store = env
    ingest(env)
    settings.max_tokens = 90
    with pytest.raises(IndexConfigChanged):
        ingest(env)
    stats = ingest(env, rebuild=True)
    assert stats["docs_new"] == 12
    assert stats["embeddings_computed"] == 0, "a rebuild with the same model should be served from cache"


def test_a_crash_mid_run_is_repaired_by_running_again(env):
    settings, embedder, store = env
    real_upsert, calls = store.upsert, {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 4:
            raise ConnectionError("vector store went away")
        return real_upsert(*args, **kwargs)

    store.upsert = flaky
    with pytest.raises(ConnectionError):
        ingest(env)
    store.upsert = real_upsert
    assert len(pending_changes(settings)["pending"]["new"]) == 9  # three documents were committed
    stats = ingest(env)
    assert stats["docs_new"] == 9 and stats["embeddings_computed"] == 0
    assert stats["points_in_store"] == 44 and pending_changes(settings)["fresh"]


def test_status_reports_pending_work_without_doing_it(env):
    settings, embedder, _ = env
    ingest(env)
    assert pending_changes(settings)["fresh"]
    changes = corpus.mutate(settings.docs_dir, seed=2, n_edit=1, n_delete=1, n_add=1)
    before = embedder.total
    report = pending_changes(settings)
    assert not report["fresh"] and embedder.total == before
    assert report["pending"] == {"new": changes["added"], "changed": changes["edited"],
                                 "deleted": changes["deleted"]}
