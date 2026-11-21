import numpy as np

from rag_ingest.chunking import Chunk
from rag_ingest.embeddings import HashingEmbedder, sparse_vector
from rag_ingest.quality import apply_gates, redact


def chunk(text: str, i: int = 0) -> Chunk:
    return Chunk(chunk_id=f"c{i}", doc_id="d.md", ordinal=i, heading_path="T > H", heading="H",
                 text=text, embed_text=f"T > H\n\n{text}", n_tokens=len(text.split()))


def test_redact_removes_emails_and_phone_numbers_but_not_ordinary_numbers():
    text, n = redact("Mail ops@example.com or call +1-555-319-1614. Retain 365 days; port 5432, at 03:00 UTC.")
    assert n == 2
    assert "ops@example.com" not in text and "319-1614" not in text
    assert "[EMAIL]" in text and "[PHONE]" in text
    assert "365 days" in text and "5432" in text and "03:00" in text


def test_gates_reject_short_duplicate_and_symbol_chunks_with_reasons():
    good = "This paragraph explains how the nightly job is restarted safely."
    chunks = [chunk(good, 0), chunk("Too short", 1), chunk(good.upper(), 2),
              chunk("=== --- *** ||| ### ~~~ ^^^ $$$ %%% &&& !!! ???", 3)]
    result = apply_gates(chunks, min_tokens=5, max_tokens=100, redact_pii=True)
    assert [c.chunk_id for c in result.accepted] == ["c0"]
    assert sorted(reason for _, reason in result.rejected) == [
        "duplicate_in_document", "mostly_symbols", "too_short"]


def test_redaction_changes_the_chunk_id_so_unredacted_vectors_are_never_reused():
    original = chunk("Contact the owner at owner@example.com for access to the table.")
    redacted = apply_gates([original], 5, 100, redact_pii=True).accepted[0]
    kept = apply_gates([original], 5, 100, redact_pii=False).accepted[0]
    assert redacted.chunk_id != original.chunk_id and "[EMAIL]" in redacted.embed_text
    assert kept.chunk_id == original.chunk_id


def test_hashing_embedder_is_deterministic_normalised_and_reflects_overlap():
    e = HashingEmbedder(256)
    a, b, c = e.embed(["restart the billing export job", "restarting billing export jobs",
                       "quarterly tax filing deadline"])
    assert np.allclose(e.embed(["restart the billing export job"])[0], a)
    assert np.isclose(np.linalg.norm(a), 1.0)
    assert a @ b > 0.4 > a @ c


def test_sparse_vectors_are_sorted_unique_and_drop_stopwords():
    indices, values = sparse_vector("the job and the job and the schedule")
    assert indices == sorted(set(indices)) and len(indices) == 2
    assert all(v > 0 for v in values)
    q_indices, q_values = sparse_vector("job schedule", is_query=True)
    assert set(q_indices) == set(indices) and q_values == [1.0, 1.0]
