"""Manual candidate audit utility for PRISM scoring decisions."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from candidate.candidate_parser import CandidateParser
    from candidate.candidate_schema import CandidateProfile
    from jd.jd_config import GOOD_TO_HAVE_KEYWORDS, MUST_HAVE_KEYWORDS, NEGATIVE_SIGNALS
    from jd.jd_parser import JDParser
    from scoring.role_alignment import RoleAlignmentEngine
    from scoring.skill_proof import SkillProofEngine
except ImportError:
    from src.candidate.candidate_parser import CandidateParser
    from src.candidate.candidate_schema import CandidateProfile
    from src.jd.jd_config import GOOD_TO_HAVE_KEYWORDS, MUST_HAVE_KEYWORDS, NEGATIVE_SIGNALS
    from src.jd.jd_parser import JDParser
    from src.scoring.role_alignment import RoleAlignmentEngine
    from src.scoring.skill_proof import SkillProofEngine


AUDIT_CANDIDATES = (
    "Ela Singh",
    "Ira Vora",
    "Aarav Kapoor",
    "Avni Pandey",
    "Rahul Joshi",
)

REQUIREMENT_EVIDENCE_TERMS: dict[str, tuple[str, ...]] = {
    "embeddings": ("embedding", "embeddings", "sentence transformers", "semantic search"),
    "retrieval": ("retrieval", "information retrieval", "semantic search", "hybrid search"),
    "ranking": ("ranking", "ranker", "learning-to-rank", "re-ranking", "reranking"),
    "recommendation": ("recommendation", "recommendations", "recommender"),
    "vector": ("vector database", "vector search", "faiss", "qdrant", "weaviate", "pinecone", "milvus"),
    "python": ("python", "pyspark", "flask", "fastapi", "django", "airflow"),
    "evaluation": ("evaluation", "offline-online", "a/b", "ndcg", "mrr", "map", "relevance"),
    "production": ("production", "deployed", "real users", "on-call", "pipeline", "scale"),
    "distributed": ("distributed systems", "kafka", "spark", "streaming", "large-scale", "inference"),
    "fine_tuning": ("lora", "qlora", "peft", "fine-tuning", "fine tuning"),
    "hrtech": ("hr-tech", "recruiting", "marketplace", "talent"),
    "open_source": ("open-source", "github"),
    "mentoring": ("mentor", "mentoring", "team from"),
    "async": ("async", "write", "writing"),
    "active_market": ("open to", "applications", "active"),
    "pure_research": ("academic lab", "pure research", "research-only"),
    "langchain_only": ("langchain",),
    "not_coding": ("architecture", "tech lead", "hasn't written production code"),
    "title_chasing": ("staff", "principal", "switching companies", "title"),
    "services_only": ("tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "mindtree"),
    "cv_speech_robotics": ("computer vision", "image classification", "speech", "robotics"),
    "closed_source": ("closed-source", "proprietary"),
    "unstable_fit": ("stable", "mature"),
    "keyword_stuffing": ("skills", "keywords"),
    "low_recruitability": ("inactive", "response rate", "last active"),
}


def main() -> None:
    """Print a manual audit for selected candidates."""
    jd_profile = JDParser().parse()
    role_engine = RoleAlignmentEngine()
    skill_engine = SkillProofEngine()
    candidates_by_name = {candidate.anonymized_name: candidate for candidate in CandidateParser().parse_all()}

    for name in AUDIT_CANDIDATES:
        candidate = candidates_by_name[name]
        role_result = role_engine.score(jd_profile, candidate)
        skill_result = skill_engine.score(candidate)

        print("=" * 88)
        print(f"Name: {candidate.anonymized_name}")
        print(f"Title: {candidate.title}")
        print(f"Company: {candidate.current_company}")
        print(f"YOE: {candidate.years_of_experience}")
        print(f"Location: {candidate.location}, {candidate.country}")
        print()
        print("Skills:")
        print(", ".join(skill.name for skill in candidate.skills) or "None")
        print()
        print("Career History:")
        for experience in candidate.career_history:
            print(
                f"- {experience.title} at {experience.company} "
                f"({experience.duration_months} months, {experience.industry})"
            )
            print(f"  {experience.description}")
        print()
        evidence_text = _candidate_evidence_text(candidate)
        print("Matched Must-Have JD Skills:")
        _print_matches(MUST_HAVE_KEYWORDS, evidence_text)
        print()
        print("Matched Good-To-Have Skills:")
        _print_matches(GOOD_TO_HAVE_KEYWORDS, evidence_text)
        print()
        print("Matched Negative Signals:")
        _print_negative_matches(NEGATIVE_SIGNALS, evidence_text)
        print()
        print("Role Alignment Breakdown:")
        print(f"- Evidence Score: {role_result.evidence_score:.2f}")
        print(f"- Raw Semantic Score: {role_result.raw_semantic_score:.2f}")
        print(f"- Domain Relevance: {role_result.domain_relevance:.3f}")
        print(f"- Effective Semantic Score: {role_result.effective_semantic_score:.2f}")
        print(f"- Career Relevance: {role_result.career_relevance_score:.2f}")
        print(f"- Experience Fit: {role_result.experience_fit_score:.2f}")
        print(f"- Domain Gate Applied: {role_result.domain_gate_applied}")
        print(f"- Final Role Alignment: {role_result.final_score:.2f}")
        print()
        print("Skill Proof Breakdown:")
        print(f"- Career Evidence: {skill_result.career_evidence_score:.2f}")
        print(f"- Project Evidence: {skill_result.project_evidence_score:.2f}")
        print(f"- Assessment Evidence: {skill_result.assessment_evidence_score:.2f}")
        print(f"- GitHub Evidence: {skill_result.github_evidence_score:.2f}")
        print(f"- Claim Consistency Multiplier: {skill_result.claim_consistency_score:.2f}")
        print(f"- Final Skill Proof: {skill_result.skill_proof_score:.2f}")
        print()
        print("Why Candidate Received This Score:")
        print(_score_reason(candidate, role_result.final_score, skill_result.explanation))
        print()


def _candidate_evidence_text(candidate: CandidateProfile) -> str:
    """Return normalized text used for audit matching."""
    career_text = " ".join(
        f"{item.title} {item.company} {item.industry} {item.description}"
        for item in candidate.career_history
    )
    skill_text = " ".join(skill.name for skill in candidate.skills)
    return _normalize(f"{candidate.headline} {candidate.summary} {career_text} {skill_text}")


def _print_matches(requirements: Iterable[str], evidence_text: str) -> None:
    """Print requirements that have matching audit evidence."""
    matches = []
    for requirement in requirements:
        terms = _terms_for_requirement(requirement)
        matched_terms = [term for term in terms if _has_term(evidence_text, term)]
        if matched_terms:
            matches.append((requirement, matched_terms))

    if not matches:
        print("- None")
        return

    for requirement, matched_terms in matches:
        print(f"- {requirement}")
        print(f"  evidence terms: {', '.join(matched_terms)}")


def _print_negative_matches(requirements: Iterable[str], evidence_text: str) -> None:
    """Print negative signals only when contextual negative phrases are present."""
    matches = []
    for requirement in requirements:
        terms = _negative_terms_for_requirement(requirement)
        matched_terms = [term for term in terms if _has_term(evidence_text, term)]
        if matched_terms:
            matches.append((requirement, matched_terms))

    if not matches:
        print("- None")
        return

    for requirement, matched_terms in matches:
        print(f"- {requirement}")
        print(f"  evidence terms: {', '.join(matched_terms)}")


def _negative_terms_for_requirement(requirement: str) -> tuple[str, ...]:
    """Map negative requirements to strict contextual phrases only."""
    normalized = _normalize(requirement)
    if "pure research" in normalized:
        return ("pure research", "research-only", "academic lab only", "without production")
    if "langchain" in normalized:
        return ("langchain wrapper only", "openai wrapper only", "chatgpt wrapper only")
    if "last 18 months" in normalized or "production coding" in normalized:
        return (
            "without production code",
            "limited production experience",
            "hasn't written production code",
            "architecture-only",
            "tech lead only",
        )
    if "title" in normalized:
        return ("title-chaser", "title chasing", "switching companies for title")
    if "consulting" in normalized:
        return ("only consulting", "services-only", "tcs only", "infosys only", "wipro only")
    if "computer vision" in normalized:
        return ("computer vision only", "speech recognition only", "robotics only")
    if "closed-source" in normalized:
        return ("closed-source only", "cannot show evidence", "proprietary only")
    if "stable, mature" in normalized:
        return ("stable mature codebase only", "maintenance-only")
    if "keyword-heavy" in normalized:
        return ("keyword stuffing", "skills section contains the most ai keywords")
    if "stale platform" in normalized:
        return ("inactive for 6 months", "low recruiter response rate", "very low recruiter response rate")
    return ()


def _terms_for_requirement(requirement: str) -> tuple[str, ...]:
    """Map a configured JD requirement to audit evidence terms."""
    normalized = _normalize(requirement)
    if "embeddings-based retrieval" in normalized:
        return REQUIREMENT_EVIDENCE_TERMS["embeddings"] + REQUIREMENT_EVIDENCE_TERMS["retrieval"]
    if "vector databases" in normalized or "hybrid search" in normalized:
        return REQUIREMENT_EVIDENCE_TERMS["vector"]
    if "strong python" in normalized:
        return REQUIREMENT_EVIDENCE_TERMS["python"]
    if "evaluation frameworks" in normalized:
        return REQUIREMENT_EVIDENCE_TERMS["evaluation"]
    if "ranking, search, recommendation, retrieval" in normalized:
        return (
            REQUIREMENT_EVIDENCE_TERMS["ranking"]
            + REQUIREMENT_EVIDENCE_TERMS["recommendation"]
            + REQUIREMENT_EVIDENCE_TERMS["retrieval"]
        )
    if "candidate-jd matching" in normalized:
        return ("candidate matching", "matching system", "candidate-jd")
    if "scrappy product-engineering" in normalized:
        return ("shipped", "ship", "owned", "product", "users", "pm")
    if "product-company" in normalized:
        return ("product company", "product companies", "product's", "users", "pm")
    if "production coding" in normalized or "production ownership" in normalized:
        return ("production code", "backend", "implemented", "built", "owned", "on-call")
    if "fine-tuning" in normalized:
        return REQUIREMENT_EVIDENCE_TERMS["fine_tuning"]
    if "learning-to-rank" in normalized:
        return ("learning-to-rank", "xgboost", "lightgbm", "ranking model", "ranker")
    if "hr-tech" in normalized:
        return ("hr-tech", "recruiting tech", "marketplace", "talent intelligence")
    if "distributed systems" in normalized:
        return REQUIREMENT_EVIDENCE_TERMS["distributed"]
    if "open-source" in normalized:
        return ("open-source", "github")
    if "mentoring" in normalized:
        return REQUIREMENT_EVIDENCE_TERMS["mentoring"]
    if "async" in normalized:
        return ("async", "writing", "documentation")
    if "active job-market" in normalized:
        return ("open to", "applications", "active")

    if "pure research" in normalized:
        return ("pure research", "academic lab", "research-only")
    if "langchain" in normalized:
        return ("langchain", "openai wrapper", "chatgpt")
    if "last 18 months" in normalized:
        return ("hasn't written production code", "architecture-only", "tech lead only")
    if "title" in normalized:
        return ("title-chaser", "staff", "principal", "switching companies")
    if "consulting" in normalized:
        return ("tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "mindtree")
    if "computer vision" in normalized:
        return ("computer vision", "image classification", "speech recognition", "robotics")
    if "closed-source" in normalized:
        return ("closed-source", "proprietary")
    if "stable, mature" in normalized:
        return ("stable, mature", "stable codebase", "mature codebase")
    if "keyword-heavy" in normalized:
        return ("keyword", "skills section")
    if "stale platform" in normalized:
        return ("last active", "response rate", "inactive")

    return tuple(token for token in normalized.split() if len(token) >= 5)


def _score_reason(candidate: CandidateProfile, role_score: float, skill_explanation: str) -> str:
    """Generate concise audit reasoning from scores and evidence."""
    if role_score >= 40:
        role_phrase = "strong JD-domain alignment"
    elif role_score >= 20:
        role_phrase = "partial or adjacent JD-domain alignment"
    else:
        role_phrase = "weak JD-domain alignment"

    return (
        f"{candidate.anonymized_name} received {role_phrase}. "
        f"{skill_explanation}"
    )


def _normalize(text: str) -> str:
    """Normalize text for deterministic matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has_term(text: str, term: str) -> bool:
    """Return whether a term appears with word-aware matching."""
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


if __name__ == "__main__":
    main()
