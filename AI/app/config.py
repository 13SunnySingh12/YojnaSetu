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
GEMINI_CHAT_MODEL = _env("GEMINI_CHAT_MODEL", "gemini-flash-latest")
GROQ_CHAT_MODEL = _env("GROQ_CHAT_MODEL", "llama-3.3-70b-versatile")

# Must match numDimensions of the Atlas vector index; changing it means re-embedding everything.
EMBEDDING_DIMENSIONS = 768
