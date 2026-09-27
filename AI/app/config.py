import os

from dotenv import find_dotenv, load_dotenv

# Local development reads the repo-root .env; real environment variables always win.
load_dotenv(find_dotenv(usecwd=True), override=False)


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, "").strip() or default


MONGODB_URI = _env("MONGODB_URI")
MONGODB_DATABASE = _env("MONGODB_DATABASE", "yojnasetu")

# Shared secret expected from the Spring Boot backend. Unset means every protected call is rejected.
AI_SERVICE_TOKEN = _env("AI_SERVICE_TOKEN")

GEMINI_API_KEY = _env("GEMINI_API_KEY")
GROQ_API_KEY = _env("GROQ_API_KEY")
# Provider model IDs get retired over time, so they stay overridable without a code change.
GEMINI_EMBEDDING_MODEL = _env("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
# Pinned to models verified with live calls (a moving alias changed behaviour under us once).
GEMINI_CHAT_MODEL = _env("GEMINI_CHAT_MODEL", "gemini-3.8-flash")
GROQ_CHAT_MODEL = _env("GROQ_CHAT_MODEL", "openai/gpt-oss-120b")

# Must match numDimensions of the Atlas vector index; changing it means re-embedding everything.
EMBEDDING_DIMENSIONS = 768
# Minimum Atlas vectorSearchScore ((1 + cosine) / 2) for a chunk to count as relevant evidence.
# Measured with gemini-embedding-2 at 768 dims: relevant queries scored 0.845-0.884, unrelated ones
# 0.760-0.776. A tuning knob, so it stays adjustable without a deploy as the corpus grows.
RETRIEVAL_MIN_SCORE = float(_env("RETRIEVAL_MIN_SCORE", "0.81"))

# Government data ingestion credentials (used only by `python -m ingestion`).
APISETU_CLIENT_ID = _env("APISETU_CLIENT_ID")
APISETU_API_KEY = _env("APISETU_API_KEY")
DATA_GOV_IN_API_KEY = _env("DATA_GOV_IN_API_KEY")
