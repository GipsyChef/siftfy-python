"""Shared helpers for the sync and async clients.

The sync (`Siftfy`) and async (`AsyncSiftfy`) clients differ only in their
HTTP transport. Everything else — URL building, header construction,
response parsing, error mapping, retry timing — is shared here.
"""

from __future__ import annotations

import random
from typing import Any

from siftfy._version import __version__
from siftfy.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
)
from siftfy.models import Prediction

DEFAULT_BASE_URL = "https://api.siftfy.io"
DEFAULT_TIMEOUT = 10.0
DEFAULT_MAX_RETRIES = 2
USER_AGENT = f"siftfy-python/{__version__}"

# Status codes worth retrying. 408 (timeout), 429 (rate limit), 5xx.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


def build_headers(api_key: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "X-API-Key": api_key,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def parse_predict_response(
    status_code: int,
    headers: dict[str, str],
    body: Any,
) -> Prediction:
    """Parse a /v1/predict response and raise on error."""
    request_id = headers.get("x-request-id") or headers.get("X-Request-Id")
    if 200 <= status_code < 300 and isinstance(body, dict):
        return Prediction.from_dict(body)

    message = _extract_error_message(body) or f"HTTP {status_code}"

    if status_code == 401:
        raise AuthenticationError(message, status_code=status_code, request_id=request_id)
    if status_code == 429:
        raise RateLimitError(
            message,
            status_code=status_code,
            request_id=request_id,
            retry_after=_parse_retry_after(headers),
        )
    raise APIError(message, status_code=status_code, request_id=request_id)


def _extract_error_message(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    # FastAPI default { "detail": "..." }, then look for siftfy-specific keys.
    for key in ("detail", "message", "error"):
        v = body.get(key)
        if isinstance(v, str):
            return v
        if isinstance(v, list) and v and isinstance(v[0], dict):
            msg = v[0].get("msg")
            if isinstance(msg, str):
                return msg
    return None


def _parse_retry_after(headers: dict[str, str]) -> float | None:
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def backoff_delay(attempt: int, *, retry_after: float | None = None) -> float:
    """Exponential backoff with jitter; honours Retry-After when given.

    attempt is 1-indexed (1 = first retry).
    """
    if retry_after is not None:
        return max(0.0, retry_after)
    base: float = min(8.0, 0.5 * float(2 ** (attempt - 1)))
    jitter: float = random.uniform(0, base / 2)
    return base + jitter


def is_retryable(status: int) -> bool:
    return status in RETRYABLE_STATUS


def validate_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError(f"text must be a str, got {type(text).__name__}")
    if not text:
        raise ValueError("text must be a non-empty string")
    return text
