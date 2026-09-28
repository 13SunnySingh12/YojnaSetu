"""End-to-end ingestion CLI runs against the local Atlas container.
MOCK / TEST ONLY: the verified records below are invented and the embeddings are fakes."""
import json

import pytest

from app import config, providers
from conftest import TEST_MONGODB_URI, FakeEmbedder
from ingestion import __main__ as cli
from ingestion import sources, store

pytestmark = pytest.mark.integration


def verified(scheme_id, **fields):
    return {"_id": scheme_id, "name": f"Test {scheme_id} Yojana", "sourceName": "myScheme",
            "sourceUrl": f"https://www.myscheme.gov.in/schemes/{scheme_id}", **fields}


@pytest.fixture
def verified_file(monkeypatch, test_db, tmp_path):
    monkeypatch.setattr(config, "MONGODB_URI", TEST_MONGODB_URI)
    monkeypatch.setattr(config, "MONGODB_DATABASE", test_db.name)
    monkeypatch.setattr(providers, "embed_documents", FakeEmbedder())
    path = tmp_path / "verified_schemes.json"
    monkeypatch.setattr(cli, "VERIFIED_FILE", path)

    def write(*records):
        path.write_text(json.dumps(list(records)), encoding="utf-8")
    return write


def test_verified_run_stores_embeds_and_prunes(verified_file, test_db, capsys):
    verified_file(verified("test-scheme", eligibilityText="Aged 60 or above.", benefits="Rs 100 per month.",
                           eligibility={"minAge": 60}))
    cli.main(["verified"])
    scheme = test_db.schemes.find_one({"_id": "test-scheme"})
    assert scheme["nameKey"] == "test test scheme yojana" and scheme["documents"] is None
    assert scheme["eligibility"] == {"minAge": 60}
    sections = {c["section"] for c in test_db.scheme_chunks.find({"schemeId": "test-scheme"})}
    assert sections == {"overview", "eligibility", "benefits"}
    assert '"stored": 1' in capsys.readouterr().out

    # The scheme leaves the file and another is added: the run prunes the old one and its chunks.
    verified_file(verified("another-scheme"))
    cli.main(["verified"])
    assert [d["_id"] for d in test_db.schemes.find()] == ["another-scheme"]
    assert test_db.scheme_chunks.count_documents({"schemeId": "test-scheme"}) == 0


def test_empty_or_mostly_emptied_file_never_prunes(verified_file, test_db):
    verified_file(*(verified(f"s-{i}") for i in range(5)))
    cli.main(["verified"])
    verified_file()  # emptied by mistake
    cli.main(["verified"])
    verified_file(verified("s-0"))  # most entries lost by mistake
    cli.main(["verified"])
    assert test_db.schemes.count_documents({}) == 5


def test_invalid_entry_keeps_its_last_good_version(verified_file, test_db, capsys):
    verified_file(verified("keep", benefits="Rs 100 per month."))
    cli.main(["verified"])
    verified_file(verified("keep", benefit="Rs 200 per month."))  # typo: rejected, and not pruned either
    cli.main(["verified"])
    assert test_db.schemes.find_one({"_id": "keep"})["benefits"] == "Rs 100 per month."
    assert "unknown field 'benefit'" in capsys.readouterr().out


def test_verified_record_replaces_the_same_scheme_from_data_gov_in(verified_file, test_db):
    dataset = {"resourceId": "0a1b2c3d-0000-4000-8000-000000000001",
               "sourceUrl": "https://www.data.gov.in/resource/test-dataset"}
    ogd = sources.map_ogd(dataset, {"name": "Test shared Yojana"})
    store.ensure_schema(test_db)
    store.store_schemes(test_db, [ogd], FakeEmbedder())
    verified_file(verified("shared"))  # same scheme name, full details
    cli.main(["verified"])
    assert [d["_id"] for d in test_db.schemes.find()] == ["shared"]
    assert test_db.scheme_chunks.count_documents({"schemeId": ogd["_id"]}) == 0


def test_ogd_run_without_configured_datasets_is_a_no_op(verified_file, test_db):
    cli.main(["ogd"])
    assert test_db.schemes.count_documents({}) == 0
