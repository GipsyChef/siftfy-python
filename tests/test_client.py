from __future__ import annotations

import httpx
import pytest
import respx

from siftfy import (
    APIError,
    AuthenticationError,
    Prediction,
    RateLimitError,
    Siftfy,
    SiftfyError,
)

API_KEY = "sk_live_test"
BASE = "https://api.siftfy.io"


@respx.mock
def test_predict_success() -> None:
    respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(
            200,
            json={"spam_probability": 0.97, "likelihood": "high"},
            headers={"x-request-id": "req_abc"},
        )
    )
    with Siftfy(api_key=API_KEY) as client:
        result = client.predict("Win a free iPad")
    assert isinstance(result, Prediction)
    assert result.spam_probability == 0.97
    assert result.likelihood == "high"


@respx.mock
def test_predict_sends_correct_payload() -> None:
    route = respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(
            200, json={"spam_probability": 0.1, "likelihood": "low"}
        )
    )
    with Siftfy(api_key=API_KEY) as client:
        client.predict("hello")
    request = route.calls[0].request
    assert request.headers["x-api-key"] == API_KEY
    assert request.headers["content-type"] == "application/json"
    assert b'"text"' in request.content
    assert b'"hello"' in request.content
    assert request.headers["user-agent"].startswith("siftfy-python/")


@respx.mock
def test_predict_authentication_error() -> None:
    respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(401, json={"detail": "invalid api key"})
    )
    with Siftfy(api_key=API_KEY, max_retries=0) as client:
        with pytest.raises(AuthenticationError) as info:
            client.predict("hi")
    assert info.value.status_code == 401
    assert "invalid api key" in str(info.value)


@respx.mock
def test_predict_rate_limit_with_retry_after() -> None:
    respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(
            429,
            json={"detail": "rate limit"},
            headers={"retry-after": "0.01"},
        )
    )
    with Siftfy(api_key=API_KEY, max_retries=0) as client:
        with pytest.raises(RateLimitError) as info:
            client.predict("hi")
    assert info.value.status_code == 429
    assert info.value.retry_after == 0.01


@respx.mock
def test_predict_retries_on_5xx_then_succeeds() -> None:
    route = respx.post(f"{BASE}/v1/predict").mock(
        side_effect=[
            httpx.Response(503, json={"detail": "unavailable"}),
            httpx.Response(200, json={"spam_probability": 0.5, "likelihood": "medium"}),
        ]
    )
    with Siftfy(api_key=API_KEY, max_retries=2) as client:
        result = client.predict("hi")
    assert result.likelihood == "medium"
    assert route.call_count == 2


@respx.mock
def test_predict_does_not_retry_4xx_other_than_408_429() -> None:
    route = respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(400, json={"detail": "bad input"})
    )
    with Siftfy(api_key=API_KEY, max_retries=3) as client:
        with pytest.raises(APIError):
            client.predict("hi")
    assert route.call_count == 1


@respx.mock
def test_predict_retries_then_gives_up() -> None:
    route = respx.post(f"{BASE}/v1/predict").mock(
        return_value=httpx.Response(503, json={"detail": "still down"})
    )
    with Siftfy(api_key=API_KEY, max_retries=1) as client:
        with pytest.raises(APIError) as info:
            client.predict("hi")
    assert info.value.status_code == 503
    assert route.call_count == 2  # original + 1 retry


@respx.mock
def test_predict_network_error_retried_then_raised() -> None:
    respx.post(f"{BASE}/v1/predict").mock(side_effect=httpx.ConnectError("boom"))
    with Siftfy(api_key=API_KEY, max_retries=1) as client:
        with pytest.raises(SiftfyError):
            client.predict("hi")


def test_empty_text_rejected() -> None:
    with Siftfy(api_key=API_KEY) as client:
        with pytest.raises(ValueError):
            client.predict("")


def test_non_string_text_rejected() -> None:
    with Siftfy(api_key=API_KEY) as client:
        with pytest.raises(TypeError):
            client.predict(123)  # type: ignore[arg-type]


def test_missing_api_key_rejected() -> None:
    with pytest.raises(ValueError):
        Siftfy(api_key="")


@respx.mock
def test_custom_base_url() -> None:
    respx.post("http://localhost:8080/v1/predict").mock(
        return_value=httpx.Response(
            200, json={"spam_probability": 0.0, "likelihood": "low"}
        )
    )
    with Siftfy(api_key=API_KEY, base_url="http://localhost:8080") as client:
        result = client.predict("hello")
    assert result.likelihood == "low"
