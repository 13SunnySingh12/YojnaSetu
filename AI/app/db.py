from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from . import config


@lru_cache(maxsize=1)
def get_db() -> Database:
    if not config.MONGODB_URI:
        raise RuntimeError("MONGODB_URI is not set")
    client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000, appname="yojnasetu-ai")
    return client[config.MONGODB_DATABASE]
