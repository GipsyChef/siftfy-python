from __future__ import annotations


class SiftfyError(Exception):
    """Base class for all errors raised by the Siftfy SDK."""


class APIError(SiftfyError):
    """The API returned a non-2xx response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.request_id = request_id


class AuthenticationError(APIError):
    """API key is missing, invalid, or revoked (401)."""


class RateLimitError(APIError):
    """You exceeded the rate limit for your tier (429).

    `retry_after` is the number of seconds the server suggested waiting,
    parsed from the Retry-After header.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, request_id=request_id)
        self.retry_after = retry_after
