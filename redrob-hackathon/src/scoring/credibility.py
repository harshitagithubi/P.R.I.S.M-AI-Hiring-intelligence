"""Credibility scoring placeholders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.candidate.candidate_schema import CandidateProfile


@dataclass(frozen=True, slots=True)
class CredibilityScore:
    """Score describing evidence strength and profile credibility."""

    candidate_id: str
    score: float
    signals: dict[str, Any] = field(default_factory=dict)


class CredibilityScorer:
    """Placeholder scorer for candidate credibility."""

    def score(self, candidate: CandidateProfile) -> CredibilityScore:
        """Score the credibility of a candidate profile."""
        raise NotImplementedError("Credibility scoring is not implemented yet.")

