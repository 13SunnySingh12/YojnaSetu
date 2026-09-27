import hmac
import logging

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException

from . import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Only the Spring Boot backend may call this service. Fails closed when no token is configured."""
    expected = config.AI_SERVICE_TOKEN
    if not expected or not x_internal_token or not hmac.compare_digest(
            x_internal_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI(title="YojnaSetu AI service", docs_url=None, redoc_url=None, openapi_url=None)
api = APIRouter(dependencies=[Depends(require_internal_token)])


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(api)
