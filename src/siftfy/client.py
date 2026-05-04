from __future__ import annotations

import time
from types import TracebackType

import httpx

from siftfy._internal import (
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    backoff_delay,
    build_headers,
    is_retryable,
    parse_predict_response,
    validate_text,
)
from siftfy.exceptions import APIError, SiftfyError
from siftfy.models import Prediction


class Siftfy:
    """Synchronous client for the Siftfy spam-classification API.

    Example:

        from siftfy import Siftfy

        client = Siftfy(api_key="sk_live_...")
        result = client.predict("Win a free iPad — click here!")
        print(result.spam_probability)  # 0.97

    Use as a context manager to ensure the underlying HTTP connection is
    closed promptly:

        with Siftfy(api_key="sk_live_...") as client:
            result = client.predict("hello")
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max(0, max_retries)
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)

    def predict(self, text: str) -> Prediction:
        """Classify a single text input.

        Raises:
            siftfy.AuthenticationError: API key invalid or missing.
            siftfy.RateLimitError: rate limit exceeded.
            siftfy.APIError: any other 4xx/5xx response.
        """
        text = validate_text(text)
        url = f"{self._base_url}/v1/predict"
        headers = build_headers(self._api_key)
        body = {"text": text}

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._http.post(url, headers=headers, json=body)
            except httpx.RequestError as e:
                last_error = e
                if attempt < self._max_retries:
                    time.sleep(backoff_delay(attempt + 1))
                    continue
                raise SiftfyError(f"request failed: {e}") from e

            if response.status_code < 400 or not is_retryable(response.status_code):
                return parse_predict_response(
                    response.status_code,
                    dict(response.headers),
                    _safe_json(response),
                )

            # Retryable error
            if attempt < self._max_retries:
                retry_after = _retry_after_seconds(response)
                time.sleep(backoff_delay(attempt + 1, retry_after=retry_after))
                continue

            return parse_predict_response(
                response.status_code,
                dict(response.headers),
                _safe_json(response),
            )

        # Unreachable — the loop always returns or raises — but mypy/strict
        # wants a terminal statement.
        raise APIError(
            f"request failed after {self._max_retries + 1} attempts: {last_error}",
            status_code=0,
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> Siftfy:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def _safe_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return None


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
