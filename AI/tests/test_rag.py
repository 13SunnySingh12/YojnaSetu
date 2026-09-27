"""MOCK / TEST ONLY: retrieval hits and model replies below are fakes."""
import pytest

from app import config, providers, rag


def hit(scheme_id, score, section="overview", text="Official text."):
    return {"schemeId": scheme_id, "schemeName": f"Scheme {scheme_id}", "section": section, "text": text,
            "score": score}


@pytest.fixture
def fakes(monkeypatch):
    state = {"hits": [], "reply": "Answer from the context.", "prompts": []}
    # The production threshold is a tuning knob; these tests exercise the logic at a fixed value.
    monkeypatch.setattr(config, "RETRIEVAL_MIN_SCORE", 0.75)
    monkeypatch.setattr(providers, "embed_query", lambda text: [0.1])
    monkeypatch.setattr(rag, "vector_search", lambda vector, limit, filter=None: state["hits"])

    def generate(system, prompt, max_tokens=512):
        state["prompts"].append((system, prompt))
        return state["reply"], "gemini"

    monkeypatch.setattr(providers, "generate", generate)
    monkeypatch.setattr(rag, "_sources", lambda ids: [{"schemeId": i, "name": f"Scheme {i}",
                                                      "sourceUrl": f"https://www.myscheme.gov.in/schemes/{i}"}
                                                     for i in dict.fromkeys(ids)])
    return state


def test_semantic_search_keeps_best_chunk_per_scheme_above_threshold(fakes):
    fakes["hits"] = [hit("a", 0.95), hit("b", 0.9), hit("a", 0.85), hit("c", 0.6)]
    assert rag.semantic_search("school fees", 10) == [{"schemeId": "a", "score": 0.95}, {"schemeId": "b", "score": 0.9}]


def test_no_relevant_evidence_returns_not_found_without_calling_the_model(fakes):
    fakes["hits"] = [hit("a", 0.5)]
    result = rag.answer("What is the pension amount?")
    assert result == {"answer": rag.NOT_FOUND_MESSAGE, "grounded": False, "sources": [], "provider": None}
    assert fakes["prompts"] == []


def test_answer_is_built_only_from_retrieved_text_and_cites_stored_sources(fakes):
    fakes["hits"] = [hit("a", 0.9, "benefits", "Rs 1000 per month."), hit("b", 0.8)]
    result = rag.answer("How much money?")
    system, prompt = fakes["prompts"][0]
    assert system == rag.ASK_SYSTEM
    assert "<context>" in prompt and "Rs 1000 per month." in prompt and "Question: How much money?" in prompt
    assert result["grounded"] is True and result["answer"] == "Answer from the context."
    assert [s["schemeId"] for s in result["sources"]] == ["a", "b"]


def test_model_saying_not_in_context_becomes_the_fixed_not_found_answer(fakes):
    fakes["hits"] = [hit("a", 0.9)]
    fakes["reply"] = "NOT_IN_CONTEXT"
    result = rag.answer("Unrelated question?")
    assert result["grounded"] is False and result["answer"] == rag.NOT_FOUND_MESSAGE
    assert result["sources"][0]["sourceUrl"].startswith("https://www.myscheme.gov.in/")


def test_explain_is_cached_and_refuses_unclear_text(fakes):
    rag.explain.cache_clear()
    assert rag.explain("S", "benefits", "Rs 500.") == ("Answer from the context.", "gemini")
    assert rag.explain("S", "benefits", "Rs 500.") == ("Answer from the context.", "gemini")
    assert len(fakes["prompts"]) == 1
    fakes["reply"] = "NOT_IN_CONTEXT"
    assert rag.explain("S", "benefits", "???")[0] is None
    rag.explain.cache_clear()


def test_eligibility_explanation_prompt_lists_only_the_engine_conditions(fakes):
    rag.explain_eligibility("Test Scheme", "MORE_INFO_NEEDED",
                            [{"requirement": "State: Bihar", "yourValue": "Bihar"}], [],
                            [{"requirement": "Annual family income up to Rs 2,50,000", "yourValue": None}])
    system, prompt = fakes["prompts"][0]
    assert system == rag.ELIGIBILITY_SYSTEM
    assert "Result: More information needed" in prompt
    assert "- State: Bihar (your answer: Bihar)" in prompt
    assert "Conditions that did not match:\n- none" in prompt
