"""Official data sources: data.gov.in (OGD) datasets, and scheme details verified against official pages."""
import hashlib
import html
import re
import sqlite3
from pathlib import Path

from app.upstream import request_json

from .store import empty_scheme

OGD_BASE = "https://api.data.gov.in/resource"
OGD_RESOURCE_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
OGD_FIELDS = ("name", "description", "eligibilityText", "benefits", "ministry", "state")
CLEAN_OGD_SQL = Path(__file__).with_name("clean_ogd.sql").read_text(encoding="utf-8")


# ---------- text helpers ----------

def clean_text(value) -> str | None:
    """Decodes HTML entities (sources sometimes double-encode them) and trims whitespace."""
    if not isinstance(value, str):
        return None
    for _ in range(3):
        decoded = html.unescape(value)
        if decoded == value:
            break
        value = decoded
    value = re.sub(r"[ \t]+\n", "\n", value).strip()
    return value or None


def name_key(name: str) -> str:
    """Normalised scheme name used to spot the same scheme arriving from two sources."""
    name = re.sub(r"\([^)]*\)", " ", name.lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", name).split())


def slugify(text: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


# ---------- scheme details verified against official pages ----------

def verified_record(raw: dict) -> dict:
    """A record copied from an official page (myScheme or a ministry site) and checked by a person.

    Fields left out mean "not provided by the official source"; the name key is always derived.
    """
    return {**empty_scheme(), **raw, "nameKey": name_key(str(raw.get("name") or ""))}


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
        **empty_scheme(),
        "_id": f"ogd-{slugify(name)[:80]}-{digest}",
        "name": name,
        "description": row.get("description"),
        "eligibilityText": row.get("eligibilityText"),
        "benefits": row.get("benefits"),
        "level": dataset.get("level"),
        "state": state,
        "ministry": row.get("ministry") or dataset.get("ministry"),
        "categories": dataset.get("categories") or [],
        "eligibility": {"states": [state]} if state else {},
        "sourceUrl": dataset["sourceUrl"],
        "sourceName": "data.gov.in",
        "nameKey": name_key(name),
    }
