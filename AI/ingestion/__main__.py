"""Loads official scheme data into MongoDB.

    python -m ingestion setup                      create collections, validator and indexes
    python -m ingestion myscheme [--limit N] [--slug SLUG ...]
    python -m ingestion ogd                        datasets listed in ogd_datasets.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from pymongo import MongoClient

from app import config
from app.upstream import UpstreamError

from . import sources, store

log = logging.getLogger("ingestion")
BATCH_SIZE = 25


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m ingestion", description="Load official scheme data.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="create collections, validator and indexes")
    myscheme = commands.add_parser("myscheme", help="official myScheme API on API Setu")
    myscheme.add_argument("--limit", type=int, help="ingest at most N schemes (no pruning)")
    myscheme.add_argument("--slug", action="append", help="ingest only this scheme slug (repeatable)")
    commands.add_parser("ogd", help="data.gov.in datasets listed in ogd_datasets.json")
    args = parser.parse_args(argv)

    if not config.MONGODB_URI:
        sys.exit("MONGODB_URI is not set")
    db = MongoClient(config.MONGODB_URI, appname="yojnasetu-ingestion")[config.MONGODB_DATABASE]
    store.ensure_schema(db)
    if args.command == "myscheme":
        run_myscheme(db, args.limit, args.slug)
    elif args.command == "ogd":
        run_ogd(db)
    store.wait_for_vector_index(db)
    log.info("done")


def run_myscheme(db, limit: int | None, slugs: list[str] | None) -> None:
    if not (config.APISETU_CLIENT_ID and config.APISETU_API_KEY):
        sys.exit("APISETU_CLIENT_ID and APISETU_API_KEY are required for the myScheme API")
    headers = sources.apisetu_headers(config.APISETU_CLIENT_ID, config.APISETU_API_KEY)
    listed = slugs or sources.list_myscheme_slugs(headers, limit)
    log.info("myScheme: %d schemes to fetch", len(listed))
    batch, failures, totals = [], 0, _totals()
    for slug in listed:
        try:
            batch.append(sources.fetch_myscheme_scheme(headers, slug))
            failures = 0
        except UpstreamError as exc:
            totals["fetch_failed"].append((slug, str(exc)))
            log.error("fetch failed for %s: %s", slug, exc)
            failures += 1
            if failures >= 3:  # credentials rejected or API down: keep what was fetched, then stop
                _add(totals, store.store_schemes(db, batch))
                raise
        if len(batch) >= BATCH_SIZE:
            _add(totals, store.store_schemes(db, batch))
            batch = []
    if batch:
        _add(totals, store.store_schemes(db, batch))
    if not slugs and not limit:  # only a complete listing proves a scheme was withdrawn
        stored = db.schemes.count_documents({"sourceName": "myScheme"})
        if listed and len(listed) >= stored // 2:
            totals["pruned"] = store.prune_missing(db, "myScheme", set(listed))
            myscheme_keys = [d["nameKey"] for d in db.schemes.find({"sourceName": "myScheme"}, {"nameKey": 1})]
            totals["ogd_duplicates_removed"] = _remove_ogd_duplicates(db, myscheme_keys)
        else:  # an empty or collapsed listing is far more likely a response change than mass withdrawal
            log.warning("listing returned %d schemes while %d are stored; not pruning", len(listed), stored)
    _report("myScheme", totals)


def run_ogd(db) -> None:
    datasets = json.loads(Path(__file__).with_name("ogd_datasets.json").read_text(encoding="utf-8"))
    if not datasets:
        log.info("no data.gov.in datasets are configured in ogd_datasets.json")
        return
    if not config.DATA_GOV_IN_API_KEY:
        sys.exit("DATA_GOV_IN_API_KEY is required for data.gov.in datasets")
    for dataset in datasets:
        rows = sources.fetch_ogd(dataset["resourceId"], config.DATA_GOV_IN_API_KEY)
        cleaned, checks = sources.clean_ogd_rows(rows, dataset["columns"])
        records, duplicates = [], 0
        for row in cleaned:
            record = sources.map_ogd(dataset, row)
            # The same scheme from myScheme carries full details, so it wins.
            if db.schemes.find_one({"nameKey": record["nameKey"], "sourceName": {"$ne": "data.gov.in"}}, {"_id": 1}):
                duplicates += 1
                continue
            records.append(record)
        totals = _totals()
        _add(totals, store.store_schemes(db, records))
        _report(f"data.gov.in {dataset['resourceId']}", {**totals, **checks, "already_from_myscheme": duplicates})


def _remove_ogd_duplicates(db, name_keys: list[str]) -> int:
    ids = [d["_id"] for d in db.schemes.find({"sourceName": "data.gov.in", "nameKey": {"$in": name_keys}}, {"_id": 1})]
    if ids:
        db.scheme_chunks.delete_many({"schemeId": {"$in": ids}})
        db.schemes.delete_many({"_id": {"$in": ids}})
    return len(ids)


def _totals() -> dict:
    return {"stored": 0, "skipped": [], "failed": [], "fetch_failed": [], "chunks_embedded": 0, "chunks_removed": 0}


def _add(totals: dict, stats: dict) -> None:
    for key, value in stats.items():
        totals[key] = totals.get(key, 0 if isinstance(value, int) else []) + value


def _report(source: str, totals: dict) -> None:
    print(json.dumps({"source": source, **totals}, indent=2, default=str))


if __name__ == "__main__":
    main()
