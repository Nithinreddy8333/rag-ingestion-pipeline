from rag_ingest.chunking import Document, chunk_by_heading, chunk_fixed, read_documents, sha


def doc(text: str, doc_id: str = "a.md") -> Document:
    return Document(doc_id=doc_id, title="Guide", text=text, content_hash=sha(text, 32), source_mtime=0.0)


SAMPLE = """# Guide

## Setup

Install the tool. Then configure it.

### Linux

Use the package manager.

## Usage

Run the command daily.
"""


def test_heading_chunks_carry_their_full_heading_path():
    chunks = chunk_by_heading(doc(SAMPLE))
    assert [c.heading_path for c in chunks] == ["Guide > Setup", "Guide > Setup > Linux", "Guide > Usage"]
    assert [c.heading for c in chunks] == ["Setup", "Linux", "Usage"]
    assert chunks[1].embed_text.startswith("Guide > Setup > Linux\n\n")
    assert chunks[1].text == "Use the package manager."


def test_headings_inside_code_fences_are_not_treated_as_sections():
    text = "# Guide\n\n## Script\n\n```bash\n# this is a comment\necho hi\n```\n"
    chunks = chunk_by_heading(doc(text))
    assert len(chunks) == 1 and "# this is a comment" in chunks[0].text


def test_long_sections_are_split_within_the_token_budget_with_overlap():
    body = " ".join(f"Sentence number {i} has exactly seven words." for i in range(60))
    chunks = chunk_by_heading(doc(f"# Guide\n\n## Long\n\n{body}\n"), max_tokens=50, overlap_tokens=10)
    assert len(chunks) > 5
    assert all(c.n_tokens <= 50 + 10 for c in chunks)
    first, second = chunks[0].text.split(), chunks[1].text.split()
    assert first[-10:] == second[:10]
    assert all(c.heading == "Long" for c in chunks)


def test_a_single_oversized_sentence_is_still_split():
    chunks = chunk_by_heading(doc("# Guide\n\n## Blob\n\n" + "word " * 500), max_tokens=100, overlap_tokens=0)
    assert len(chunks) == 5 and all(c.n_tokens <= 100 for c in chunks)


def test_chunk_ids_are_stable_when_another_section_changes():
    before = {c.heading: c.chunk_id for c in chunk_by_heading(doc(SAMPLE))}
    edited = SAMPLE.replace("Run the command daily.", "Run the command hourly.")
    after = {c.heading: c.chunk_id for c in chunk_by_heading(doc(edited))}
    assert before["Setup"] == after["Setup"] and before["Linux"] == after["Linux"]
    assert before["Usage"] != after["Usage"]


def test_chunk_ids_differ_between_documents_with_identical_text():
    a = chunk_by_heading(doc(SAMPLE, "a.md"))[0]
    b = chunk_by_heading(doc(SAMPLE, "b.md"))[0]
    assert a.chunk_id != b.chunk_id and a.embed_text == b.embed_text


def test_fixed_chunker_covers_every_word():
    words = [f"w{i}" for i in range(250)]
    chunks = chunk_fixed(doc(" ".join(words)), max_tokens=100, overlap_tokens=20)
    assert [c.n_tokens for c in chunks] == [100, 100, 90]
    assert {w for c in chunks for w in c.text.split()} == set(words)


def test_read_documents_uses_relative_posix_ids_and_first_heading_as_title(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.md").write_text("intro\n\n# Real Title\n\nbody")
    (tmp_path / "notes.txt").write_text("plain text")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    docs = {d.doc_id: d for d in read_documents(tmp_path)}
    assert set(docs) == {"sub/x.md", "notes.txt"}
    assert docs["sub/x.md"].title == "Real Title" and docs["notes.txt"].title == "notes"
