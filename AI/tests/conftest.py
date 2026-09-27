import hashlib
import os
import random
import uuid

import pytest
from pymongo import MongoClient

from app import config

TEST_MONGODB_URI = os.environ.get("TEST_MONGODB_URI", "mongodb://localhost:27018/?directConnection=true")


def fake_vector(text: str) -> list[float]:
    """MOCK / TEST ONLY: deterministic pseudo-embedding; carries no meaning."""
    rng = random.Random(hashlib.sha256(text.encode()).digest())
    values = [rng.gauss(0, 1) for _ in range(config.EMBEDDING_DIMENSIONS)]
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values]


class FakeEmbedder:
    """MOCK / TEST ONLY: records calls instead of contacting Gemini."""

    def __init__(self):
        self.calls = []

    def __call__(self, docs):
        self.calls.append(docs)
        return [fake_vector(text) for _, text in docs]


@pytest.fixture
def test_db():
    """A throwaway database on the local Atlas container (docker compose up -d mongodb)."""
    client = MongoClient(TEST_MONGODB_URI, serverSelectionTimeoutMS=3000)
    name = f"yojnasetu_test_{uuid.uuid4().hex[:8]}"
    yield client[name]
    client.drop_database(name)
    client.close()
