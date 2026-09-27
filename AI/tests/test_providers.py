"""MOCK / TEST ONLY: every provider response in this file is a fake built for unit tests."""
import json

import httpx
import pytest

from app import config, providers, upstream

DIM = config.EMBEDDING_DIMENSIONS


def vec(*head):
    return list(head) + [0.0] * (DIM - len(head))


@pytest.fixture
def fake(monkeypatch):
    """Routes requests by URL prefix to handler functions; records every request."""
    state = {"calls": [], "routes": {}, "sleeps": []}

    def handler(request):
        state["calls"].append(request)
        for prefix, respond in state["routes"].items():
            if str(request.url).startswith(prefix):
                return respond(request)
        return httpx.Response(404, json={"error": "no fake route"})

    monkeypatch.setattr(upstream, "client", httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(upstream, "sleep", state["sleeps"].append)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setattr(config, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(config, "GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
    return state


EMBED_URL = f"{providers.GEMINI_BASE}/models/gemini-embedding-2:batchEmbedContents"
GEN_URL = f"{providers.GEMINI_BASE}/models/{config.GEMINI_CHAT_MODEL}:generateContent"


def embeddings_for(request, values=None):
    n = len(json.loads(request.content)["requests"])
    return httpx.Response(200, json={"embeddings": [{"values": values or vec(3.0, 4.0)} for _ in range(n)]})


def test_embed_query_sends_task_prefix_and_returns_unit_vector(fake):
    fake["routes"][EMBED_URL] = embeddings_for
    result = providers.embed_query("school fees help")

    request = fake["calls"][0]
    body = json.loads(request.content)["requests"][0]
    assert request.headers["x-goog-api-key"] == "test-gemini-key"
    assert "key=" not in str(request.url)
    assert body["model"] == "models/gemini-embedding-2"
    assert body["outputDimensionality"] == DIM
    assert body["content"]["parts"][0]["text"] == "task: search result | query: school fees help"
    assert "taskType" not in body
    assert result[:2] == pytest.approx([0.6, 0.8]) and len(result) == DIM


def test_embed_documents_batches_and_includes_titles(fake):
    fake["routes"][EMBED_URL] = embeddings_for
    docs = [(f"Scheme {i}", f"text {i}") for i in range(120)]
    result = providers.embed_documents(docs)

    sizes = [len(json.loads(c.content)["requests"]) for c in fake["calls"]]
    assert sizes == [50, 50, 20]
    first = json.loads(fake["calls"][0].content)["requests"][0]
    assert first["content"]["parts"][0]["text"] == "title: Scheme 0 | text: text 0"
    assert len(result) == 120


def test_legacy_embedding_model_uses_task_type(fake, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
    fake["routes"][f"{providers.GEMINI_BASE}/models/gemini-embedding-001:batchEmbedContents"] = embeddings_for
    providers.embed_documents([("PM Scheme", "plain text")])

    body = json.loads(fake["calls"][0].content)["requests"][0]
    assert body["taskType"] == "RETRIEVAL_DOCUMENT"
    assert body["title"] == "PM Scheme"
    assert body["content"]["parts"][0]["text"] == "plain text"


def test_wrong_dimension_embedding_is_rejected(fake):
    fake["routes"][EMBED_URL] = lambda r: embeddings_for(r, values=[1.0] * 10)
    with pytest.raises(upstream.UpstreamError, match="10 dimensions"):
        providers.embed_query("x")


def test_missing_embedding_count_is_rejected(fake):
    fake["routes"][EMBED_URL] = lambda r: httpx.Response(200, json={"embeddings": []})
    with pytest.raises(upstream.UpstreamError, match="expected 1 embeddings"):
        providers.embed_query("x")


def test_rate_limit_honours_retry_after_then_succeeds(fake):
    replies = iter([httpx.Response(429, headers={"retry-after": "7"}, text="slow down")])
    fake["routes"][EMBED_URL] = lambda r: next(replies, None) or embeddings_for(r)
    providers.embed_documents([("t", "x")])
    assert len(fake["calls"]) == 2
    assert fake["sleeps"] == [7]


def test_non_retryable_error_is_not_retried(fake):
    fake["routes"][EMBED_URL] = lambda r: httpx.Response(400, text="bad request")
    with pytest.raises(upstream.UpstreamError, match="HTTP 400"):
        providers.embed_documents([("t", "x")])
    assert len(fake["calls"]) == 1


def test_generate_prefers_gemini(fake):
    fake["routes"][GEN_URL] = lambda r: httpx.Response(200, json={
        "candidates": [{"content": {"parts": [{"text": " Simple answer. "}]}, "finishReason": "STOP"}]})
    text, provider = providers.generate("system rules", "question")

    body = json.loads(fake["calls"][0].content)
    assert (text, provider) == ("Simple answer.", "gemini")
    assert body["systemInstruction"]["parts"][0]["text"] == "system rules"
    assert body["contents"][0]["parts"][0]["text"] == "question"


def test_generate_falls_back_to_groq_when_gemini_fails(fake):
    fake["routes"][GEN_URL] = lambda r: httpx.Response(503, text="overloaded")
    fake["routes"][providers.GROQ_CHAT_URL] = lambda r: httpx.Response(200, json={
        "choices": [{"message": {"content": "Groq answer."}, "finish_reason": "stop"}]})
    text, provider = providers.generate("system rules", "question")

    groq_request = fake["calls"][-1]
    body = json.loads(groq_request.content)
    assert (text, provider) == ("Groq answer.", "groq")
    assert groq_request.headers["authorization"] == "Bearer test-groq-key"
    assert body["messages"][0] == {"role": "system", "content": "system rules"}
    assert body["model"] == config.GROQ_CHAT_MODEL


def test_generate_falls_back_when_gemini_blocks_the_prompt(fake):
    fake["routes"][GEN_URL] = lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})
    fake["routes"][providers.GROQ_CHAT_URL] = lambda r: httpx.Response(200, json={
        "choices": [{"message": {"content": "ok"}}]})
    assert providers.generate("s", "p")[1] == "groq"


def test_generate_uses_groq_alone_when_gemini_is_not_configured(fake, monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    fake["routes"][providers.GROQ_CHAT_URL] = lambda r: httpx.Response(200, json={
        "choices": [{"message": {"content": "ok"}}]})
    assert providers.generate("s", "p") == ("ok", "groq")
    assert len(fake["calls"]) == 1


def test_generate_raises_when_every_provider_fails_without_leaking_keys(fake):
    fake["routes"][GEN_URL] = lambda r: httpx.Response(500, text="boom")
    fake["routes"][providers.GROQ_CHAT_URL] = lambda r: httpx.Response(401, text="invalid api key")
    with pytest.raises(upstream.UpstreamError) as info:
        providers.generate("s", "p")
    message = str(info.value)
    assert "gemini: HTTP 500" in message and "groq: HTTP 401" in message
    assert "test-gemini-key" not in message and "test-groq-key" not in message


def test_generate_raises_when_nothing_is_configured(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "GROQ_API_KEY", None)
    with pytest.raises(upstream.UpstreamError, match="no LLM provider"):
        providers.generate("s", "p")


def test_transport_failure_is_retried_for_ingestion_but_not_for_user_queries(fake):
    def fail(request):
        raise httpx.ConnectTimeout("timed out", request=request)
    fake["routes"][EMBED_URL] = fail
    with pytest.raises(upstream.UpstreamError, match="ConnectTimeout"):
        providers.embed_documents([("t", "x")])
    assert len(fake["calls"]) == 5
    with pytest.raises(upstream.UpstreamError):
        providers.embed_query("x")
    assert len(fake["calls"]) == 6
