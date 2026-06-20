"""Candidate parser for Module 2 of the P.R.I.S.M AI hackathon project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .candidate_schema import (
        CandidateCertification,
        CandidateEducation,
        CandidateExperience,
        CandidateLanguage,
        CandidateProfile,
        CandidateSkill,
        GithubSignals,
        RecruiterSignals,
        SalaryRange,
    )
except ImportError:
    from candidate_schema import (  # type: ignore[no-redef]
        CandidateCertification,
        CandidateEducation,
        CandidateExperience,
        CandidateLanguage,
        CandidateProfile,
        CandidateSkill,
        GithubSignals,
        RecruiterSignals,
        SalaryRange,
    )


DEFAULT_SAMPLE_CANDIDATES_PATH = Path(
    "/Users/harshitagupta/Downloads/[PUB] India_runs_data_and_ai_challenge/"
    "India_runs_data_and_ai_challenge/sample_candidates.json"
)


class CandidateParser:
    """Parse Redrob challenge candidate JSON into structured dataclasses."""

    def __init__(self, candidates_path: Path | str = DEFAULT_SAMPLE_CANDIDATES_PATH) -> None:
        self.candidates_path = Path(candidates_path)

    def load_candidates(self) -> list[dict[str, Any]]:
        """Load candidate records from the configured JSON file."""
        if not self.candidates_path.exists():
            raise FileNotFoundError(f"Candidate file not found: {self.candidates_path}")

        payload = json.loads(self.candidates_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return payload
        raise ValueError("Candidate JSON must contain an object or a list of objects.")

    def parse_all(self) -> list[CandidateProfile]:
        """Parse every candidate in the configured JSON file."""
        return [self.parse_candidate(candidate) for candidate in self.load_candidates()]

    def parse_candidate(self, candidate: dict[str, Any]) -> CandidateProfile:
        """Parse a single raw candidate dictionary into a ``CandidateProfile``."""
        profile = self._required_dict(candidate, "profile")
        signals = self._required_dict(candidate, "redrob_signals")

        return CandidateProfile(
            candidate_id=str(candidate["candidate_id"]),
            anonymized_name=str(profile["anonymized_name"]),
            headline=str(profile["headline"]),
            summary=str(profile["summary"]),
            location=str(profile["location"]),
            country=str(profile["country"]),
            title=str(profile["current_title"]),
            current_company=str(profile["current_company"]),
            current_company_size=str(profile["current_company_size"]),
            current_industry=str(profile["current_industry"]),
            years_of_experience=float(profile["years_of_experience"]),
            skills=self.extract_skills(candidate),
            education=self.extract_education(candidate),
            certifications=self.extract_certifications(candidate),
            recruiter_signals=self.extract_recruiter_signals(candidate),
            github_signals=self.extract_github_signals(candidate),
            career_history=self.extract_career_history(candidate),
            languages=self.extract_languages(candidate),
        )

    def extract_title(self, candidate: dict[str, Any]) -> str:
        """Extract the candidate's current title."""
        return str(self._required_dict(candidate, "profile")["current_title"])

    def extract_current_company(self, candidate: dict[str, Any]) -> str:
        """Extract the candidate's current company."""
        return str(self._required_dict(candidate, "profile")["current_company"])

    def extract_years_of_experience(self, candidate: dict[str, Any]) -> float:
        """Extract total years of professional experience."""
        return float(self._required_dict(candidate, "profile")["years_of_experience"])

    def extract_skills(self, candidate: dict[str, Any]) -> list[CandidateSkill]:
        """Extract structured skills and evidence fields."""
        return [
            CandidateSkill(
                name=str(skill["name"]),
                proficiency=str(skill["proficiency"]),
                endorsements=int(skill["endorsements"]),
                duration_months=self._optional_int(skill.get("duration_months")),
            )
            for skill in candidate.get("skills", [])
        ]

    def extract_education(self, candidate: dict[str, Any]) -> list[CandidateEducation]:
        """Extract structured education entries."""
        return [
            CandidateEducation(
                institution=str(item["institution"]),
                degree=str(item["degree"]),
                field_of_study=str(item["field_of_study"]),
                start_year=int(item["start_year"]),
                end_year=int(item["end_year"]),
                grade=self._optional_str(item.get("grade")),
                tier=str(item.get("tier", "unknown")),
            )
            for item in candidate.get("education", [])
        ]

    def extract_certifications(self, candidate: dict[str, Any]) -> list[CandidateCertification]:
        """Extract structured certification entries."""
        return [
            CandidateCertification(
                name=str(item["name"]),
                issuer=str(item["issuer"]),
                year=int(item["year"]),
            )
            for item in candidate.get("certifications", [])
        ]

    def extract_recruiter_signals(self, candidate: dict[str, Any]) -> RecruiterSignals:
        """Extract recruiter-facing activity, availability, and trust signals."""
        signals = self._required_dict(candidate, "redrob_signals")
        salary = signals.get("expected_salary_range_inr_lpa") or {}
        return RecruiterSignals(
            profile_completeness_score=self._optional_float(signals.get("profile_completeness_score")),
            signup_date=self._optional_str(signals.get("signup_date")),
            last_active_date=self._optional_str(signals.get("last_active_date")),
            open_to_work_flag=bool(signals.get("open_to_work_flag", False)),
            profile_views_received_30d=int(signals.get("profile_views_received_30d", 0)),
            applications_submitted_30d=int(signals.get("applications_submitted_30d", 0)),
            recruiter_response_rate=self._optional_float(signals.get("recruiter_response_rate")),
            avg_response_time_hours=self._optional_float(signals.get("avg_response_time_hours")),
            connection_count=int(signals.get("connection_count", 0)),
            endorsements_received=int(signals.get("endorsements_received", 0)),
            notice_period_days=self._optional_int(signals.get("notice_period_days")),
            expected_salary_range_inr_lpa=SalaryRange(
                min=self._optional_float(salary.get("min")),
                max=self._optional_float(salary.get("max")),
            ),
            preferred_work_mode=self._optional_str(signals.get("preferred_work_mode")),
            willing_to_relocate=bool(signals.get("willing_to_relocate", False)),
            search_appearance_30d=int(signals.get("search_appearance_30d", 0)),
            saved_by_recruiters_30d=int(signals.get("saved_by_recruiters_30d", 0)),
            interview_completion_rate=self._optional_float(signals.get("interview_completion_rate")),
            offer_acceptance_rate=self._optional_float(signals.get("offer_acceptance_rate")),
            verified_email=bool(signals.get("verified_email", False)),
            verified_phone=bool(signals.get("verified_phone", False)),
            linkedin_connected=bool(signals.get("linkedin_connected", False)),
            skill_assessment_scores={
                str(name): float(score)
                for name, score in (signals.get("skill_assessment_scores") or {}).items()
            },
        )

    def extract_github_signals(self, candidate: dict[str, Any]) -> GithubSignals:
        """Extract GitHub activity signals from Redrob profile data."""
        score = self._optional_float(
            self._required_dict(candidate, "redrob_signals").get("github_activity_score")
        )
        return GithubSignals(
            github_activity_score=score,
            has_github_activity=score is not None and score >= 0,
        )

    def extract_career_history(self, candidate: dict[str, Any]) -> list[CandidateExperience]:
        """Extract structured career-history entries."""
        return [
            CandidateExperience(
                company=str(item["company"]),
                title=str(item["title"]),
                start_date=str(item["start_date"]),
                end_date=self._optional_str(item.get("end_date")),
                duration_months=int(item["duration_months"]),
                is_current=bool(item["is_current"]),
                industry=str(item["industry"]),
                company_size=str(item["company_size"]),
                description=str(item["description"]),
            )
            for item in candidate.get("career_history", [])
        ]

    def extract_languages(self, candidate: dict[str, Any]) -> list[CandidateLanguage]:
        """Extract structured language entries."""
        return [
            CandidateLanguage(
                language=str(item["language"]),
                proficiency=str(item["proficiency"]),
            )
            for item in candidate.get("languages", [])
        ]

    @staticmethod
    def _required_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a required nested dictionary or raise a useful error."""
        value = payload.get(key)
        if not isinstance(value, dict):
            raise ValueError(f"Candidate record is missing required object: {key}")
        return value

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        """Convert a value to ``str`` while preserving missing values."""
        return None if value is None else str(value)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        """Convert a value to ``int`` while preserving missing values."""
        return None if value is None else int(value)

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        """Convert a value to ``float`` while preserving missing values."""
        return None if value is None else float(value)


def main() -> None:
    """Load sample candidates and print structured ``CandidateProfile`` objects."""
    profiles = CandidateParser().parse_all()
    print(json.dumps([profile.to_dict() for profile in profiles], indent=2))


if __name__ == "__main__":
    main()
