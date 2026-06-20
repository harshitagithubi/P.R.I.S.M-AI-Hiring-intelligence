"""Explanation generation placeholders for ranked candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.ranking.ranker import CandidateRank


@dataclass(frozen=True, slots=True)
class CandidateExplanation:
    """Human-readable explanation for a ranked candidate."""

    candidate_id: str
    summary: str
    supporting_points: tuple[str, ...] = field(default_factory=tuple)
    concerns: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


class ExplanationGenerator:
    """Placeholder generator for ranking explanations."""

    def generate(self, rank: CandidateRank) -> CandidateExplanation:
        """Generate a candidate explanation from a ranked result."""
        raise NotImplementedError("Explanation generation is not implemented yet.")

