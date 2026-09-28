"""Loads official scheme data into MongoDB.

    python -m ingestion setup       create collections, validator and indexes
    python -m ingestion verified    scheme details checked against official pages (verified_schemes.json)
    python -m ingestion ogd         datasets listed in ogd_datasets.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from pymongo import MongoClient

from app import config

from . import sources, store

log = logging.getLogger("ingestion")
VERIFIED_FILE = Path(__file__).with_name("verified_schemes.json")
OGD_DATASETS_FILE = Path(__file__).with_name("ogd_datasets.json")
# Every record that did not come from data.gov.in was loaded from the verified file.
VERIFIED_SCOPE = {"sourceName": {"$ne": "data.gov.in"}}


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="python -m ingestion", description="Load official scheme data.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="create collections, validator and indexes")
    commands.add_parser("verified", help=f"scheme details checked against official pages ({VERIFIED_FILE.name})")
    commands.add_parser("ogd", help=f"data.gov.in datasets listed in {OGD_DATASETS_FILE.name}")
    args = parser.parse_args(argv)

    if not config.MONGODB_URI:
        sys.exit("MONGODB_URI is not set")
    db = MongoClient(config.MONGODB_URI, appname="yojnasetu-ingestion")[config.MONGODB_DATABASE]
    store.ensure_schema(db)
    if args.command == "verified":
        run_verified(db)
    elif args.command == "ogd":
        run_ogd(db)
    store.wait_for_vector_index(db)
    log.info("done")


def run_verified(db) -> None:
    listed = json.loads(VERIFIED_FILE.read_text(encoding="utf-8"))
    if not listed:
        log.info("no records in %s", VERIFIED_FILE.name)
        return
    records = [sources.verified_record(raw) for raw in listed]
    totals = _totals()
    _add(totals, store.store_schemes(db, records))
    # The file is the complete list, but an invalid entry keeps its last good version.
    seen = {str(r.get("_id")) for r in records}
    stored = db.schemes.count_documents(VERIFIED_SCOPE)
    if len(seen) >= stored // 2:
        totals["pruned"] = store.prune_missing(db, VERIFIED_SCOPE, seen)
    else:  # a mostly emptied file is far more likely a mistake than mass withdrawal
        log.warning("%s lists %d schemes while %d are stored; not pruning", VERIFIED_FILE.name, len(seen), stored)
    verified_keys = [d["nameKey"] for d in db.schemes.find(VERIFIED_SCOPE, {"nameKey": 1})]
    totals["ogd_duplicates_removed"] = _remove_ogd_duplicates(db, verified_keys)
    _report("verified", totals)


def run_ogd(db) -> None:
    datasets = json.loads(OGD_DATASETS_FILE.read_text(encoding="utf-8"))
    if not datasets:
        log.info("no data.gov.in datasets are configured in %s", OGD_DATASETS_FILE.name)
        return
    if not config.DATA_GOV_IN_API_KEY:
        sys.exit("DATA_GOV_IN_API_KEY is required for data.gov.in datasets")
    for dataset in datasets:
        rows = sources.fetch_ogd(dataset["resourceId"], config.DATA_GOV_IN_API_KEY)
        cleaned, checks = sources.clean_ogd_rows(rows, dataset["columns"])
        records, duplicates = [], 0
        for row in cleaned:
            record = sources.map_ogd(dataset, row)
            # A verified record of the same scheme carries full details, so it wins.
            if db.schemes.find_one({**VERIFIED_SCOPE, "nameKey": record["nameKey"]}, {"_id": 1}):
                duplicates += 1
                continue
            records.append(record)
        totals = _totals()
        _add(totals, store.store_schemes(db, records))
        _report(f"data.gov.in {dataset['resourceId']}", {**totals, **checks, "already_verified": duplicates})


def _remove_ogd_duplicates(db, name_keys: list[str]) -> int:
    ids = [d["_id"] for d in db.schemes.find({"sourceName": "data.gov.in", "nameKey": {"$in": name_keys}}, {"_id": 1})]
    if ids:
        db.scheme_chunks.delete_many({"schemeId": {"$in": ids}})
        db.schemes.delete_many({"_id": {"$in": ids}})
    return len(ids)


def _totals() -> dict:
    return {"stored": 0, "skipped": [], "failed": [], "chunks_embedded": 0, "chunks_removed": 0}


def _add(totals: dict, stats: dict) -> None:
    for key, value in stats.items():
        totals[key] = totals.get(key, 0 if isinstance(value, int) else []) + value


def _report(source: str, totals: dict) -> None:
    print(json.dumps({"source": source, **totals}, indent=2, default=str))


if __name__ == "__main__":
    main()
