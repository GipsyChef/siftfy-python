"""Official Python client for the Siftfy spam-classification API.

>>> from siftfy import Siftfy
>>> client = Siftfy(api_key="sk_live_...")
>>> result = client.predict("Win a free iPad — click here!")
>>> result.spam_probability
0.97
>>> result.likelihood
'high'
"""

from siftfy._version import __version__
from siftfy.async_client import AsyncSiftfy
from siftfy.client import Siftfy
from siftfy.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
    SiftfyError,
)
from siftfy.models import Likelihood, Prediction

__all__ = [
    "APIError",
    "AsyncSiftfy",
    "AuthenticationError",
    "Likelihood",
    "Prediction",
    "RateLimitError",
    "Siftfy",
    "SiftfyError",
    "__version__",
]
