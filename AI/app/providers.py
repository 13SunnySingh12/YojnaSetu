"""Gemini (embeddings + primary generation) and Groq (generation fallback) over their REST APIs."""
import logging
import math
import time

import httpx

from . import config

log = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
EMBED_BATCH_SIZE = 50
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

http = httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0))


class ProviderError(Exception):
    """A provider call failed. Messages never contain credentials (keys travel in headers only)."""


def embed_query(text: str) -> list[float]:
    return _embed([(None, text)], query=True, attempts=2)[0]


def embed_documents(docs: list[tuple[str, str]]) -> list[list[float]]:
    """Embeds (title, text) pairs for storage; retries harder because ingestion is not user-facing."""
    return _embed(docs, query=False, attempts=5)


def generate(system: str, prompt: str, max_tokens: int = 512) -> tuple[str, str]:
    """Returns (text, provider). Gemini first; Groq when Gemini is unconfigured or fails."""
    errors = []
    for name, key, call in (
        ("gemini", config.GEMINI_API_KEY, _gemini_generate),
        ("groq", config.GROQ_API_KEY, _groq_generate),
    ):
        if not key:
            continue
        try:
            return call(system, prompt, max_tokens), name
        except ProviderError as exc:
            log.warning("%s generation failed: %s", name, exc)
            errors.append(f"{name}: {exc}")
    raise ProviderError("; ".join(errors) or "no LLM provider is configured")


def _embed(docs: list[tuple[str | None, str]], query: bool, attempts: int) -> list[list[float]]:
    if not config.GEMINI_API_KEY:
        raise ProviderError("GEMINI_API_KEY is not configured")
    model = config.GEMINI_EMBEDDING_MODEL
    # gemini-embedding-001 takes a taskType; newer models take the task as a text prefix instead.
    legacy = model.startswith("gemini-embedding-001")
    vectors = []
    for start in range(0, len(docs), EMBED_BATCH_SIZE):
        requests = []
        for title, text in docs[start:start + EMBED_BATCH_SIZE]:
            request = {"model": f"models/{model}", "outputDimensionality": config.EMBEDDING_DIMENSIONS}
            if legacy:
                request["taskType"] = "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT"
                if title:
                    request["title"] = title
            elif query:
                text = f"task: search result | query: {text}"
            else:
                text = f"title: {title or 'none'} | text: {text}"
            request["content"] = {"parts": [{"text": text}]}
            requests.append(request)
        data = _post(
            f"{GEMINI_BASE}/models/{model}:batchEmbedContents",
            {"x-goog-api-key": config.GEMINI_API_KEY},
            {"requests": requests},
            attempts,
        )
        embeddings = data.get("embeddings") or []
        if len(embeddings) != len(requests):
            raise ProviderError(f"expected {len(requests)} embeddings, got {len(embeddings)}")
        vectors.extend(_unit_vector(e.get("values") or []) for e in embeddings)
    return vectors


def _unit_vector(values: list[float]) -> list[float]:
    if len(values) != config.EMBEDDING_DIMENSIONS:
        raise ProviderError(f"embedding has {len(values)} dimensions, expected {config.EMBEDDING_DIMENSIONS}")
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        raise ProviderError("embedding is a zero vector")
    return [v / norm for v in values]


def _gemini_generate(system: str, prompt: str, max_tokens: int) -> str:
    data = _post(
        f"{GEMINI_BASE}/models/{config.GEMINI_CHAT_MODEL}:generateContent",
        {"x-goog-api-key": config.GEMINI_API_KEY},
        {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
        },
        attempts=1,  # the Groq fallback is the retry for user-facing calls
    )
    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or (
            candidates[0].get("finishReason") if candidates else "no candidates")
        raise ProviderError(f"empty Gemini response ({reason})")
    return text


def _groq_generate(system: str, prompt: str, max_tokens: int) -> str:
    data = _post(
        GROQ_CHAT_URL,
        {"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        {
            "model": config.GROQ_CHAT_MODEL,
            "temperature": 0.2,
            "max_completion_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        },
        attempts=1,
    )
    choices = data.get("choices") or []
    text = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
    if not text:
        raise ProviderError("empty Groq response")
    return text


def _post(url: str, headers: dict, body: dict, attempts: int) -> dict:
    """POST with bounded retries on rate limits, server errors and transport failures only."""
    error = "no attempt made"
    for attempt in range(1, attempts + 1):
        wait = 2 ** attempt
        try:
            resp = http.post(url, headers=headers, json=body)
        except httpx.TransportError as exc:
            error = f"{type(exc).__name__} calling provider"
        else:
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError:
                    raise ProviderError("provider returned invalid JSON") from None
            error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code not in RETRYABLE_STATUS:
                raise ProviderError(error)
            retry_after = resp.headers.get("retry-after", "")
            if retry_after.isdigit():
                wait = int(retry_after)
        if attempt < attempts:
            time.sleep(min(wait, 30))
    raise ProviderError(error)
