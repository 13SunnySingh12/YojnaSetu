"""Gemini (embeddings + primary generation) and Groq (generation fallback) over their REST APIs."""
import logging
import math

from . import config
from .upstream import UpstreamError, request_json

log = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
EMBED_BATCH_SIZE = 50
GENERATION_TIMEOUT = 15.0


def embed_query(text: str) -> list[float]:
    # One quick attempt: callers degrade (keyword-only search) rather than keep the user waiting.
    return _embed([(None, text)], query=True, attempts=1, timeout=10)[0]


def embed_documents(docs: list[tuple[str, str]]) -> list[list[float]]:
    """Embeds (title, text) pairs for storage; retries harder because ingestion is not user-facing."""
    return _embed(docs, query=False, attempts=5, timeout=60)


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
        except UpstreamError as exc:
            log.warning("%s generation failed: %s", name, exc)
            errors.append(f"{name}: {exc}")
    raise UpstreamError("; ".join(errors) or "no LLM provider is configured")


def _embed(docs: list[tuple[str | None, str]], query: bool, attempts: int, timeout: float) -> list[list[float]]:
    if not config.GEMINI_API_KEY:
        raise UpstreamError("GEMINI_API_KEY is not configured")
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
        data = request_json("POST", f"{GEMINI_BASE}/models/{model}:batchEmbedContents",
                            headers={"x-goog-api-key": config.GEMINI_API_KEY},
                            json={"requests": requests}, attempts=attempts, timeout=timeout)
        embeddings = data.get("embeddings") or []
        if len(embeddings) != len(requests):
            raise UpstreamError(f"expected {len(requests)} embeddings, got {len(embeddings)}")
        vectors.extend(_unit_vector(e.get("values") or []) for e in embeddings)
    return vectors


def _unit_vector(values: list[float]) -> list[float]:
    if len(values) != config.EMBEDDING_DIMENSIONS:
        raise UpstreamError(f"embedding has {len(values)} dimensions, expected {config.EMBEDDING_DIMENSIONS}")
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        raise UpstreamError("embedding is a zero vector")
    return [v / norm for v in values]


def _gemini_generate(system: str, prompt: str, max_tokens: int) -> str:
    data = request_json(
        "POST", f"{GEMINI_BASE}/models/{config.GEMINI_CHAT_MODEL}:generateContent",
        headers={"x-goog-api-key": config.GEMINI_API_KEY},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            # Thinking tokens count against maxOutputTokens; short grounded rewrites do not need them.
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens,
                                 "thinkingConfig": {"thinkingBudget": 0}},
        },
        timeout=GENERATION_TIMEOUT,
    )  # single attempt: the Groq fallback is the retry for user-facing calls
    candidates = data.get("candidates") or []
    parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        reason = (data.get("promptFeedback") or {}).get("blockReason") or (
            candidates[0].get("finishReason") if candidates else "no candidates")
        raise UpstreamError(f"empty Gemini response ({reason})")
    return text


def _groq_generate(system: str, prompt: str, max_tokens: int) -> str:
    data = request_json(
        "POST", GROQ_CHAT_URL,
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json={
            "model": config.GROQ_CHAT_MODEL,
            "temperature": 0.2,
            # gpt-oss reasons before answering and those tokens count against this limit.
            "max_completion_tokens": max_tokens + 512,
            "reasoning_effort": "low",
            "include_reasoning": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        },
        timeout=GENERATION_TIMEOUT,
    )
    choices = data.get("choices") or []
    text = ((choices[0].get("message") or {}).get("content") or "").strip() if choices else ""
    if not text:
        raise UpstreamError("empty Groq response")
    return text
