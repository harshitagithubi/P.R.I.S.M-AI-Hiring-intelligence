"""Explainability Engine for P.R.I.S.M AI."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from candidate.candidate_parser import CandidateParser
    from candidate.candidate_schema import CandidateProfile
    from jd.jd_parser import JDParser
    from jd.jd_schema import JDProfile
    from scoring.market_validation import MarketValidationEngine
    from scoring.prism_ranker import PRISMRankingEngine, PRISMRankingResult
    from scoring.recruitability import RecruitabilityEngine
    from scoring.role_alignment import RoleAlignmentEngine
    from scoring.skill_proof import JD_RELEVANT_CONCEPTS, SkillProofEngine
except ImportError:
    from src.candidate.candidate_parser import CandidateParser
    from src.candidate.candidate_schema import CandidateProfile
    from src.jd.jd_parser import JDParser
    from src.jd.jd_schema import JDProfile
    from src.scoring.market_validation import MarketValidationEngine
    from src.scoring.prism_ranker import PRISMRankingEngine, PRISMRankingResult
    from src.scoring.recruitability import RecruitabilityEngine
    from src.scoring.role_alignment import RoleAlignmentEngine
    from src.scoring.skill_proof import JD_RELEVANT_CONCEPTS, SkillProofEngine


@dataclass(frozen=True)
class CandidateExplanation:
    """Recruiter-facing explanation for a PRISM-ranked candidate."""

    candidate_id: str
    candidate_name: str
    qualification_tier: str
    final_score: float
    strengths: list[str]
    missing_requirements: list[str]
    risks: list[str]
    evidence_found: list[str]
    recruitability_summary: str
    market_summary: str
    decision_reason: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable explanation."""
        return asdict(self)


class ExplainabilityEngine:
    """Generate explanations from PRISM scores and candidate evidence."""

    def __init__(self) -> None:
        self.role_engine = RoleAlignmentEngine()
        self.skill_engine = SkillProofEngine()
        self.recruitability_engine = RecruitabilityEngine()
        self.market_engine = MarketValidationEngine()
        self.ranking_engine = PRISMRankingEngine(
            role_alignment_engine=self.role_engine,
            skill_proof_engine=self.skill_engine,
            recruitability_engine=self.recruitability_engine,
            market_validation_engine=self.market_engine,
        )

    def explain_candidate(
        self,
        jd_profile: JDProfile,
        candidate: CandidateProfile,
        ranking_result: PRISMRankingResult | None = None,
    ) -> CandidateExplanation:
        """Generate an explanation for one candidate."""
        if ranking_result is None:
            ranking_result = self.ranking_engine.rank_candidates(jd_profile, [candidate], limit=1)[0]

        role = self.role_engine.score(jd_profile, candidate)
        skill = self.skill_engine.score(candidate)
        recruitability = self.recruitability_engine.score(candidate)
        market = self.market_engine.score(candidate)
        evidence_concepts = self._evidence_concepts(candidate)
        claimed_concepts = self._claimed_concepts(candidate)

        strengths = self._strengths(candidate, evidence_concepts, role.final_score, skill.skill_proof_score)
        missing_requirements = self._missing_requirements(evidence_concepts)
        risks = self._risks(candidate, role.domain_gate_applied, claimed_concepts, evidence_concepts, skill.skill_proof_score)
        evidence_found = self._evidence_found(candidate, evidence_concepts)

        return CandidateExplanation(
            candidate_id=candidate.candidate_id,
            candidate_name=candidate.anonymized_name,
            qualification_tier=ranking_result.qualification_tier,
            final_score=ranking_result.final_score,
            strengths=strengths,
            missing_requirements=missing_requirements,
            risks=risks,
            evidence_found=evidence_found,
            recruitability_summary=(
                f"Recruitability {recruitability.recruitability_score:.1f}: "
                f"last active {candidate.recruiter_signals.last_active_date}, "
                f"{(candidate.recruiter_signals.recruiter_response_rate or 0) * 100:.0f}% recruiter response rate, "
                f"{candidate.recruiter_signals.notice_period_days}-day notice period."
            ),
            market_summary=(
                f"Market validation {market.market_validation_score:.1f}: "
                f"{candidate.recruiter_signals.saved_by_recruiters_30d} recruiter saves, "
                f"{candidate.recruiter_signals.profile_views_received_30d} views, "
                f"{candidate.recruiter_signals.search_appearance_30d} search appearances."
            ),
            decision_reason=self._decision_reason(
                ranking_result=ranking_result,
                strengths=strengths,
                missing_requirements=missing_requirements,
                risks=risks,
                candidate=candidate,
                evidence_concepts=evidence_concepts,
            ),
        )

    def explain_top_candidates(
        self,
        jd_profile: JDProfile,
        candidates: list[CandidateProfile],
        limit: int = 20,
    ) -> list[CandidateExplanation]:
        """Generate explanations for the top ranked candidates."""
        rankings = self.ranking_engine.rank_candidates(jd_profile, candidates, limit=limit)
        candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
        return [
            self.explain_candidate(jd_profile, candidate_by_id[result.candidate_id], result)
            for result in rankings
        ]

    def _evidence_concepts(self, candidate: CandidateProfile) -> set[str]:
        """Return JD concepts supported by career/project evidence."""
        text = self._career_text(candidate)
        concepts: set[str] = set()
        for concept, terms in JD_RELEVANT_CONCEPTS.items():
            if any(self._has_term(text, term) for term in terms):
                concepts.add(concept)
        return concepts

    def _claimed_concepts(self, candidate: CandidateProfile) -> set[str]:
        """Return JD concepts claimed in skill names."""
        text = self._normalize(" ".join(skill.name for skill in candidate.skills))
        concepts: set[str] = set()
        for concept, terms in JD_RELEVANT_CONCEPTS.items():
            if any(self._has_term(text, term) for term in terms):
                concepts.add(concept)
        return concepts

    def _strengths(
        self,
        candidate: CandidateProfile,
        evidence_concepts: set[str],
        role_score: float,
        skill_score: float,
    ) -> list[str]:
        """Build concise strengths."""
        strengths: list[str] = []
        if {"ranking", "recommendation"} & evidence_concepts:
            strengths.append("Production ranking or recommendation-system evidence appears in career history.")
        if {"retrieval", "embeddings", "vector_database"} & evidence_concepts:
            strengths.append("Retrieval, embeddings, or vector-search evidence was found.")
        if "python" in evidence_concepts:
            strengths.append("Python or backend/data pipeline evidence supports technical execution.")
        if role_score >= 40:
            strengths.append("Role alignment is strong relative to the JD.")
        if skill_score >= 40:
            strengths.append("Skill proof is supported by multiple evidence sources.")
        if not strengths:
            strengths.append("Candidate has limited but nonzero adjacent technical signals.")
        return strengths

    @staticmethod
    def _missing_requirements(evidence_concepts: set[str]) -> list[str]:
        """Return missing JD-critical evidence categories."""
        required = {
            "retrieval": "production retrieval evidence",
            "ranking": "ranking or learning-to-rank evidence",
            "recommendation": "recommendation-system evidence",
            "embeddings": "embeddings evidence",
            "vector_database": "vector database or vector-search evidence",
            "evaluation": "ranking evaluation or A/B testing evidence",
        }
        return [label for concept, label in required.items() if concept not in evidence_concepts]

    def _risks(
        self,
        candidate: CandidateProfile,
        domain_gate_applied: bool,
        claimed_concepts: set[str],
        evidence_concepts: set[str],
        skill_score: float,
    ) -> list[str]:
        """Build risks from gates and claim/proof mismatch."""
        risks: list[str] = []
        unsupported_claims = claimed_concepts - evidence_concepts
        if unsupported_claims and skill_score < 10:
            risks.append(
                "Profile claims JD-relevant skills but supporting career evidence was not found."
            )
        if domain_gate_applied:
            risks.append("Domain gate applied because retrieval/ranking career relevance is absent.")
        if candidate.current_industry.lower() == "it services":
            risks.append("Current profile is in IT services; JD prefers product-company applied ML depth.")
        if candidate.recruiter_signals.recruiter_response_rate is not None and candidate.recruiter_signals.recruiter_response_rate < 0.3:
            risks.append("Recruiter response rate is low.")
        if not risks:
            risks.append("No major PRISM reliability risk detected.")
        return risks

    def _evidence_found(self, candidate: CandidateProfile, concepts: set[str]) -> list[str]:
        """Return evidence snippets for display."""
        snippets: list[str] = []
        for experience in candidate.career_history:
            text = self._normalize(f"{experience.title} {experience.description}")
            if any(
                any(self._has_term(text, term) for term in terms)
                for concept, terms in JD_RELEVANT_CONCEPTS.items()
                if concept in concepts
            ):
                snippets.append(f"{experience.title} at {experience.company}: {experience.description[:220]}")
        if not snippets:
            snippets.append("No strong JD-domain career evidence found.")
        return snippets[:5]

    @staticmethod
    def _decision_reason(
        ranking_result: PRISMRankingResult,
        strengths: list[str],
        missing_requirements: list[str],
        risks: list[str],
        candidate: CandidateProfile,
        evidence_concepts: set[str],
    ) -> str:
        """Return structured Evidence, JD Match, and Concern explanation."""
        # 1. Evidence: list matched job titles and companies
        evidence_bullets = []
        for job in candidate.career_history:
            desc = job.description.lower()
            title = job.title.lower()
            # If the job matches search/retrieval/ranking/recommendation/embeddings/vector database
            if any(term in desc or term in title for term in ("ranking", "ranker", "recommend", "retrieval", "search", "embedding", "vector", "faiss", "pinecone", "qdrant", "weaviate", "milvus")):
                # Find matching sentences or extract
                sentences = [s.strip() for s in job.description.split(".") if s.strip()]
                matched_sentence = ""
                for s in sentences:
                    if any(term in s.lower() for term in ("ranking", "ranker", "recommend", "retrieval", "search", "embedding", "vector", "faiss", "pinecone", "qdrant", "weaviate", "milvus")):
                        matched_sentence = s.strip()
                        if not matched_sentence.endswith("."):
                            matched_sentence += "."
                        break
                if matched_sentence:
                    evidence_bullets.append(f"{matched_sentence} as {job.title} at {job.company}.")
                else:
                    evidence_bullets.append(f"Demonstrated capability as {job.title} at {job.company}.")

        if not evidence_bullets:
            if candidate.career_history:
                first_job = candidate.career_history[0]
                evidence_bullets.append(f"Worked as {first_job.title} at {first_job.company}.")
            else:
                evidence_bullets.append("No career history evidence found.")

        evidence_str = "\n".join(f"- {bullet}" for bullet in evidence_bullets[:4])

        # 2. JD Match
        matched_terms = []
        if "retrieval" in evidence_concepts:
            matched_terms.append("retrieval")
        if "ranking" in evidence_concepts:
            matched_terms.append("ranking")
        if "recommendation" in evidence_concepts:
            matched_terms.append("recommendation")
        if "embeddings" in evidence_concepts or "vector_database" in evidence_concepts:
            matched_terms.append("vector databases & embeddings")
        if matched_terms:
            jd_match_text = f"Matches {', '.join(matched_terms)} requirements."
        else:
            jd_match_text = "Matches basic technical developer requirements."

        # 3. Concern
        concerns = []
        if candidate.recruiter_signals.notice_period_days is not None and candidate.recruiter_signals.notice_period_days > 0:
            concerns.append(f"{candidate.recruiter_signals.notice_period_days}-day notice period.")
        if candidate.recruiter_signals.recruiter_response_rate is not None and candidate.recruiter_signals.recruiter_response_rate < 0.4:
            concerns.append(f"Low recruiter response rate ({candidate.recruiter_signals.recruiter_response_rate*100:.0f}%).")
        
        # Fraud checks
        from datetime import datetime, date
        days_since_active = None
        if candidate.recruiter_signals.last_active_date:
            try:
                parsed = datetime.strptime(candidate.recruiter_signals.last_active_date, "%Y-%m-%d").date()
                days_since_active = (date(2026, 6, 15) - parsed).days
                if days_since_active > 730:
                    concerns.append("Inactive for more than 2 years (Ghost Candidate).")
            except Exception:
                pass

        current_jobs = sum(1 for job in candidate.career_history if job.is_current)
        if current_jobs > 1:
            concerns.append("Multiple active current jobs.")

        total_duration_months = sum(job.duration_months for job in candidate.career_history)
        actual_years = total_duration_months / 12
        if candidate.years_of_experience > actual_years + 4:
            concerns.append(f"Experience inflation (claims {candidate.years_of_experience} YOE, actual {actual_years:.1f} YOE).")

        if not concerns:
            concerns.append("No major concerns detected.")
            
        concern_str = "\n".join(f"- {c}" for c in concerns[:3])

        return (
            f"Evidence:\n{evidence_str}\n\n"
            f"JD Match:\n{jd_match_text}\n\n"
            f"Concern:\n{concern_str}"
        )

    @staticmethod
    def _career_text(candidate: CandidateProfile) -> str:
        """Return normalized career evidence text."""
        return ExplainabilityEngine._normalize(
            " ".join(
                f"{item.title} {item.company} {item.industry} {item.description}"
                for item in candidate.career_history
            )
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for matching."""
        return re.sub(r"\s+", " ", text.lower()).strip()

    @staticmethod
    def _has_term(text: str, term: str) -> bool:
        """Return whether term exists with word-aware matching."""
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def main() -> None:
    """Generate and print explanations for top PRISM candidates."""
    jd_profile = JDParser().parse()
    candidates = CandidateParser().parse_all()
    ranker = PRISMRankingEngine()
    rankings = ranker.rank_candidates(jd_profile, candidates, limit=20)
    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    engine = ExplainabilityEngine()
    explanations = [
        engine.explain_candidate(jd_profile, candidates_by_id[ranking.candidate_id], ranking)
        for ranking in rankings
    ]

    output_path = Path("outputs") / "explanations.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps([explanation.to_dict() for explanation in explanations], indent=2),
        encoding="utf-8",
    )

    for explanation in explanations[:10]:
        print(f"Candidate Name: {explanation.candidate_name}")
        print(f"Qualification Tier: {explanation.qualification_tier}")
        print(f"Final Score: {explanation.final_score:.2f}")
        print("Strengths:")
        for item in explanation.strengths:
            print(f"- {item}")
        print("Missing Requirements:")
        for item in explanation.missing_requirements:
            print(f"- {item}")
        print("Risks:")
        for item in explanation.risks:
            print(f"- {item}")
        print(f"Decision Reason: {explanation.decision_reason}")
        print()


if __name__ == "__main__":
    main()
