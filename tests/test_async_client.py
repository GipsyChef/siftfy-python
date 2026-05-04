from __future__ import annotations

import httpx
import pytest
import respx

from siftfy import AsyncSiftfy, AuthenticationError, RateLimitError

API_KEY = "sk_live_test"
BASE = "https://api.siftfy.io"


@respx.mock
async def test_async_predict_success() -> None:
    respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(
            200, json={"spam_probability": 0.92, "likelihood": "high"}
        )
    )
    async with AsyncSiftfy(api_key=API_KEY) as client:
        result = await client.predict("Win a free iPad")
    assert result.spam_probability == 0.92
    assert result.likelihood == "high"


@respx.mock
async def test_async_predict_authentication_error() -> None:
    respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(401, json={"detail": "invalid api key"})
    )
    async with AsyncSiftfy(api_key=API_KEY, max_retries=0) as client:
        with pytest.raises(AuthenticationError):
            await client.predict("hi")


@respx.mock
async def test_async_predict_retries_on_503_then_succeeds() -> None:
    route = respx.post(f"{BASE}/v1/predict").mock(
        side_effect=[
            httpx.Response(503, json={"detail": "unavailable"}),
            httpx.Response(
                200, json={"spam_probability": 0.4, "likelihood": "medium"}
            ),
        ]
    )
    async with AsyncSiftfy(api_key=API_KEY, max_retries=2) as client:
        result = await client.predict("hi")
    assert result.likelihood == "medium"
    assert route.call_count == 2


@respx.mock
async def test_async_predict_rate_limit() -> None:
    respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(
            429, json={"detail": "rate limit"}, headers={"retry-after": "0.01"}
        )
    )
    async with AsyncSiftfy(api_key=API_KEY, max_retries=0) as client:
        with pytest.raises(RateLimitError) as info:
            await client.predict("hi")
    assert info.value.retry_after == 0.01
