"""End-to-end ingestion CLI run against the local Atlas container.
MOCK / TEST ONLY: API Setu responses and embeddings are fakes."""
import httpx
import pytest

from app import config, providers, upstream
from conftest import TEST_MONGODB_URI, FakeEmbedder
from ingestion.__main__ import main
from test_sources import DETAIL, DOCUMENTS, FAQS

pytestmark = pytest.mark.integration


@pytest.fixture
def cli_env(monkeypatch, test_db):
    monkeypatch.setattr(config, "MONGODB_URI", TEST_MONGODB_URI)
    monkeypatch.setattr(config, "MONGODB_DATABASE", test_db.name)
    monkeypatch.setattr(config, "APISETU_CLIENT_ID", "client-test")
    monkeypatch.setattr(config, "APISETU_API_KEY", "key-test")
    monkeypatch.setattr(providers, "embed_documents", FakeEmbedder())
    listing = {"slugs": ["test-state-scheme"]}

    def handler(request):
        path = request.url.path
        if path.endswith("/search/schemes"):
            slugs = listing["slugs"] if request.url.params["from"] == "0" else []
            return httpx.Response(200, json={"data": {"hits": {"items": [
                {"fields": {"slug": s, "schemeName": s}} for s in slugs]}}})
        if path.endswith("/public/schemes"):
            slug = request.url.params["slug"]
            return httpx.Response(200, json={"data": {**DETAIL, "slug": slug, "schemeId": f"id-{slug}"}})
        if path.endswith("/documents"):
            return httpx.Response(200, json={"data": DOCUMENTS})
        if path.endswith("/faqs"):
            return httpx.Response(200, json={"data": FAQS})
        return httpx.Response(404)

    monkeypatch.setattr(upstream, "client", httpx.Client(transport=httpx.MockTransport(handler)))
    return listing


def test_myscheme_run_stores_embeds_and_prunes(cli_env, test_db, capsys):
    main(["myscheme"])
    scheme = test_db.schemes.find_one({"_id": "test-state-scheme"})
    assert scheme["sourceUrl"] == "https://www.myscheme.gov.in/schemes/test-state-scheme"
    sections = {c["section"] for c in test_db.scheme_chunks.find({"schemeId": "test-state-scheme"})}
    assert sections == {"overview", "eligibility", "benefits", "documents", "application", "faq"}
    assert '"stored": 1' in capsys.readouterr().out

    # The source stops publishing the scheme and publishes another: a complete run prunes the old one.
    cli_env["slugs"] = ["another-scheme"]
    main(["myscheme"])
    assert [d["_id"] for d in test_db.schemes.find()] == ["another-scheme"]
    assert test_db.scheme_chunks.count_documents({"schemeId": "test-state-scheme"}) == 0


def test_empty_listing_never_prunes_stored_schemes(cli_env, test_db):
    main(["myscheme"])
    cli_env["slugs"] = []  # e.g. an unrecognised response shape yields no slugs
    main(["myscheme"])
    assert test_db.schemes.count_documents({}) == 1


def test_limited_run_never_prunes(cli_env, test_db):
    main(["myscheme"])
    cli_env["slugs"] = ["another-scheme"]
    main(["myscheme", "--limit", "1"])
    assert {d["_id"] for d in test_db.schemes.find()} == {"test-state-scheme", "another-scheme"}


def test_ogd_run_without_configured_datasets_is_a_no_op(cli_env, test_db):
    main(["ogd"])
    assert test_db.schemes.count_documents({}) == 0
