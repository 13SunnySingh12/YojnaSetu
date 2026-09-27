from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import config
from app.main import app, require_internal_token

guarded = FastAPI()


@guarded.get("/guarded", dependencies=[Depends(require_internal_token)])
def guarded_route():
    return {"ok": True}


def test_health_needs_no_token():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_guard_fails_closed_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(config, "AI_SERVICE_TOKEN", None)
    client = TestClient(guarded)
    assert client.get("/guarded", headers={"X-Internal-Token": "anything"}).status_code == 401
    assert client.get("/guarded").status_code == 401


def test_guard_rejects_wrong_or_missing_token(monkeypatch):
    monkeypatch.setattr(config, "AI_SERVICE_TOKEN", "s3cret-test-token")
    client = TestClient(guarded)
    assert client.get("/guarded").status_code == 401
    assert client.get("/guarded", headers={"X-Internal-Token": "wrong"}).status_code == 401


def test_guard_accepts_the_configured_token(monkeypatch):
    monkeypatch.setattr(config, "AI_SERVICE_TOKEN", "s3cret-test-token")
    response = TestClient(guarded).get("/guarded", headers={"X-Internal-Token": "s3cret-test-token"})
    assert response.status_code == 200
