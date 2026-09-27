"""Official data sources: the myScheme API on API Setu, and data.gov.in (OGD) datasets."""
import hashlib
import html
import re
import sqlite3
from pathlib import Path

from app.upstream import UpstreamError, request_json

MYSCHEME_BASE = "https://apisetu.gov.in/meity/myscheme/srv/v7"
MYSCHEME_PAGE = "https://www.myscheme.gov.in/schemes/{slug}"
OGD_BASE = "https://api.data.gov.in/resource"
OGD_RESOURCE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
OGD_FIELDS = ("name", "description", "eligibilityText", "benefits", "ministry", "state")
CLEAN_OGD_SQL = Path(__file__).with_name("clean_ogd.sql").read_text(encoding="utf-8")
LINK = re.compile(r"^https?://", re.IGNORECASE)


# ---------- text helpers ----------

def clean_text(value) -> str | None:
    """Decodes HTML entities (the source sometimes double-encodes them) and trims whitespace."""
    if not isinstance(value, str):
        return None
    for _ in range(3):
        decoded = html.unescape(value)
        if decoded == value:
            break
        value = decoded
    value = re.sub(r"[ \t]+\n", "\n", value).strip()
    return value or None


def rich_text(nodes) -> str | None:
    """Flattens the source's rich-text tree (paragraphs, ordered/unordered lists, links) to plain text."""
    lines: list[str] = []

    def inline(leaf: dict) -> str:
        text = leaf.get("text") or ""
        link = leaf.get("link") or leaf.get("url")
        return f"{text} ({link})" if isinstance(link, str) and LINK.match(link) and link not in text else text

    def walk(node: dict, marker: str = "") -> None:
        children = [c for c in node.get("children") or [] if isinstance(c, dict)]
        kind = node.get("type")
        if kind in ("ol_list", "ul_list"):
            for i, child in enumerate(children, 1):
                walk(child, f"{i}. " if kind == "ol_list" else "- ")
        elif not children:
            if node.get("text", "").strip():
                lines.append(marker + inline(node).strip())
        elif all("children" not in c for c in children):
            text = "".join(inline(c) for c in children).strip()
            if text:
                lines.append(marker + text)
        else:
            for i, child in enumerate(children):
                walk(child, marker if i == 0 else "")

    for node in nodes if isinstance(nodes, list) else []:
        if isinstance(node, dict):
            walk(node)
    return clean_text("\n".join(lines))


def label(value) -> str | None:
    return clean_text(value.get("label")) if isinstance(value, dict) else clean_text(value)


def labels(values) -> list[str]:
    return [v for v in (label(x) for x in values or []) if v]


def name_key(name: str) -> str:
    """Normalised scheme name used to spot the same scheme arriving from two sources."""
    name = re.sub(r"\([^)]*\)", " ", name.lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", name).split())


def slugify(text: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


# ---------- myScheme (API Setu) ----------

def apisetu_headers(client_id: str, api_key: str) -> dict:
    return {"X-APISETU-CLIENTID": client_id, "X-APISETU-APIKEY": api_key}


def list_myscheme_slugs(headers: dict, limit: int | None = None, page_size: int = 50) -> list[str]:
    """Pages through the official search API (sorted by name for stable paging) and returns scheme slugs."""
    slugs: list[str] = []
    seen: set[str] = set()
    offset = 0
    while limit is None or len(slugs) < limit:
        data = request_json("GET", f"{MYSCHEME_BASE}/search/schemes", headers=headers, attempts=3, params={
            "lang": "en", "q": "[]", "keyword": "", "sort": "schemename-asc", "from": offset, "size": page_size})
        page = [s for s in _scheme_slugs(data) if s not in seen]
        if not page:
            break
        seen.update(page)
        slugs.extend(page)
        offset += page_size
    return slugs[:limit] if limit else slugs


def _scheme_slugs(payload) -> list[str]:
    # The published example response omits the item structure, so items are found structurally:
    # any object (or its "fields" object) that carries both a slug and a scheme name.
    found = []

    def walk(node) -> None:
        if isinstance(node, dict):
            fields = node.get("fields") if isinstance(node.get("fields"), dict) else node
            if isinstance(fields.get("slug"), str) and fields.get("schemeName"):
                found.append(fields["slug"])
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return found


def fetch_myscheme_scheme(headers: dict, slug: str) -> dict:
    """Fetches details, documents and FAQs for one scheme and maps them to a scheme record."""
    detail = request_json("GET", f"{MYSCHEME_BASE}/public/schemes", headers=headers, attempts=3,
                          params={"slug": slug, "lang": "en"}).get("data") or {}
    scheme_id = detail.get("schemeId")
    if not scheme_id:
        raise UpstreamError(f"no scheme found for slug {slug!r}")
    return map_myscheme(detail, _optional(headers, f"{scheme_id}/documents"), _optional(headers, f"{scheme_id}/faqs"))


def _optional(headers: dict, path: str) -> dict:
    """Documents and FAQs may simply not be published (404); any other failure aborts this scheme."""
    try:
        return request_json("GET", f"{MYSCHEME_BASE}/public/schemes/{path}", headers=headers, attempts=3,
                            params={"lang": "en"}).get("data") or {}
    except UpstreamError as exc:
        if exc.status == 404:
            return {}
        raise


def map_myscheme(detail: dict, documents: dict, faqs: dict) -> dict:
    en = detail.get("en") or {}
    basic = en.get("basicDetails") or {}
    content = en.get("schemeContent") or {}
    criteria = content.get("eligibilityCriteria") or {}
    slug = detail.get("slug")
    level = label(basic.get("level"))
    # A state scheme is offered by that state's government; central schemes have no state condition.
    state = label(basic.get("state")) if (level or "").lower() == "state" else None
    name = clean_text(basic.get("schemeName")) or ""
    return {
        "_id": slug,
        "name": name,
        "shortTitle": clean_text(basic.get("schemeShortTitle")),
        "description": clean_text(content.get("briefDescription")),
        "details": clean_text(content.get("detailedDescription_md")) or rich_text(content.get("detailedDescription")),
        "eligibilityText": clean_text(criteria.get("eligibilityDescription_md"))
                           or rich_text(criteria.get("eligibilityDescription")),
        "benefits": rich_text(content.get("benefits")),
        "documents": rich_text((documents.get("en") or {}).get("documents_required")),
        "applicationProcess": _application_text(content.get("applicationProcess")),
        "conditions": None,  # not part of the documented response; mapped only once verified against live data
        "level": level,
        "state": state,
        "ministry": label(basic.get("nodalMinistryName")),
        "department": label(basic.get("nodalDepartmentName")),
        "implementingAgency": clean_text(basic.get("implementingAgency")),
        "categories": labels(basic.get("schemeCategory")),
        "tags": [t for t in (clean_text(t) for t in basic.get("tags") or []) if t],
        "beneficiaryTypes": labels(basic.get("targetBeneficiaries")),
        "openDate": basic.get("schemeOpenDate"),
        "closeDate": basic.get("schemeCloseDate"),
        "references": [{"title": clean_text(r.get("title")) or "Official reference", "url": r["url"].strip()}
                       for r in content.get("references") or []
                       if isinstance(r, dict) and isinstance(r.get("url"), str) and LINK.match(r["url"].strip())],
        "faqs": [{"question": q, "answer": a} for q, a in (
            (clean_text(f.get("question")), rich_text(f.get("answer"))) for f in (faqs.get("en") or {}).get("faqs") or []
            if isinstance(f, dict)) if q and a],
        "eligibility": {"states": [state]} if state else {},
        "sourceUrl": MYSCHEME_PAGE.format(slug=slug) if slug else None,
        "sourceName": "myScheme",
        "nameKey": name_key(name),
    }


def _application_text(steps) -> str | None:
    blocks = []
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, dict):
            continue
        mode, url = clean_text(step.get("mode")), step.get("url")
        lines = [f"{mode}:" if mode else None, rich_text(step.get("process")),
                 f"Apply at: {url.strip()}" if isinstance(url, str) and LINK.match(url.strip()) else None]
        block = "\n".join(line for line in lines if line)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks) or None


# ---------- data.gov.in (OGD) ----------

def fetch_ogd(resource_id: str, api_key: str, page_size: int = 100, max_records: int = 5000) -> list[dict]:
    if not OGD_RESOURCE_ID.match(resource_id):
        raise ValueError(f"not a data.gov.in resource id: {resource_id!r}")
    rows: list[dict] = []
    while len(rows) < max_records:
        data = request_json("GET", f"{OGD_BASE}/{resource_id}", attempts=3, params={
            "api-key": api_key, "format": "json", "offset": len(rows), "limit": page_size})
        batch = data.get("records") or []
        rows.extend(batch)
        if not batch or len(rows) >= int(data.get("total") or 0):
            break
    return rows


def clean_ogd_rows(rows: list[dict], columns: dict[str, str]) -> tuple[list[dict], dict]:
    """Loads mapped columns into SQLite and cleans them with clean_ogd.sql. Returns (rows, checks)."""
    con = sqlite3.connect(":memory:")
    try:
        con.execute(f"CREATE TABLE raw (row_no INTEGER, {', '.join(f'{f} TEXT' for f in OGD_FIELDS)})")
        con.executemany(
            f"INSERT INTO raw VALUES (?, {', '.join('?' for _ in OGD_FIELDS)})",
            [(i, *(_cell(row.get(columns[f])) if f in columns else None for f in OGD_FIELDS))
             for i, row in enumerate(rows)])
        missing_name = con.execute("SELECT COUNT(*) FROM raw WHERE TRIM(COALESCE(name, '')) = ''").fetchone()[0]
        con.row_factory = sqlite3.Row
        cleaned = [dict(r) for r in con.execute(CLEAN_OGD_SQL)]
    finally:
        con.close()
    checks = {"rows": len(rows), "missing_name": missing_name, "duplicates": len(rows) - missing_name - len(cleaned)}
    return cleaned, checks


def _cell(value) -> str | None:
    return clean_text(str(value)) if value is not None else None


def map_ogd(dataset: dict, row: dict) -> dict:
    name = row["name"]
    state = row.get("state") or dataset.get("state")
    digest = hashlib.sha1(f"{dataset['resourceId']}:{name}".encode()).hexdigest()[:8]
    return {
        "_id": f"ogd-{slugify(name)[:80]}-{digest}",
        "name": name,
        "shortTitle": None,
        "description": row.get("description"),
        "details": None,
        "eligibilityText": row.get("eligibilityText"),
        "benefits": row.get("benefits"),
        "documents": None,
        "applicationProcess": None,
        "conditions": None,
        "level": dataset.get("level"),
        "state": state,
        "ministry": row.get("ministry") or dataset.get("ministry"),
        "department": None,
        "implementingAgency": None,
        "categories": dataset.get("categories") or [],
        "tags": [],
        "beneficiaryTypes": [],
        "openDate": None,
        "closeDate": None,
        "references": [],
        "faqs": [],
        "eligibility": {"states": [state]} if state else {},
        "sourceUrl": dataset["sourceUrl"],
        "sourceName": "data.gov.in",
        "nameKey": name_key(name),
    }
