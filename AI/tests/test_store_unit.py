import pytest

from ingestion.store import build_chunks, split_text, validate

VALID = {"_id": "pm-test", "name": "Test Scheme", "sourceUrl": "https://www.myscheme.gov.in/schemes/pm-test",
         "sourceName": "myScheme"}


@pytest.mark.parametrize("url", [
    "https://www.myscheme.gov.in/schemes/pm-kisan",
    "https://data.gov.in/resource/x",
    "https://pmkisan.gov.in",
    "https://scholarships.nic.in/page",
])
def test_official_urls_are_accepted(url):
    assert validate({**VALID, "sourceUrl": url}) is None


@pytest.mark.parametrize("url", [
    None, "", "http://www.myscheme.gov.in/schemes/x",  # plain http
    "https://example.com/gov.in", "https://gov.in.example.com/", "https://gov.in@example.com/",
    "https://www.myscheme.gov.in:8443/", "https://fakegov.in/", "ftp://data.gov.in/",
])
def test_unofficial_or_missing_urls_are_rejected(url):
    assert validate({**VALID, "sourceUrl": url}) == "missing or non-official source URL"


def test_missing_name_and_bad_id_are_rejected():
    assert validate({**VALID, "name": "  "}) == "missing scheme name"
    assert validate({**VALID, "_id": "has space"}) == "invalid or missing id"
    assert validate({**VALID, "sourceName": ""}) == "missing source name"


def test_split_text_packs_paragraphs_under_the_limit():
    text = "\n\n".join(["a" * 40, "b" * 40, "c" * 40])
    assert split_text(text, limit=90) == ["a" * 40 + "\n\n" + "b" * 40, "c" * 40]


def test_split_text_breaks_long_paragraphs_by_sentence_then_hard_cut():
    pieces = split_text("First sentence here. " + "x" * 50, limit=30)
    assert all(len(p) <= 30 for p in pieces)
    assert "".join(pieces).replace("\n", "") == "First sentence here." + "x" * 50


def test_split_text_of_empty_text_is_empty():
    assert split_text("  \n\n ") == []


def test_build_chunks_creates_sections_with_stable_ids():
    record = {**VALID, "description": "Helps farmers.", "eligibilityText": "Must be a farmer.",
              "faqs": [{"question": "Who?", "answer": "Farmers."}]}
    chunks = build_chunks(record)
    assert [c["_id"] for c in chunks] == ["pm-test#overview#0", "pm-test#eligibility#0", "pm-test#faq#0"]
    assert chunks[0]["text"] == "Test Scheme\n\nHelps farmers."
    assert chunks[2]["text"] == "Q: Who?\nA: Farmers."
    assert all(c["schemeId"] == "pm-test" and c["hash"] for c in chunks)


def test_overview_chunk_exists_even_without_description():
    assert [c["section"] for c in build_chunks(VALID)] == ["overview"]


def test_chunk_hash_changes_with_text_and_embedding_model(monkeypatch):
    base = build_chunks({**VALID, "benefits": "Rs 1000"})[1]["hash"]
    assert build_chunks({**VALID, "benefits": "Rs 2000"})[1]["hash"] != base
    monkeypatch.setattr("app.config.GEMINI_EMBEDDING_MODEL", "another-model")
    assert build_chunks({**VALID, "benefits": "Rs 1000"})[1]["hash"] != base
