"""Structured schema for the P.R.I.S.M AI JD Understanding Engine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class JDProfile:
    """Structured hiring profile extracted from the Redrob AI hackathon JD."""

    title: str
    must_have: list[str]
    good_to_have: list[str]
    negative_signals: list[str]
    experience_min: int | None
    experience_max: int | None
    preferred_locations: list[str]
    weights: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the JD profile."""
        return {
            "title": self.title,
            "must_have": self.must_have,
            "good_to_have": self.good_to_have,
            "negative_signals": self.negative_signals,
            "experience_min": self.experience_min,
            "experience_max": self.experience_max,
            "preferred_locations": self.preferred_locations,
            "weights": self.weights,
        }


JobDescription = JDProfile
