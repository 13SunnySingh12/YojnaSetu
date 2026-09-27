import hmac
import logging
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from . import config, rag
from .upstream import UpstreamError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("ai-service")

SCHEME_ID = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"


def require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Only the Spring Boot backend may call this service. Fails closed when no token is configured."""
    expected = config.AI_SERVICE_TOKEN
    if not expected or not x_internal_token or not hmac.compare_digest(
            x_internal_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI(title="YojnaSetu AI service", docs_url=None, redoc_url=None, openapi_url=None)
api = APIRouter(dependencies=[Depends(require_internal_token)])


@app.exception_handler(UpstreamError)
def provider_unavailable(request: Request, exc: UpstreamError) -> JSONResponse:
    log.warning("provider failure on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "AI provider unavailable"})


@app.exception_handler(PyMongoError)
def database_unavailable(request: Request, exc: PyMongoError) -> JSONResponse:
    log.error("database failure on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(20, ge=1, le=50)


class RelatedIn(BaseModel):
    schemeId: str = Field(pattern=SCHEME_ID)
    limit: int = Field(5, ge=1, le=20)


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    schemeId: str | None = Field(None, pattern=SCHEME_ID)


class ExplainIn(BaseModel):
    schemeName: str = Field(min_length=1, max_length=300)
    section: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=20000)


class Condition(BaseModel):
    field: str = Field(max_length=40)
    requirement: str = Field(max_length=500)
    yourValue: str | None = Field(None, max_length=200)


class EligibilityExplainIn(BaseModel):
    schemeName: str = Field(min_length=1, max_length=300)
    status: Literal["LIKELY_MATCH", "NOT_A_MATCH", "MORE_INFO_NEEDED"]
    matched: list[Condition] = Field(default_factory=list, max_length=20)
    unmatched: list[Condition] = Field(default_factory=list, max_length=20)
    missing: list[Condition] = Field(default_factory=list, max_length=20)


@api.post("/search")
def search(body: SearchIn) -> dict:
    return {"results": rag.semantic_search(body.query, body.limit)}


@api.post("/related")
def related(body: RelatedIn) -> dict:
    return {"results": rag.related_schemes(body.schemeId, body.limit)}


@api.post("/ask")
def ask(body: AskIn) -> dict:
    return rag.answer(body.question.strip(), body.schemeId)


@api.post("/explain")
def explain(body: ExplainIn) -> dict:
    explanation, provider = rag.explain(body.schemeName, body.section, body.text)
    return {"explanation": explanation, "provider": provider}


@api.post("/explain-eligibility")
def explain_eligibility(body: EligibilityExplainIn) -> dict:
    text, provider = rag.explain_eligibility(
        body.schemeName, body.status, [c.model_dump() for c in body.matched],
        [c.model_dump() for c in body.unmatched], [c.model_dump() for c in body.missing])
    return {"explanation": text, "provider": provider}


app.include_router(api)
