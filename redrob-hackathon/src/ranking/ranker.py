"""Candidate ranking placeholders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class CandidateRank:
    """Final ranked candidate result."""

    candidate_id: str
    rank: int
    total_score: float
    component_scores: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class CandidateRanker:
    """Placeholder ranker for large candidate batches."""

    def rank(self, candidates: Iterable[dict[str, Any]]) -> list[CandidateRank]:
        """Rank candidates using precomputed scoring signals."""
        raise NotImplementedError("Candidate ranking is not implemented yet.")



