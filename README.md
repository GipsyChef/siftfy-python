# siftfy-python

Official Python client for the [Siftfy](https://siftfy.io) spam-classification
API. POST text, get a calibrated spam probability back. One round-trip, no
queues, no models to host.

[![PyPI version](https://img.shields.io/pypi/v/siftfy)](https://pypi.org/project/siftfy/)
[![Python versions](https://img.shields.io/pypi/pyversions/siftfy)](https://pypi.org/project/siftfy/)
[![CI](https://github.com/siftfy/siftfy-python/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/siftfy/siftfy-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Install

```bash
pip install siftfy
```

## Quick start

```python
from siftfy import Siftfy

client = Siftfy(api_key="sk_live_...")

result = client.predict("Win a free iPad — click here!")
print(result.spam_probability)  # 0.97
print(result.likelihood)        # "high"
```

Get an API key at [siftfy.io](https://siftfy.io) — the free tier covers
10,000 requests/month at no cost.

## Runnable examples

Use these when wiring Siftfy into a real form, signup flow, or moderation
queue:

- [FastAPI contact-form spam filter](https://siftfy.io/examples/fastapi-spam-filter)
- [Next.js route handler](https://siftfy.io/examples/nextjs-spam-filter)
- [Django view](https://siftfy.io/examples/django-spam-filter)
- [Laravel controller](https://siftfy.io/examples/laravel-spam-filter)
- [Webflow Worker](https://siftfy.io/examples/webflow-worker-spam-filter)
- [Ghost webhook pattern](https://siftfy.io/examples/ghost-spam-filter)
- [Browser spam probability tester](https://siftfy.io/tools/spam-probability-tester)

## Async

```python
import asyncio
from siftfy import AsyncSiftfy

async def main() -> None:
    async with AsyncSiftfy(api_key="sk_live_...") as client:
        result = await client.predict("hello, world")
        print(result.spam_probability)

asyncio.run(main())
```

## Calibrated probabilities

Every `spam_probability` is a calibrated value between 0 and 1 — at 0.7,
roughly 70% of inputs with that score are actually spam. Pick a threshold
appropriate to your use case (a help-desk form tolerates more false positives
than a marketplace listing); the same model serves both.

The `likelihood` field is a coarse bucket (`"low"`, `"medium"`, `"high"`)
derived from the probability. Handy for quick branches, but for production
decisions thread on the raw probability and your own threshold.

## Errors

```python
from siftfy import (
    Siftfy,
    AuthenticationError,  # 401 — bad / revoked key
    RateLimitError,       # 429 — over your tier limit; .retry_after available
    APIError,             # any other 4xx/5xx
    SiftfyError,          # network / request transport errors
)

try:
    result = client.predict(text)
except RateLimitError as e:
    sleep_for = e.retry_after or 1.0
    ...
except AuthenticationError:
    ...
except APIError as e:
    log(f"siftfy error {e.status_code}: {e} (request_id={e.request_id})")
```

The client retries idempotent failures (HTTP 408 / 429 / 5xx, network errors)
with exponential backoff and jitter, honouring `Retry-After` when present.
Tune with `max_retries=N` (default 2; set 0 to disable).

## Configuration

```python
client = Siftfy(
    api_key="sk_live_...",
    base_url="https://api.siftfy.io",  # override for self-hosted / staging
    timeout=10.0,                       # seconds, applied per attempt
    max_retries=2,                      # 0 disables retries
)
```

You can also pass your own `httpx.Client` (or `httpx.AsyncClient` for the
async client) via `http_client=...` if you want connection pooling, custom
transports, or to share a client across services.

## Resources

- API reference: <https://siftfy.io/docs>
- Predict endpoint: <https://siftfy.io/docs/predict>
- Runnable examples: <https://siftfy.io/examples>
- Free anti-spam tools: <https://siftfy.io/tools>
- Contact-form guide: <https://siftfy.io/use-cases/contact-forms>
- Comparison guide: <https://siftfy.io/best-spam-detection-api>
- Pricing: <https://siftfy.io/pricing>
- Status: ping `https://api.siftfy.io/health`
- Issues: <https://github.com/siftfy/siftfy-python/issues>

## License

MIT — see [LICENSE](LICENSE).
