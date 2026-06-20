"""Market Validation Engine for PRISM AI.

Market validation captures external demand and platform visibility, but its
influence is deliberately capped so popularity never outweighs technical fit.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from candidate.candidate_parser import CandidateParser
    from candidate.candidate_schema import CandidateProfile
except ImportError:
    from src.candidate.candidate_parser import CandidateParser
    from src.candidate.candidate_schema import CandidateProfile


@dataclass(frozen=True)
class MarketValidationResult:
    """Capped market-validation signals for a candidate."""

    recruiter_interest_score: float
    discoverability_score: float
    demand_score: float
    market_validation_score: float
    explanation: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


class MarketValidationEngine:
    """Score recruiter demand and platform visibility with capped influence."""

    def score(self, candidate: CandidateProfile) -> MarketValidationResult:
        """Return capped market-validation score components."""
        recruiter_interest_score = self.score_recruiter_interest(candidate)
        discoverability_score = self.score_discoverability(candidate)
        demand_score = self.score_demand(candidate)
        market_validation_score = min(
            75.0,
            0.45 * recruiter_interest_score
            + 0.35 * discoverability_score
            + 0.20 * demand_score,
        )

        return MarketValidationResult(
            recruiter_interest_score=round(recruiter_interest_score, 2),
            discoverability_score=round(discoverability_score, 2),
            demand_score=round(demand_score, 2),
            market_validation_score=round(market_validation_score, 2),
            explanation=self._explain(candidate, market_validation_score),
        )

    @staticmethod
    def score_recruiter_interest(candidate: CandidateProfile) -> float:
        """Score explicit recruiter interest through saves and views."""
        signals = candidate.recruiter_signals
        saves_score = min(100.0, signals.saved_by_recruiters_30d * 5.0)
        views_score = min(100.0, signals.profile_views_received_30d * 0.5)
        return 0.70 * saves_score + 0.30 * views_score

    @staticmethod
    def score_discoverability(candidate: CandidateProfile) -> float:
        """Score how often the candidate appears in recruiter searches."""
        appearances = candidate.recruiter_signals.search_appearance_30d
        return min(80.0, appearances / 3.0)

    @staticmethod
    def score_demand(candidate: CandidateProfile) -> float:
        """Score candidate-side market activity without over-rewarding spray applications."""
        applications = candidate.recruiter_signals.applications_submitted_30d
        if applications <= 0:
            return 0.0
        if applications <= 3:
            return applications * 25.0
        if applications <= 6:
            return 75.0
        return 60.0

    def _explain(self, candidate: CandidateProfile, market_validation_score: float) -> str:
        """Generate a short market-validation explanation."""
        signals = candidate.recruiter_signals
        return (
            f"{candidate.anonymized_name} has market validation {market_validation_score:.1f}: "
            f"{signals.saved_by_recruiters_30d} recruiter save(s), "
            f"{signals.profile_views_received_30d} profile view(s), "
            f"{signals.search_appearance_30d} search appearance(s), and "
            f"{signals.applications_submitted_30d} recent application(s). "
            "Influence is capped so market popularity cannot outweigh technical fit."
        )


def main() -> None:
    """Load sample candidates and print Top 10 by market-validation score."""
    engine = MarketValidationEngine()
    candidates = CandidateParser().parse_all()
    ranked = sorted(
        (
            {
                "candidate_name": candidate.anonymized_name,
                "candidate_id": candidate.candidate_id,
                "title": candidate.title,
                "current_company": candidate.current_company,
                **engine.score(candidate).to_dict(),
            }
            for candidate in candidates
        ),
        key=lambda item: item["market_validation_score"],
        reverse=True,
    )
    print(json.dumps(ranked[:10], indent=2))


if __name__ == "__main__":
    main()
