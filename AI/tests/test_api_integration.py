"""AI service endpoints end to end on the local Atlas container.
MOCK / TEST ONLY: scheme records, embeddings and model replies are fakes."""
import time

import pytest
from fastapi.testclient import TestClient

from app import config, db, providers
from app.main import app
from app.upstream import UpstreamError
from conftest import TEST_MONGODB_URI, FakeEmbedder, fake_vector
from ingestion.store import ensure_schema, store_schemes, wait_for_vector_index

pytestmark = pytest.mark.integration
TOKEN = {"X-Internal-Token": "integration-token"}


def record(scheme_id, **fields):
    return {"_id": scheme_id, "name": f"Fixture {scheme_id} (MOCK / TEST ONLY)",
            "sourceUrl": f"https://www.myscheme.gov.in/schemes/{scheme_id}", "sourceName": "myScheme",
            "description": f"Overview of {scheme_id}.", **fields}


@pytest.fixture
def client(monkeypatch, test_db):
    ensure_schema(test_db)
    store_schemes(test_db, [record("girls-edu", eligibilityText="Girls in classes 9 to 12."),
                            record("farm-loan", benefits="Crop loan at low interest."),
                            record("old-pension")], FakeEmbedder())
    wait_for_vector_index(test_db, timeout=120)
    monkeypatch.setattr(config, "MONGODB_URI", TEST_MONGODB_URI)
    monkeypatch.setattr(config, "MONGODB_DATABASE", test_db.name)
    monkeypatch.setattr(config, "AI_SERVICE_TOKEN", "integration-token")
    db.get_db.cache_clear()
    replies = []
    monkeypatch.setattr(providers, "generate", lambda system, prompt, max_tokens=512: (
        replies.append(prompt) or "Grounded reply.", "gemini"))
    yield TestClient(app), test_db, replies
    db.get_db.cache_clear()


def query_near(monkeypatch, test_db, chunk_id):
    """Makes the query embedding equal to a stored chunk's embedding, so the expected hit is known."""
    vector = test_db.scheme_chunks.find_one({"_id": chunk_id})["embedding"]
    monkeypatch.setattr(providers, "embed_query", lambda text: vector)


def eventually(call, check, attempts=30):
    for _ in range(attempts):  # vectors written moments ago are indexed asynchronously
        result = call()
        if check(result):
            return result
        time.sleep(1)
    return result


def test_endpoints_require_the_internal_token(client):
    http, _, _ = client
    assert http.post("/search", json={"query": "x"}).status_code == 401
    assert http.post("/search", json={"query": "x"}, headers={"X-Internal-Token": "wrong"}).status_code == 401


def test_search_returns_the_scheme_with_the_closest_text(client, monkeypatch):
    http, test_db, _ = client
    query_near(monkeypatch, test_db, "girls-edu#eligibility#0")
    response = eventually(lambda: http.post("/search", json={"query": "school help for my daughter"}, headers=TOKEN),
                          lambda r: r.json()["results"])
    assert response.json()["results"][0]["schemeId"] == "girls-edu"
    assert all(r["score"] >= config.RETRIEVAL_MIN_SCORE for r in response.json()["results"])


def test_related_schemes_exclude_the_scheme_itself(client, monkeypatch):
    http, test_db, _ = client
    monkeypatch.setattr(config, "RETRIEVAL_MIN_SCORE", 0.0)  # fake vectors carry no meaning
    response = eventually(lambda: http.post("/related", json={"schemeId": "farm-loan"}, headers=TOKEN),
                          lambda r: r.json()["results"])
    ids = [r["schemeId"] for r in response.json()["results"]]
    assert ids and "farm-loan" not in ids


def test_ask_answers_from_retrieved_text_with_stored_source_links(client, monkeypatch):
    http, test_db, replies = client
    query_near(monkeypatch, test_db, "farm-loan#benefits#0")
    response = eventually(lambda: http.post("/ask", json={"question": "Is there a crop loan?"}, headers=TOKEN),
                          lambda r: r.json()["grounded"])
    body = response.json()
    assert body["grounded"] is True and body["answer"] == "Grounded reply."
    assert "Crop loan at low interest." in replies[-1]
    assert body["sources"][0] == {"schemeId": "farm-loan", "name": "Fixture farm-loan (MOCK / TEST ONLY)",
                                  "sourceUrl": "https://www.myscheme.gov.in/schemes/farm-loan"}


def test_ask_without_relevant_evidence_is_not_answered(client, monkeypatch):
    http, test_db, replies = client
    query_near(monkeypatch, test_db, "old-pension#overview#0")  # first prove the index is serving results
    eventually(lambda: http.post("/search", json={"query": "pension"}, headers=TOKEN), lambda r: r.json()["results"])
    monkeypatch.setattr(providers, "embed_query", lambda text: fake_vector("unrelated question text"))
    body = http.post("/ask", json={"question": "Who won the cricket match?"}, headers=TOKEN).json()
    assert body["grounded"] is False and body["sources"] == []
    assert replies == []


def test_provider_outage_is_a_503_without_details(client, monkeypatch):
    http, _, _ = client

    def down(text):
        raise UpstreamError("HTTP 503: provider overloaded")

    monkeypatch.setattr(providers, "embed_query", down)
    response = http.post("/search", json={"query": "anything"}, headers=TOKEN)
    assert response.status_code == 503 and response.json() == {"detail": "AI provider unavailable"}


def test_invalid_requests_are_rejected(client):
    http, _, _ = client
    assert http.post("/ask", json={"question": "x" * 501}, headers=TOKEN).status_code == 422
    assert http.post("/related", json={"schemeId": "../etc"}, headers=TOKEN).status_code == 422
