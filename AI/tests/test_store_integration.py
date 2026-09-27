"""Runs against the local Atlas container. MOCK / TEST ONLY scheme records and embeddings."""
import time

import pytest
from pymongo.errors import WriteError

from app import providers
from conftest import FakeEmbedder
from ingestion.store import VECTOR_INDEX, ensure_schema, prune_missing, store_schemes, wait_for_vector_index

pytestmark = pytest.mark.integration


def record(scheme_id, **fields):
    return {"_id": scheme_id, "name": f"Test fixture {scheme_id} (MOCK / TEST ONLY)",
            "sourceUrl": f"https://www.myscheme.gov.in/schemes/{scheme_id}", "sourceName": "myScheme",
            "description": f"Description of {scheme_id}.", **fields}


def test_database_rejects_a_scheme_without_an_official_source(test_db):
    ensure_schema(test_db)
    with pytest.raises(WriteError):
        test_db.schemes.insert_one({"_id": "x", "name": "No source", "sourceName": "myScheme"})
    with pytest.raises(WriteError):
        test_db.schemes.insert_one({"_id": "y", "name": "Bad source", "sourceName": "myScheme",
                                    "sourceUrl": "https://example.com/scheme"})


def test_store_embeds_only_changed_chunks_and_removes_stale_ones(test_db):
    ensure_schema(test_db)
    embed = FakeEmbedder()
    first = store_schemes(test_db, [record("s-a", eligibilityText="Age 18 to 40."), record("s-b")], embed)
    assert first["stored"] == 2 and first["chunks_embedded"] == 3 and first["skipped"] == []
    assert test_db.scheme_chunks.count_documents({"embedding": {"$exists": True}}) == 3

    again = store_schemes(test_db, [record("s-a", eligibilityText="Age 18 to 40."), record("s-b")], embed)
    assert again["chunks_embedded"] == 0 and len(embed.calls) == 2  # nothing re-embedded

    changed = store_schemes(test_db, [record("s-a", benefits="Rs 500 per month.")], embed)
    assert changed["chunks_embedded"] == 1  # only the new benefits chunk
    assert changed["chunks_removed"] == 1  # eligibility section disappeared
    sections = sorted(c["section"] for c in test_db.scheme_chunks.find({"schemeId": "s-a"}))
    assert sections == ["benefits", "overview"]
    assert test_db.schemes.find_one({"_id": "s-a"})["syncedAt"]


def test_invalid_records_are_skipped_with_a_reason(test_db):
    ensure_schema(test_db)
    stats = store_schemes(test_db, [record("ok"), record("bad", sourceUrl="https://example.org/x")], FakeEmbedder())
    assert stats["stored"] == 1
    assert stats["skipped"] == [("bad", "missing or non-official source URL")]
    assert test_db.schemes.count_documents({}) == 1


def test_embedding_failure_skips_the_scheme_and_aborts_after_three_in_a_row(test_db):
    ensure_schema(test_db)

    def failing(docs):
        raise providers.ProviderError("quota exhausted")

    with pytest.raises(providers.ProviderError):
        store_schemes(test_db, [record(f"f-{i}") for i in range(5)], failing)
    # Scheme documents are stored (keyword search still works) but no chunk exists without an embedding.
    assert test_db.scheme_chunks.count_documents({}) == 0
    stats = store_schemes(test_db, [record("f-0")], FakeEmbedder())
    assert stats["chunks_embedded"] == 1  # a re-run completes what failed


def test_prune_removes_schemes_the_source_no_longer_publishes(test_db):
    ensure_schema(test_db)
    store_schemes(test_db, [record("keep"), record("gone")], FakeEmbedder())
    assert prune_missing(test_db, "myScheme", {"keep"}) == 1
    assert [d["_id"] for d in test_db.schemes.find()] == ["keep"]
    assert test_db.scheme_chunks.count_documents({"schemeId": "gone"}) == 0


def test_stored_chunks_are_searchable_by_vector(test_db):
    ensure_schema(test_db)
    store_schemes(test_db, [record("v-a", eligibilityText="Girls in class 9."), record("v-b")], FakeEmbedder())
    wait_for_vector_index(test_db, timeout=120)
    target = test_db.scheme_chunks.find_one({"_id": "v-a#eligibility#0"})
    pipeline = [{"$vectorSearch": {"index": VECTOR_INDEX, "path": "embedding", "queryVector": target["embedding"],
                                   "numCandidates": 20, "limit": 1}}, {"$project": {"_id": 1}}]
    deadline = time.monotonic() + 60
    hits = []
    while not hits and time.monotonic() < deadline:  # newly written vectors are indexed asynchronously
        hits = list(test_db.scheme_chunks.aggregate(pipeline))
        time.sleep(1)
    assert hits == [{"_id": "v-a#eligibility#0"}]
