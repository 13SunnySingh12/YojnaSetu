"""Validates scheme records, stores them in MongoDB and keeps their chunk embeddings current."""
import hashlib
import logging
import re
import time
from datetime import datetime, timezone

from pymongo import ReplaceOne
from pymongo.database import Database
from pymongo.operations import SearchIndexModel

from app import config, providers
from app.upstream import UpstreamError

log = logging.getLogger(__name__)

# Official Indian government hosts only: *.gov.in or *.nic.in over https.
OFFICIAL_URL_PATTERN = r"^https://([a-z0-9-]+\.)*(gov|nic)\.in(/|$)"
OFFICIAL_URL = re.compile(OFFICIAL_URL_PATTERN)
SCHEME_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")

VECTOR_INDEX = "chunk_vectors"
MAX_CHUNK_CHARS = 1500
# (section, record fields joined into that section's text). "overview" always exists.
SECTIONS = [
    ("overview", ("description", "details")),
    ("eligibility", ("eligibilityText",)),
    ("benefits", ("benefits",)),
    ("documents", ("documents",)),
    ("application", ("applicationProcess",)),
    ("conditions", ("conditions",)),
]

SCHEME_VALIDATOR = {"$jsonSchema": {
    "bsonType": "object",
    "required": ["_id", "name", "sourceUrl", "sourceName"],
    "properties": {
        "_id": {"bsonType": "string", "minLength": 1},
        "name": {"bsonType": "string", "minLength": 1},
        "sourceUrl": {"bsonType": "string", "pattern": OFFICIAL_URL_PATTERN},
        "sourceName": {"bsonType": "string", "minLength": 1},
    },
}}


def ensure_schema(db: Database) -> None:
    """Idempotently creates collections, the source-URL validator and all indexes."""
    names = db.list_collection_names()
    if "schemes" in names:
        db.command("collMod", "schemes", validator=SCHEME_VALIDATOR)
    else:
        db.create_collection("schemes", validator=SCHEME_VALIDATOR)
    if "scheme_chunks" not in names:
        db.create_collection("scheme_chunks")

    db.schemes.create_index(
        [("name", "text"), ("shortTitle", "text"), ("tags", "text"), ("categories", "text"),
         ("description", "text")],
        weights={"name": 10, "shortTitle": 8, "tags": 5, "categories": 3, "description": 2},
        default_language="english", name="scheme_text")
    db.schemes.create_index("categories")
    db.schemes.create_index("state")
    db.schemes.create_index("nameKey")
    db.scheme_chunks.create_index("schemeId")
    if not list(db.scheme_chunks.list_search_indexes(VECTOR_INDEX)):
        db.scheme_chunks.create_search_index(SearchIndexModel(name=VECTOR_INDEX, type="vectorSearch", definition={
            "fields": [
                {"type": "vector", "path": "embedding", "numDimensions": config.EMBEDDING_DIMENSIONS,
                 "similarity": "cosine"},
                {"type": "filter", "path": "schemeId"},
                {"type": "filter", "path": "section"},
            ]}))


def wait_for_vector_index(db: Database, timeout: float = 300) -> None:
    deadline = time.monotonic() + timeout
    while True:
        index = next(iter(db.scheme_chunks.list_search_indexes(VECTOR_INDEX)), None)
        if index and index.get("queryable"):
            return
        if time.monotonic() > deadline:
            raise TimeoutError(f"vector index not queryable after {timeout}s: {index}")
        time.sleep(2)


def validate(record: dict) -> str | None:
    """Returns why a record cannot be published, or None when it is valid."""
    if not SCHEME_ID.match(str(record.get("_id") or "")):
        return "invalid or missing id"
    if not str(record.get("name") or "").strip():
        return "missing scheme name"
    if not OFFICIAL_URL.match(str(record.get("sourceUrl") or "")):
        return "missing or non-official source URL"
    if not str(record.get("sourceName") or "").strip():
        return "missing source name"
    return None


def split_text(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Packs paragraphs (then sentences, then hard cuts) into pieces of at most `limit` characters."""
    units = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        paragraph = paragraph.strip()
        if len(paragraph) <= limit:
            units.append(paragraph)
            continue
        for sentence in re.split(r"(?<=[.!?])\s+|\n", paragraph):
            units.extend(sentence[i:i + limit] for i in range(0, len(sentence), limit))
    pieces, current = [], ""
    for unit in filter(None, units):
        if current and len(current) + 2 + len(unit) > limit:
            pieces.append(current)
            current = unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    return pieces + [current] if current else pieces


def build_chunks(record: dict) -> list[dict]:
    chunks = []
    faq_text = "\n\n".join(f"Q: {f['question']}\nA: {f['answer']}" for f in record.get("faqs") or [])
    sections = SECTIONS + [("faq", ())]
    for section, fields in sections:
        text = faq_text if section == "faq" else "\n\n".join(str(record[f]) for f in fields if record.get(f))
        if section == "overview":
            text = f"{record['name']}\n\n{text}".strip()
        for i, piece in enumerate(split_text(text)):
            title = f"{record['name']} - {section}"
            digest = hashlib.sha256(f"{config.GEMINI_EMBEDDING_MODEL}\n{title}\n{piece}".encode()).hexdigest()
            chunks.append({"_id": f"{record['_id']}#{section}#{i}", "schemeId": record["_id"],
                           "schemeName": record["name"], "section": section, "title": title,
                           "text": piece, "hash": digest})
    return chunks


def store_schemes(db: Database, records: list[dict], embed=None) -> dict:
    """Upserts valid records and embeds only chunks whose content changed. Returns run statistics."""
    embed = embed or providers.embed_documents
    stats = {"stored": 0, "skipped": [], "failed": [], "chunks_embedded": 0, "chunks_removed": 0}
    now = datetime.now(timezone.utc)
    consecutive_failures = 0
    for record in records:
        problem = validate(record)
        if problem:
            stats["skipped"].append((record.get("_id") or record.get("name"), problem))
            log.warning("skipped %s: %s", record.get("_id") or record.get("name"), problem)
            continue
        db.schemes.replace_one({"_id": record["_id"]}, {**record, "syncedAt": now}, upsert=True)
        stats["stored"] += 1

        chunks = build_chunks(record)
        existing = {c["_id"]: c["hash"] for c in db.scheme_chunks.find({"schemeId": record["_id"]}, {"hash": 1})}
        changed = [c for c in chunks if existing.get(c["_id"]) != c["hash"]]
        if changed:
            # A chunk is written only together with its embedding, so a failed run is simply re-run.
            try:
                vectors = embed([(c["title"], c["text"]) for c in changed])
            except UpstreamError as exc:
                stats["failed"].append((record["_id"], str(exc)))
                log.error("embedding failed for %s: %s", record["_id"], exc)
                consecutive_failures += 1
                if consecutive_failures >= 3:  # quota exhausted or provider down: stop burning requests
                    raise
                continue
            consecutive_failures = 0
            db.scheme_chunks.bulk_write(
                [ReplaceOne({"_id": c["_id"]}, {**c, "embedding": v}, upsert=True) for c, v in zip(changed, vectors)])
            stats["chunks_embedded"] += len(changed)
        stale = set(existing) - {c["_id"] for c in chunks}
        if stale:
            stats["chunks_removed"] += db.scheme_chunks.delete_many({"_id": {"$in": list(stale)}}).deleted_count
    return stats


def prune_missing(db: Database, source_name: str, seen_ids: set[str]) -> int:
    """After a complete run of one source, removes that source's schemes it no longer publishes."""
    gone = [d["_id"] for d in db.schemes.find({"sourceName": source_name, "_id": {"$nin": list(seen_ids)}}, {"_id": 1})]
    if gone:
        db.scheme_chunks.delete_many({"schemeId": {"$in": gone}})
        db.schemes.delete_many({"_id": {"$in": gone}})
    return len(gone)
