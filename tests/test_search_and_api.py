import pytest
from fastapi.testclient import TestClient

from rag_ingest.api import create_app
from rag_ingest.pipeline import run_ingest


@pytest.fixture()
def indexed(env):
    settings, embedder, store = env
    run_ingest(settings, embedder=embedder, store=store)
    return env


@pytest.mark.parametrize("mode", ["dense", "sparse", "hybrid"])
def test_every_mode_finds_the_right_document(indexed, mode):
    _, embedder, store = indexed
    hits = store.search("fraud-features runbook restart procedure", embedder, mode=mode, k=3)
    assert hits[0].doc_id == "runbooks/fraud-features.md"
    assert hits[0].heading == "Restart procedure"
    assert len(hits) == 3 and hits[0].score >= hits[-1].score


def test_category_filter_restricts_results(indexed):
    _, embedder, store = indexed
    for mode in ("dense", "sparse", "hybrid"):
        hits = store.search("retention days", embedder, mode=mode, k=10, category="policies")
        assert hits and all(h.doc_id.startswith("policies/") for h in hits)


def test_unknown_mode_is_rejected(indexed):
    _, embedder, store = indexed
    with pytest.raises(ValueError):
        store.search("anything", embedder, mode="magic")


def test_api_endpoints(indexed, monkeypatch):
    settings, embedder, store = indexed
    monkeypatch.setattr("rag_ingest.api.get_embedder", lambda *_: embedder)
    with TestClient(create_app(settings, store=store)) as client:
        assert client.get("/health").json()["points"] == 44
        body = client.get("/search", params={"q": "how are confidential columns masked", "k": 2}).json()
        assert len(body["hits"]) == 2 and body["hits"][0]["doc_id"] == "policies/pii-handling-standard.md"
        assert client.get("/search", params={"q": "x", "mode": "magic"}).status_code == 422
        assert client.get("/search", params={"q": ""}).status_code == 422
        assert client.get("/search", params={"q": "x", "k": 500}).status_code == 422
        assert client.get("/status").json()["fresh"] is True
