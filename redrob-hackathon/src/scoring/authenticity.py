"""Authenticity scoring placeholders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.candidate.candidate_schema import CandidateProfile


@dataclass(frozen=True, slots=True)
class AuthenticityScore:
    """Score describing profile consistency and authenticity signals."""

    candidate_id: str
    score: float
    signals: dict[str, Any] = field(default_factory=dict)


class AuthenticityScorer:
    """Placeholder scorer for candidate authenticity."""

    def score(self, candidate: CandidateProfile) -> AuthenticityScore:
        """Score the authenticity of a candidate profile."""
        raise NotImplementedError("Authenticity scoring is not implemented yet.")

