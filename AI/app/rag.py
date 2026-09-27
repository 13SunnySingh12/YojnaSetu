"""Semantic retrieval over scheme chunks and answers grounded only in retrieved official text."""
from functools import lru_cache

from . import config, providers
from .db import get_db

VECTOR_INDEX = "chunk_vectors"
CONTEXT_CHUNKS = 6
NO_ANSWER = "NOT_IN_CONTEXT"
NOT_FOUND_MESSAGE = ("This information was not found in the stored scheme data. "
                     "Please check the official source for the scheme.")

ASK_SYSTEM = f"""You answer questions about Indian government schemes for ordinary citizens.
Rules:
- Use ONLY the scheme text inside <context>. Do not use any other knowledge.
- If the context does not contain the answer, reply exactly: {NO_ANSWER}
- Never invent or guess benefits, amounts, dates, deadlines, documents, eligibility rules or application steps.
- Answer in 2 to 5 short, simple sentences and name the scheme the answer comes from.
- Never say that someone is eligible or approved: the concerned government department decides that."""

EXPLAIN_SYSTEM = f"""You rewrite official Indian government scheme text in simple language for a citizen with basic reading skills.
Rules:
- Use ONLY the given text. Do not add, remove or change any fact, number, date, condition or document.
- Use short sentences and everyday words; explain terms such as "domicile" or "BPL" in plain words.
- Use a short bulleted list when there are several points.
- If the text is empty or unclear, reply exactly: {NO_ANSWER}"""

ELIGIBILITY_SYSTEM = """You explain the result of an automatic eligibility check in one or two short, simple sentences.
Rules:
- Use ONLY the conditions listed. Do not add conditions, facts or advice.
- Never say that the person is eligible or approved. Say what matched, what did not, and what is missing.
- Use plain everyday language."""

STATUS_WORDS = {"LIKELY_MATCH": "Likely match", "NOT_A_MATCH": "Not a match",
                "MORE_INFO_NEEDED": "More information needed"}


def vector_search(query_vector: list[float], limit: int, filter: dict | None = None) -> list[dict]:
    """Nearest chunks, best first, each with its Atlas vectorSearchScore."""
    stage = {"index": VECTOR_INDEX, "path": "embedding", "queryVector": query_vector,
             "numCandidates": max(limit * 20, 100), "limit": limit}
    if filter:
        stage["filter"] = filter
    return list(get_db().scheme_chunks.aggregate([
        {"$vectorSearch": stage},
        {"$project": {"schemeId": 1, "schemeName": 1, "section": 1, "text": 1,
                      "score": {"$meta": "vectorSearchScore"}}},
    ]))


def _best_per_scheme(hits: list[dict], limit: int) -> list[dict]:
    best: dict[str, float] = {}
    for hit in hits:  # already sorted best first
        if hit["score"] >= config.RETRIEVAL_MIN_SCORE and hit["schemeId"] not in best:
            best[hit["schemeId"]] = hit["score"]
    return [{"schemeId": scheme_id, "score": score} for scheme_id, score in list(best.items())[:limit]]


def semantic_search(query: str, limit: int) -> list[dict]:
    """Schemes whose text is closest in meaning to the query."""
    return _best_per_scheme(vector_search(providers.embed_query(query), limit * 4), limit)


def related_schemes(scheme_id: str, limit: int) -> list[dict]:
    """Schemes whose overview is closest to this scheme's overview."""
    anchor = get_db().scheme_chunks.find_one({"_id": f"{scheme_id}#overview#0"}, {"embedding": 1})
    if not anchor:
        return []
    hits = vector_search(anchor["embedding"], limit * 4,
                         {"schemeId": {"$ne": scheme_id}, "section": "overview"})
    return _best_per_scheme(hits, limit)


def answer(question: str, scheme_id: str | None = None) -> dict:
    """RAG: retrieve relevant official text, then let the LLM answer from that text only."""
    filter = {"schemeId": scheme_id} if scheme_id else None
    hits = [h for h in vector_search(providers.embed_query(question), CONTEXT_CHUNKS, filter)
            if h["score"] >= config.RETRIEVAL_MIN_SCORE]
    if not hits:  # no evidence: never ask the model, so nothing can be made up
        return {"answer": NOT_FOUND_MESSAGE, "grounded": False, "sources": [], "provider": None}
    context = "\n\n".join(f"[{h['schemeName']} - {h['section']}]\n{h['text']}" for h in hits)
    text, provider = providers.generate(
        ASK_SYSTEM, f"<context>\n{context}\n</context>\n\nQuestion: {question}", max_tokens=400)
    grounded = NO_ANSWER not in text
    return {"answer": text if grounded else NOT_FOUND_MESSAGE, "grounded": grounded,
            "sources": _sources([h["schemeId"] for h in hits]), "provider": provider}


@lru_cache(maxsize=256)
def explain(scheme_name: str, section: str, text: str) -> tuple[str | None, str]:
    """Plain-language version of one official section; identical requests reuse the first answer."""
    result, provider = providers.generate(
        EXPLAIN_SYSTEM, f"Scheme: {scheme_name}\nSection: {section}\n\nOfficial text:\n{text}", max_tokens=500)
    return (None if NO_ANSWER in result else result), provider


def explain_eligibility(scheme_name: str, status: str, matched: list[dict], unmatched: list[dict],
                        missing: list[dict]) -> tuple[str, str]:
    def lines(conditions: list[dict]) -> str:
        return "\n".join(f"- {c['requirement']}" + (f" (your answer: {c['yourValue']})" if c.get("yourValue") else "")
                         for c in conditions) or "- none"
    prompt = (f"Scheme: {scheme_name}\nResult: {STATUS_WORDS[status]}\n"
              f"Conditions that matched:\n{lines(matched)}\nConditions that did not match:\n{lines(unmatched)}\n"
              f"Information not provided:\n{lines(missing)}")
    return providers.generate(ELIGIBILITY_SYSTEM, prompt, max_tokens=150)


def _sources(scheme_ids: list[str]) -> list[dict]:
    """Source names and links come from the stored records, never from model output."""
    ordered = list(dict.fromkeys(scheme_ids))
    found = {d["_id"]: d for d in get_db().schemes.find({"_id": {"$in": ordered}}, {"name": 1, "sourceUrl": 1})}
    return [{"schemeId": i, "name": found[i]["name"], "sourceUrl": found[i]["sourceUrl"]} for i in ordered if i in found]
