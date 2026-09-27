"""MOCK / TEST ONLY: synthetic fixtures shaped like the documented API Setu myScheme and data.gov.in
responses. The scheme content below is invented for tests and describes no real scheme."""
import json

import httpx
import pytest

from app import upstream
from ingestion import sources
from ingestion.store import validate


def leaf(text, **extra):
    return {"text": text, **extra}


def para(*leaves):
    return {"type": "paragraph", "children": list(leaves)}


DETAIL = {
    "schemeId": "abc123",
    "slug": "test-state-scheme",
    "en": {
        "basicDetails": {
            "schemeName": "Test State Pension Scheme",
            "schemeShortTitle": "TSPS",
            "level": {"value": "state", "label": "State"},
            "state": {"value": 1, "label": "Test State"},
            "nodalMinistryName": {"value": 7, "label": "Test Ministry"},
            "nodalDepartmentName": {"value": 8, "label": "Test Department"},
            "implementingAgency": "Test Board",
            "schemeCategory": [{"value": "c1", "label": "Social welfare &amp; Empowerment"}],
            "targetBeneficiaries": [{"value": "individual", "label": "Individual"}],
            "tags": ["Pension", " Worker "],
            "schemeOpenDate": "2020-01-01",
        },
        "schemeContent": {
            "briefDescription": "A test pension for registered workers.",
            "detailedDescription_md": "&amp;quot;Test&amp;quot; pension details.\n",
            "benefits": [{"type": "ul_list", "children": [
                {"type": "list_item", "children": [leaf("Rs 100 per month")]}]}],
            "eligibilityCriteria": {"eligibilityDescription_md": "1. Resident of Test State.\n2. Aged 60 or above.\n"},
            "applicationProcess": [{"mode": "Online", "url": "https://test.gov.in/apply",
                                    "process": [para(leaf("Register on the portal."))]}],
            "references": [{"title": "Guidelines", "url": "https://test.gov.in/guidelines.pdf"},
                           {"title": "Bad", "url": "javascript:alert(1)"}],
        },
    },
}
DOCUMENTS = {"en": {"documents_required": [{"type": "ol_list", "children": [
    {"type": "list_item", "children": [leaf("Proof of identity")]},
    {"type": "list_item", "children": [leaf("Proof of address")]}]}]}}
FAQS = {"en": {"faqs": [{"_id": "f1", "question": "Who can apply?", "answer": [para(leaf("Registered workers."))]}]}}


def test_clean_text_decodes_double_encoded_entities():
    assert sources.clean_text("&amp;quot;Hi&amp;quot; &amp;amp; bye ") == '"Hi" & bye'
    assert sources.clean_text("   ") is None
    assert sources.clean_text(None) is None


def test_rich_text_flattens_lists_paragraphs_and_links():
    nodes = [para(leaf("Apply "), leaf("here", link="https://x.gov.in/a")),
             {"type": "ol_list", "children": [
                 {"type": "list_item", "children": [leaf("First")]},
                 {"type": "list_item", "children": [para(leaf("Second"))]}]}]
    assert sources.rich_text(nodes) == "Apply here (https://x.gov.in/a)\n1. First\n2. Second"
    assert sources.rich_text([]) is None and sources.rich_text(None) is None


def test_map_myscheme_maps_documented_fields():
    record = sources.map_myscheme(DETAIL, DOCUMENTS, FAQS)
    assert record["_id"] == "test-state-scheme"
    assert record["name"] == "Test State Pension Scheme"
    assert record["details"] == '"Test" pension details.'
    assert record["eligibilityText"] == "1. Resident of Test State.\n2. Aged 60 or above."
    assert record["benefits"] == "- Rs 100 per month"
    assert record["documents"] == "1. Proof of identity\n2. Proof of address"
    assert record["applicationProcess"] == "Online:\nRegister on the portal.\nApply at: https://test.gov.in/apply"
    assert record["conditions"] is None  # undocumented field is never guessed
    assert (record["level"], record["state"]) == ("State", "Test State")
    assert record["eligibility"] == {"states": ["Test State"]}
    assert record["categories"] == ["Social welfare & Empowerment"]
    assert record["tags"] == ["Pension", "Worker"]
    assert record["references"] == [{"title": "Guidelines", "url": "https://test.gov.in/guidelines.pdf"}]
    assert record["faqs"] == [{"question": "Who can apply?", "answer": "Registered workers."}]
    assert record["sourceUrl"] == "https://www.myscheme.gov.in/schemes/test-state-scheme"
    assert record["nameKey"] == "test state pension scheme"
    assert validate(record) is None


def test_central_scheme_has_no_state_condition():
    detail = json.loads(json.dumps(DETAIL))
    detail["en"]["basicDetails"]["level"] = {"value": "central", "label": "Central"}
    record = sources.map_myscheme(detail, {}, {})
    assert record["state"] is None and record["eligibility"] == {}
    assert record["documents"] is None and record["faqs"] == []


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


def search_page(items):
    return httpx.Response(200, json={"status": "Success", "data": {"hits": {"items": [
        {"id": i, "fields": {"slug": s, "schemeName": f"Scheme {s}"}} for i, s in enumerate(items)]}}})


def test_list_slugs_pages_until_empty_and_sends_auth_headers(api):
    pages = {0: ["a", "b"], 2: ["c"]}
    api["routes"].append((lambda r: r.url.path.endswith("/search/schemes"),
                          lambda r: search_page(pages.get(int(r.url.params["from"]), []))))
    headers = sources.apisetu_headers("client-test", "key-test")
    assert sources.list_myscheme_slugs(headers, page_size=2) == ["a", "b", "c"]
    first = api["calls"][0]
    assert first.headers["X-APISETU-CLIENTID"] == "client-test" and first.headers["X-APISETU-APIKEY"] == "key-test"
    assert first.url.params["sort"] == "schemename-asc" and first.url.params["q"] == "[]"
    assert sources.list_myscheme_slugs(headers, limit=1, page_size=2) == ["a"]


def test_fetch_scheme_treats_missing_faqs_as_none_published(api):
    api["routes"] += [
        (lambda r: r.url.path.endswith("/public/schemes"), lambda r: httpx.Response(200, json={"data": DETAIL})),
        (lambda r: r.url.path.endswith("/documents"), lambda r: httpx.Response(200, json={"data": DOCUMENTS})),
    ]
    record = sources.fetch_myscheme_scheme({}, "test-state-scheme")
    assert record["documents"] and record["faqs"] == []
    assert api["calls"][0].url.params["slug"] == "test-state-scheme"


def test_fetch_scheme_aborts_when_documents_fail(api):
    api["routes"] += [
        (lambda r: r.url.path.endswith("/public/schemes"), lambda r: httpx.Response(200, json={"data": DETAIL})),
        (lambda r: r.url.path.endswith("/documents"), lambda r: httpx.Response(500, text="err")),
    ]
    with pytest.raises(upstream.UpstreamError):
        sources.fetch_myscheme_scheme({}, "test-state-scheme")


def test_fetch_scheme_rejects_unknown_slug(api):
    api["routes"].append((lambda r: True, lambda r: httpx.Response(200, json={"data": {}})))
    with pytest.raises(upstream.UpstreamError, match="no scheme found"):
        sources.fetch_myscheme_scheme({}, "nope")


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
