"""Recruitability Engine for PRISM AI.

This module estimates how realistically hireable a candidate is right now
using Redrob behavioral and logistics signals.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime
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


PRIMARY_LOCATIONS = ("pune", "noida")
ACCEPTABLE_LOCATIONS = ("delhi", "delhi ncr", "gurgaon", "gurugram", "hyderabad", "mumbai")


@dataclass(frozen=True)
class RecruitabilityResult:
    """Recruitability component scores for a candidate."""

    activity_score: float
    responsiveness_score: float
    availability_score: float
    logistics_score: float
    market_interest_score: float
    recruitability_score: float
    hireability_score: float
    availability_multiplier: float
    explanation: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


class RecruitabilityEngine:
    """Score current hireability using Redrob behavioral signals."""

    def __init__(self, reference_date: date | None = None) -> None:
        self.reference_date = reference_date or date.today()

    def score(self, candidate: CandidateProfile) -> RecruitabilityResult:
        """Return recruitability scores and availability multiplier."""
        activity_score = self.score_activity(candidate)
        responsiveness_score = self.score_responsiveness(candidate)
        availability_score = self.score_availability(candidate)
        logistics_score = self.score_logistics(candidate)
        market_interest_score = self.score_market_interest(candidate)
        recruitability_score = (
            0.30 * activity_score
            + 0.25 * responsiveness_score
            + 0.20 * availability_score
            + 0.15 * logistics_score
            + 0.10 * market_interest_score
        )
        recruitability_score *= self._stale_activity_multiplier(
            candidate.recruiter_signals.last_active_date
        )

        # Calculate hireability_score based on 5 metrics
        last_active_val = self._last_active_score(candidate.recruiter_signals.last_active_date)
        response_val = (candidate.recruiter_signals.recruiter_response_rate or 0.0) * 100.0
        notice_val = self._notice_period_score(candidate.recruiter_signals.notice_period_days)
        open_to_work_val = 100.0 if candidate.recruiter_signals.open_to_work_flag else 45.0
        interview_val = (candidate.recruiter_signals.interview_completion_rate or 0.0) * 100.0

        hireability_score = (
            0.35 * last_active_val
            + 0.25 * response_val
            + 0.20 * notice_val
            + 0.10 * open_to_work_val
            + 0.10 * interview_val
        )

        availability_multiplier = self.compute_availability_multiplier(hireability_score)

        return RecruitabilityResult(
            activity_score=round(activity_score, 2),
            responsiveness_score=round(responsiveness_score, 2),
            availability_score=round(availability_score, 2),
            logistics_score=round(logistics_score, 2),
            market_interest_score=round(market_interest_score, 2),
            recruitability_score=round(recruitability_score, 2),
            hireability_score=round(hireability_score, 2),
            availability_multiplier=round(availability_multiplier, 3),
            explanation=self._explain(candidate, recruitability_score, availability_multiplier),
        )

    def score_activity(self, candidate: CandidateProfile) -> float:
        """Score recent platform activity and job-search intent."""
        signals = candidate.recruiter_signals
        recency_score = self._last_active_score(signals.last_active_date)
        application_score = min(100.0, signals.applications_submitted_30d * 20.0)
        activity_score = 0.85 * recency_score + 0.15 * application_score
        days_since_active = self._days_since_active(signals.last_active_date)
        if days_since_active is not None and days_since_active > 180:
            return min(activity_score, 20.0)
        if days_since_active is not None and days_since_active > 150:
            return min(activity_score, 35.0)
        return activity_score

    def score_responsiveness(self, candidate: CandidateProfile) -> float:
        """Score likelihood that the candidate responds to recruiters."""
        signals = candidate.recruiter_signals
        response_rate_score = (signals.recruiter_response_rate or 0.0) * 100.0
        response_time_score = self._response_time_score(signals.avg_response_time_hours)
        return 0.65 * response_rate_score + 0.35 * response_time_score

    def score_availability(self, candidate: CandidateProfile) -> float:
        """Score availability from open-to-work and notice-period signals."""
        signals = candidate.recruiter_signals
        open_to_work_score = 100.0 if signals.open_to_work_flag else 45.0
        notice_score = self._notice_period_score(signals.notice_period_days)
        return 0.55 * open_to_work_score + 0.45 * notice_score

    def score_logistics(self, candidate: CandidateProfile) -> float:
        """Score role logistics against Pune/Noida hybrid preference."""
        signals = candidate.recruiter_signals
        location_score = self._location_score(candidate)
        work_mode_score = self._work_mode_score(signals.preferred_work_mode)
        relocation_score = 100.0 if signals.willing_to_relocate else 55.0
        return 0.45 * location_score + 0.35 * work_mode_score + 0.20 * relocation_score

    def score_market_interest(self, candidate: CandidateProfile) -> float:
        """Score recruiter interest using capped market signals."""
        signals = candidate.recruiter_signals
        saves = min(100.0, signals.saved_by_recruiters_30d * 12.0)
        views = min(100.0, signals.profile_views_received_30d * 4.0)
        appearances = min(100.0, signals.search_appearance_30d / 3.0)
        return 0.45 * saves + 0.30 * views + 0.25 * appearances

    @staticmethod
    def compute_availability_multiplier(recruitability_score: float) -> float:
        """Convert recruitability score to a bounded ranking multiplier."""
        multiplier = 0.75 + (recruitability_score / 100.0) * 0.40
        return max(0.75, min(1.15, multiplier))

    def _last_active_score(self, last_active_date: str | None) -> float:
        """Score activity recency from last active date."""
        days = self._days_since_active(last_active_date)
        if days is None:
            return 0.0
        if days <= 30:
            return 100.0
        if days <= 60:
            return 80.0
        if days <= 90:
            return 60.0
        if days <= 180:
            return 30.0
        return 10.0

    def _days_since_active(self, last_active_date: str | None) -> int | None:
        """Return days since last platform activity."""
        if not last_active_date:
            return None
        try:
            parsed = datetime.strptime(last_active_date, "%Y-%m-%d").date()
        except ValueError:
            return None
        return max(0, (self.reference_date - parsed).days)

    def _stale_activity_multiplier(self, last_active_date: str | None) -> float:
        """Apply a final recruitability penalty for stale platform activity."""
        days = self._days_since_active(last_active_date)
        if days is None:
            return 0.80
        if days > 180:
            return 0.75
        if days > 150:
            return 0.85
        if days > 120:
            return 0.92
        return 1.0

    @staticmethod
    def _response_time_score(hours: float | None) -> float:
        """Score median recruiter response time."""
        if hours is None:
            return 0.0
        if hours <= 24:
            return 100.0
        if hours <= 72:
            return 80.0
        if hours <= 168:
            return 55.0
        if hours <= 336:
            return 30.0
        return 10.0

    @staticmethod
    def _notice_period_score(days: int | None) -> float:
        """Score stated notice period."""
        if days is None:
            return 40.0
        if days <= 15:
            return 100.0
        if days <= 30:
            return 90.0
        if days <= 60:
            return 65.0
        if days <= 90:
            return 40.0
        return 15.0

    @staticmethod
    def _work_mode_score(work_mode: str | None) -> float:
        """Score preferred work mode against a flexible hybrid role."""
        if not work_mode:
            return 50.0
        normalized = work_mode.lower()
        if normalized == "hybrid":
            return 100.0
        if normalized == "flexible":
            return 95.0
        if normalized == "onsite":
            return 85.0
        if normalized == "remote":
            return 55.0
        return 50.0

    @staticmethod
    def _location_score(candidate: CandidateProfile) -> float:
        """Score location fit for Pune/Noida preference."""
        location = candidate.location.lower()
        country = candidate.country.lower()
        if any(city in location for city in PRIMARY_LOCATIONS):
            return 100.0
        if any(city in location for city in ACCEPTABLE_LOCATIONS):
            return 80.0
        if country == "india":
            return 65.0 if candidate.recruiter_signals.willing_to_relocate else 45.0
        return 35.0 if candidate.recruiter_signals.willing_to_relocate else 20.0

    def _explain(
        self,
        candidate: CandidateProfile,
        recruitability_score: float,
        availability_multiplier: float,
    ) -> str:
        """Generate a short recruitability explanation."""
        signals = candidate.recruiter_signals
        response_rate = (signals.recruiter_response_rate or 0.0) * 100.0
        notice = signals.notice_period_days if signals.notice_period_days is not None else "unknown"
        activity = signals.last_active_date or "unknown"
        relocation = "willing to relocate" if signals.willing_to_relocate else "not marked willing to relocate"
        return (
            f"{candidate.anonymized_name} has recruitability {recruitability_score:.1f} "
            f"(multiplier {availability_multiplier:.2f}) based on last activity {activity}, "
            f"{response_rate:.0f}% recruiter response rate, {notice}-day notice period, "
            f"{signals.preferred_work_mode or 'unknown'} work-mode preference, and {relocation}."
        )


RecruitabilityScore = RecruitabilityResult


class RecruitabilityScorer(RecruitabilityEngine):
    """Backward-compatible scorer name from the initial project skeleton."""


def main() -> None:
    """Load sample candidates and print Top 10 by recruitability score."""
    engine = RecruitabilityEngine()
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
        key=lambda item: item["recruitability_score"],
        reverse=True,
    )
    print(json.dumps(ranked[:10], indent=2))


if __name__ == "__main__":
    main()
