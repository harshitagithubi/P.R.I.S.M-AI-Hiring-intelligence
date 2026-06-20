"""Structured candidate schemas for the P.R.I.S.M AI Candidate Intelligence Engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class CandidateExperience:
    """A normalized candidate career-history entry."""

    company: str
    title: str
    start_date: str
    end_date: str | None
    duration_months: int
    is_current: bool
    industry: str
    company_size: str
    description: str


@dataclass(frozen=True)
class CandidateEducation:
    """A normalized candidate education entry."""

    institution: str
    degree: str
    field_of_study: str
    start_year: int
    end_year: int
    grade: str | None = None
    tier: str = "unknown"


@dataclass(frozen=True)
class CandidateSkill:
    """A normalized candidate skill entry with evidence strength."""

    name: str
    proficiency: str
    endorsements: int
    duration_months: int | None = None


@dataclass(frozen=True)
class CandidateCertification:
    """A normalized candidate certification entry."""

    name: str
    issuer: str
    year: int


@dataclass(frozen=True)
class CandidateLanguage:
    """A normalized candidate language entry."""

    language: str
    proficiency: str


@dataclass(frozen=True)
class SalaryRange:
    """Expected salary range in INR LPA."""

    min: float | None = None
    max: float | None = None


@dataclass(frozen=True)
class RecruiterSignals:
    """Recruiter-facing availability, engagement, and verification signals."""

    profile_completeness_score: float | None
    signup_date: str | None
    last_active_date: str | None
    open_to_work_flag: bool
    profile_views_received_30d: int
    applications_submitted_30d: int
    recruiter_response_rate: float | None
    avg_response_time_hours: float | None
    connection_count: int
    endorsements_received: int
    notice_period_days: int | None
    expected_salary_range_inr_lpa: SalaryRange
    preferred_work_mode: str | None
    willing_to_relocate: bool
    search_appearance_30d: int
    saved_by_recruiters_30d: int
    interview_completion_rate: float | None
    offer_acceptance_rate: float | None
    verified_email: bool
    verified_phone: bool
    linkedin_connected: bool
    skill_assessment_scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class GithubSignals:
    """GitHub-derived activity signal from the Redrob profile."""

    github_activity_score: float | None
    has_github_activity: bool


@dataclass(frozen=True)
class CandidateProfile:
    """Structured representation of a candidate profile from the challenge dataset."""

    candidate_id: str
    anonymized_name: str
    headline: str
    summary: str
    location: str
    country: str
    title: str
    current_company: str
    current_company_size: str
    current_industry: str
    years_of_experience: float
    skills: list[CandidateSkill]
    education: list[CandidateEducation]
    certifications: list[CandidateCertification]
    recruiter_signals: RecruiterSignals
    github_signals: GithubSignals
    career_history: list[CandidateExperience] = field(default_factory=list)
    languages: list[CandidateLanguage] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the candidate profile."""
        return asdict(self)
