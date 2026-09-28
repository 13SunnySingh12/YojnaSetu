"""MOCK / TEST ONLY: synthetic fixtures shaped like documented data.gov.in responses and hand-written verified
records. The scheme content below is invented for tests and describes no real scheme."""
import httpx
import pytest

from app import upstream
from ingestion import sources
from ingestion.store import validate


def test_clean_text_decodes_double_encoded_entities():
    assert sources.clean_text("&amp;quot;Hi&amp;quot; &amp;amp; bye ") == '"Hi" & bye'
    assert sources.clean_text("   ") is None
    assert sources.clean_text(None) is None


@pytest.fixture
def api(monkeypatch):
    state = {"calls": [], "routes": []}

    def handler(request):
        state["calls"].append(request)
        for match, respond in state["routes"]:
            if match(request):
                return respond(request)
        return httpx.Response(404, json={"status": "Failure"})

    monkeypatch.setattr(upstream, "client", httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(upstream, "sleep", lambda s: None)
    return state


RESOURCE = "0a1b2c3d-0000-4000-8000-000000000001"


def test_fetch_ogd_pages_by_total_and_validates_resource_id(api):
    api["routes"].append((lambda r: RESOURCE in r.url.path, lambda r: httpx.Response(200, json={
        "total": 3, "records": [{"n": i} for i in range(int(r.url.params["offset"]),
                                                          min(3, int(r.url.params["offset"]) + 2))]})))
    assert [row["n"] for row in sources.fetch_ogd(RESOURCE, "ogd-key-test", page_size=2)] == [0, 1, 2]
    assert api["calls"][0].url.params["api-key"] == "ogd-key-test"
    with pytest.raises(ValueError):
        sources.fetch_ogd("../../etc", "k")


def test_clean_ogd_rows_trims_drops_nameless_and_dedupes():
    rows = [{"scheme": " Alpha Yojana ", "obj": " Helps farmers "}, {"scheme": "", "obj": "x"},
            {"scheme": "alpha yojana", "obj": "dup"}, {"scheme": "Beta", "obj": " "}]
    cleaned, checks = sources.clean_ogd_rows(rows, {"name": "scheme", "description": "obj"})
    assert cleaned == [
        {"name": "Alpha Yojana", "description": "Helps farmers", "eligibilityText": None, "benefits": None,
         "ministry": None, "state": None},
        {"name": "Beta", "description": None, "eligibilityText": None, "benefits": None, "ministry": None,
         "state": None}]
    assert checks == {"rows": 4, "missing_name": 1, "duplicates": 1}


def test_map_ogd_produces_a_publishable_record():
    dataset = {"resourceId": RESOURCE, "sourceUrl": "https://www.data.gov.in/resource/test-dataset",
               "level": "Central", "categories": ["Social welfare & Empowerment"], "ministry": "Test Ministry"}
    record = sources.map_ogd(dataset, {"name": "Alpha Yojana", "description": "Helps farmers"})
    assert record["_id"].startswith("ogd-alpha-yojana-")
    assert record["sourceName"] == "data.gov.in" and record["ministry"] == "Test Ministry"
    assert validate(record) is None
    assert sources.map_ogd(dataset, {"name": "Alpha Yojana"})["_id"] == record["_id"]  # stable across runs


def test_name_key_ignores_case_punctuation_and_acronyms():
    assert sources.name_key("Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)") == "pradhan mantri kisan samman nidhi"


def test_verified_record_fills_the_common_shape_and_derives_the_name_key():
    record = sources.verified_record({"_id": "test-scheme", "name": "Test Kisan Yojana (TKY)",
                                      "sourceUrl": "https://www.myscheme.gov.in/schemes/test-scheme",
                                      "sourceName": "myScheme", "benefits": "Rs 100 per month.",
                                      "nameKey": "typed by hand"})
    assert record["nameKey"] == "test kisan yojana"
    assert record["benefits"] == "Rs 100 per month." and record["documents"] is None
    assert record["categories"] == [] and record["eligibility"] == {}
    assert validate(record) is None
