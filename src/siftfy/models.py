from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Likelihood = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Prediction:
    """A single classification result returned by the Siftfy API.

    `spam_probability` is calibrated: at 0.7, roughly 70% of inputs with that
    score are actually spam. `likelihood` is a coarse bucket derived from the
    probability — handy for quick branches; pick your own threshold off the
    raw probability for production decisions.
    """

    spam_probability: float
    likelihood: Likelihood

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Prediction:
        return cls(
            spam_probability=float(data["spam_probability"]),
            likelihood=data["likelihood"],
        )
