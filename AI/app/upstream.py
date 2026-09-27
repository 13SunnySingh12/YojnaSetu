"""The one HTTP client for external services (AI providers, government data APIs)."""
import logging
from time import sleep

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# httpx logs full request URLs at INFO; data.gov.in requires its API key in the query string.
logging.getLogger("httpx").setLevel(logging.WARNING)

client = httpx.Client(timeout=httpx.Timeout(30.0, connect=5.0))


class UpstreamError(Exception):
    """An external call failed. Messages never contain URLs or credentials."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def request_json(method: str, url: str, *, headers: dict | None = None, params: dict | None = None,
                 json: dict | None = None, attempts: int = 1, timeout: float = 30.0) -> dict:
    """Bounded retries on rate limits, server errors and transport failures only."""
    error = UpstreamError("no attempt made")
    for attempt in range(1, attempts + 1):
        wait = 2 ** attempt
        try:
            resp = client.request(method, url, headers=headers, params=params, json=json,
                                  timeout=httpx.Timeout(timeout, connect=5.0))
        except httpx.TransportError as exc:
            error = UpstreamError(f"{type(exc).__name__} calling upstream service")
        else:
            if resp.status_code < 400:
                try:
                    return resp.json()
                except ValueError:
                    raise UpstreamError("upstream service returned invalid JSON", resp.status_code) from None
            error = UpstreamError(f"HTTP {resp.status_code}: {resp.text[:200]}", resp.status_code)
            if resp.status_code not in RETRYABLE_STATUS:
                raise error
            retry_after = resp.headers.get("retry-after", "")
            if retry_after.isdigit():
                wait = int(retry_after)
        if attempt < attempts:
            sleep(min(wait, 30))
    raise error
