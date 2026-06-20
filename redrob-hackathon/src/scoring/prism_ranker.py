"""Final PRISM Ranking Engine V4.

Combines Capability Fit, Evidence Strength, Recruitability, Ownership,
Market Validation, Assessments, and Semantic Similarity into a single ranked list.
"""

from __future__ import annotations

import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
import numpy as np

def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(dot / (norm1 * norm2))

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from candidate.candidate_parser import CandidateParser
    from candidate.candidate_schema import CandidateProfile
    from jd.jd_parser import JDParser
    from jd.jd_schema import JDProfile
    from scoring.market_validation import MarketValidationEngine
    from scoring.recruitability import RecruitabilityEngine
    from scoring.role_alignment import RoleAlignmentEngine
    from scoring.skill_proof import SkillProofEngine
    from utils.embedding_manager import EmbeddingManager
except ImportError:
    from src.candidate.candidate_parser import CandidateParser
    from src.candidate.candidate_schema import CandidateProfile
    from src.jd.jd_parser import JDParser
    from src.jd.jd_schema import JDProfile
    from src.scoring.market_validation import MarketValidationEngine
    from src.scoring.recruitability import RecruitabilityEngine
    from src.scoring.role_alignment import RoleAlignmentEngine
    from src.scoring.skill_proof import SkillProofEngine
    from src.utils.embedding_manager import EmbeddingManager

NON_AI_TITLES = {
    "marketing manager",
    "civil engineer",
    "graphic designer",
    "customer support",
    "sales executive",
    "accountant",
    "hr manager",
    "mechanical engineer",
    "operations manager",
    "project manager",
    "business analyst",
    "brand designer",
    "brand design",
    "mechanical engineering",
}

AI_CLAIM_TERMS = (
    "faiss",
    "pinecone",
    "qdrant",
    "weaviate",
    "milvus",
    "vector search",
    "vector database",
    "embeddings",
    "embedding",
    "langchain",
    "rag",
    "retrieval",
    "information retrieval",
    "recommendation systems",
    "recommendation",
)


@dataclass(frozen=True)
class PRISMRankingResult:
    """Final PRISM ranking result with score breakdown."""

    candidate_id: str
    candidate_name: str
    role_alignment_score: float
    skill_proof_score: float
    recruitability_score: float
    hireability_score: float
    market_validation_score: float
    score_breakdown: dict[str, float]
    technical_strength: float
    qualification_tier: str
    availability_multiplier: float
    effective_availability_multiplier: float
    final_score: float
    rank: int
    ranking_explanation: str
    raw_semantic_score: float
    career_evidence_score: float
    domain_gate_penalty: float
    domain_gate_applied: bool
    self_claim_score: float
    contradiction_severity: int
    contradiction_penalty: float
    domain_relevance: float
    fraud_penalty: float
    degraded_confidence: bool
    capability_score: float
    confidence_score: float
    ownership_score: float = 0.0
    capability_scores: dict[str, float] = field(default_factory=dict)
    capability_breakdowns: dict[str, dict[str, float]] = field(default_factory=dict)
    role_alignment_contribution: float = 0.0
    supporting_contribution: float = 0.0

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)

    @property
    def name(self) -> str:
        return self.candidate_name

    @property
    def role_alignment(self) -> float:
        return self.role_alignment_score

    @property
    def skill_proof(self) -> float:
        return self.skill_proof_score

    @property
    def recruitability(self) -> float:
        return self.recruitability_score

    @property
    def hireability(self) -> float:
        return self.hireability_score

    @property
    def market_validation(self) -> float:
        return self.market_validation_score


class PRISMRankingEngine:
    """Rank candidates using all PRISM V4 scoring modules."""

    # Max score bounds for scaling
    CAREER_EVIDENCE_MAX = 100.0
    CLAIM_STRENGTH_MAX = 100.0

    # Scale-independent thresholds
    LOW_EVIDENCE_THRESHOLD = 0.08 * CAREER_EVIDENCE_MAX   # 8.0
    EVIDENCE_THRESHOLD = 0.20 * CAREER_EVIDENCE_MAX       # 20.0
    HIGH_CLAIM_THRESHOLD = 0.05 * CLAIM_STRENGTH_MAX       # 5.0
    MODERATE_THRESHOLD = 0.02 * CLAIM_STRENGTH_MAX         # 2.0
    CONTRADICTION_THRESHOLD = 10.0
    HONEYPOT_THRESHOLD = 10.0
    MIN_ALIGNMENT = 2.0

    def __init__(
        self,
        role_alignment_engine: RoleAlignmentEngine | None = None,
        skill_proof_engine: SkillProofEngine | None = None,
        recruitability_engine: RecruitabilityEngine | None = None,
        market_validation_engine: MarketValidationEngine | None = None,
    ) -> None:
        self.role_alignment_engine = role_alignment_engine or RoleAlignmentEngine()
        self.skill_proof_engine = skill_proof_engine or SkillProofEngine()
        self.recruitability_engine = recruitability_engine or RecruitabilityEngine()
        self.market_validation_engine = market_validation_engine or MarketValidationEngine()

    def rank_candidates(
        self,
        jd_profile: JDProfile,
        candidates: list[CandidateProfile],
        limit: int = 100,
    ) -> list[PRISMRankingResult]:
        """Rank all candidates strictly by Final Score descending and Candidate ID ascending."""
        # Batch-encode all candidate and JD texts
        texts_to_encode = []
        
        jd_text = f"{jd_profile.title}. {' '.join(jd_profile.must_have)}. {' '.join(jd_profile.good_to_have)}"
        texts_to_encode.append(jd_text)
        texts_to_encode.append(f"{jd_profile.title} {' '.join(jd_profile.must_have)} {' '.join(jd_profile.good_to_have)}")

        from scoring.role_alignment import CAPABILITY_DESCRIPTIONS
        for cap_desc in CAPABILITY_DESCRIPTIONS.values():
            texts_to_encode.append(cap_desc)

        for candidate in candidates:
            summary_text = f"{candidate.headline} {candidate.summary} {candidate.title}"
            texts_to_encode.append(summary_text)

            cand_text = f"{candidate.headline}. {candidate.summary}. {candidate.title}. " + " ".join(
                f"{item.title}: {item.description}" for item in candidate.career_history
            )
            texts_to_encode.append(cand_text)

            for job in candidate.career_history:
                job_text = f"{job.title} at {job.company}. {job.description}"
                texts_to_encode.append(job_text)
                texts_to_encode.append(job.title)

        emb_mgr = EmbeddingManager()
        emb_mgr.batch_encode(texts_to_encode)

        unranked = [self._score_candidate(jd_profile, candidate) for candidate in candidates]

        # Sort strictly by effective_score DESC, with candidate_id ASC as a tiebreaker
        def get_sort_key(res):
            effective_score = res.final_score
            if res.qualification_tier == "Honeypot":
                effective_score -= 100.0
            return (-effective_score, res.candidate_id)

        sorted_results = sorted(
            unranked,
            key=get_sort_key,
        )

        ranked_results = [
            PRISMRankingResult(
                candidate_id=result.candidate_id,
                candidate_name=result.candidate_name,
                role_alignment_score=result.role_alignment_score,
                skill_proof_score=result.skill_proof_score,
                recruitability_score=result.recruitability_score,
                final_score=result.final_score,
                hireability_score=result.hireability_score,
                market_validation_score=result.market_validation_score,
                score_breakdown=result.score_breakdown,
                technical_strength=result.technical_strength,
                qualification_tier=result.qualification_tier,
                availability_multiplier=result.availability_multiplier,
                effective_availability_multiplier=result.effective_availability_multiplier,
                rank=index,
                ranking_explanation=result.ranking_explanation,
                raw_semantic_score=result.raw_semantic_score,
                career_evidence_score=result.career_evidence_score,
                domain_gate_penalty=result.domain_gate_penalty,
                domain_gate_applied=result.domain_gate_applied,
                self_claim_score=result.self_claim_score,
                contradiction_severity=result.contradiction_severity,
                contradiction_penalty=result.contradiction_penalty,
                domain_relevance=result.domain_relevance,
                fraud_penalty=result.fraud_penalty,
                degraded_confidence=result.degraded_confidence,
                capability_score=result.capability_score,
                confidence_score=result.confidence_score,
                ownership_score=result.ownership_score,
                capability_scores=result.capability_scores,
                capability_breakdowns=result.capability_breakdowns,
                role_alignment_contribution=result.role_alignment_contribution,
                supporting_contribution=result.supporting_contribution,
            )
            for index, result in enumerate(sorted_results[:limit], start=1)
        ]
        return ranked_results

    def _score_candidate(
        self,
        jd_profile: JDProfile,
        candidate: CandidateProfile,
    ) -> PRISMRankingResult:
        """Score a single candidate using PRISM V4 logic."""
        role_alignment = self.role_alignment_engine.score(jd_profile, candidate)
        skill_proof = self.skill_proof_engine.score(candidate)
        recruitability = self.recruitability_engine.score(candidate)
        market_validation = self.market_validation_engine.score(candidate)

        # Base score components
        cap_fit = role_alignment.capability_fit_score
        ev_strength = role_alignment.evidence_strength_score
        rec = recruitability.recruitability_score
        own = role_alignment.ownership_score
        mv = market_validation.market_validation_score
        assess = skill_proof.assessment_evidence_score

        base_score = (
            0.45 * cap_fit
            + 0.20 * ev_strength
            + 0.15 * rec
            + 0.10 * own
            + 0.05 * mv
            + 0.05 * assess
        )

        lexical = role_alignment.lexical_similarity_score
        capability_score = (0.90 * base_score + 0.10 * lexical)

        # Product Company Bonus (Soft preference)
        product_companies = {"flipkart", "swiggy", "meesho", "setu", "nykaa"}
        has_product_exp = any(
            any(prod in job.company.lower() for prod in product_companies)
            for job in candidate.career_history
        )
        if has_product_exp:
            capability_score += 5.0

        capability_score = min(100.0, max(0.0, capability_score))

        # --- Honeypot & Fraud Defense ---
        honeypot_mult = 1.0

        # 1. Duplicate career descriptions
        is_behavioral_twin = self._has_duplicate_descriptions(candidate)
        if is_behavioral_twin:
            honeypot_mult *= 0.60

        # 2. Ghost Candidate Detection
        days_since_last_active = self.recruitability_engine._days_since_active(
            candidate.recruiter_signals.last_active_date
        )
        is_ghost = days_since_last_active is not None and days_since_last_active > 730
        if is_ghost:
            honeypot_mult *= 0.75

        # 3. Multiple Current Jobs
        current_jobs = sum(1 for job in candidate.career_history if job.is_current)
        is_multiple = current_jobs > 1
        if is_multiple:
            honeypot_mult *= 0.70

        # 4. Fake Experience Detection
        total_duration_months = sum(job.duration_months for job in candidate.career_history)
        actual_years = total_duration_months / 12
        claimed_yoe = candidate.years_of_experience
        is_fake_yoe = claimed_yoe > actual_years + 4
        if is_fake_yoe:
            honeypot_mult *= 0.75

        # 5. Wrong Domain Professionals claiming AI expertise
        retrieval_skills = sum(1 for s in candidate.skills if any(self._term_matches(s.name.lower(), t) for t in AI_CLAIM_TERMS))
        title_lower = candidate.title.lower().strip()
        is_wrong_domain = title_lower in NON_AI_TITLES and retrieval_skills > 5
        if is_wrong_domain:
            honeypot_mult *= 0.40

        # 6. Keyword Stuffers
        is_stuffer = len(candidate.skills) > 15 and role_alignment.support_ratio < 0.2
        if is_stuffer:
            honeypot_mult *= 0.80

        # 7. Consulting-only Careers
        consulting_companies = {"tcs", "infosys", "wipro", "accenture"}
        consulting_months = sum(
            job.duration_months for job in candidate.career_history
            if any(comp in job.company.lower() for comp in consulting_companies)
        )
        consulting_ratio = consulting_months / total_duration_months if total_duration_months > 0 else 0.0
        if consulting_ratio > 0.8:
            honeypot_mult *= 0.80

        # Career Consistency
        career_consistency_score = 100.0
        has_non_ai = False
        has_technical = False
        for job in candidate.career_history:
            job_title = job.title.lower()
            if any(term in job_title for term in ("marketing", "civil", "sales", "hr", "graphic", "designer", "brand", "accountant", "customer support")):
                has_non_ai = True
            if any(term in job_title for term in ("engineer", "developer", "researcher", "data", "ml", "retrieval", "scientist")):
                has_technical = True
        if has_non_ai and has_technical:
            career_consistency_score = 40.0
            honeypot_mult *= 0.85

        # Trust-Aware Ranking: multiply capability by all confidence adjustments
        confidence_score = honeypot_mult
        
        breakdowns = getattr(role_alignment, "capability_breakdowns", {})
        
        # Penalize contradictions
        if skill_proof.contradiction_severity == 2:
            confidence_score *= 0.60
        elif skill_proof.contradiction_severity == 1:
            confidence_score *= 0.80
        elif skill_proof.contradiction_penalty > 0.0:
            confidence_score *= 0.90

        # Cap confidence penalties at 0.80 floor for candidates with:
        # - repeated verified core evidence
        # - multiple relevant roles
        # - strong ownership
        # - not catastrophic fraud (ghost, multiple current jobs, fake YOE, wrong domain, severe contradiction)
        has_core_verified_evidence = False
        has_core_recurrence = False
        for cap in ["retrieval", "ranking", "recommendation", "search_infrastructure"]:
            bd = breakdowns.get(cap, {})
            career_ev = bd.get("career_evidence", 0.0)
            project_ev = bd.get("project_evidence", 0.0)
            assess_ev = bd.get("assessment_evidence", 0.0)
            num_jobs = bd.get("num_relevant_jobs", 0)

            has_career = career_ev > 0.0
            has_project = project_ev > 0.0
            has_assess = assess_ev > 0.0

            # Verified evidence must originate from:
            # - Career history OR Career + Project OR Career + Assessment
            has_valid_origin = has_career or (has_career and has_project) or (has_career and has_assess)
            has_ownership = (own >= 15.0)

            if has_valid_origin and has_ownership:
                has_core_verified_evidence = True

            # Recurrence check:
            # - multiple career roles
            # OR
            # - career + project
            # OR
            # - career + assessment
            if (num_jobs >= 2) or (has_career and has_project) or (has_career and has_assess):
                has_core_recurrence = True

        is_catastrophic_fraud = is_ghost or is_multiple or is_fake_yoe or is_wrong_domain or (skill_proof.contradiction_severity == 2)
        if has_core_verified_evidence and has_core_recurrence and (not is_catastrophic_fraud):
            confidence_score = max(0.80, confidence_score)

        final_score = capability_score * confidence_score
        
        # Apply Generic Candidate/No-core-evidence penalty directly to final_score
        has_any_core_evidence = False
        for cap in ["retrieval", "ranking", "recommendation", "search_infrastructure"]:
            bd = breakdowns.get(cap, {})
            if bd.get("career_evidence", 0.0) > 0.0 or bd.get("project_evidence", 0.0) > 0.0 or bd.get("assessment_evidence", 0.0) > 0.0:
                has_any_core_evidence = True
                break
        if not has_any_core_evidence:
            final_score *= 0.40

        original_final_score = min(100.0, max(0.0, final_score))

        # Dynamic evidence-driven verdicts (using original_final_score to keep verdicts frozen)
        reqs = getattr(role_alignment, "requirements", {})
        mandatory_caps = reqs.get("mandatory", ["retrieval", "ranking", "vector_databases"])
        important_caps = reqs.get("important", [])

        has_core_mandatory_evidence = False
        for cap in mandatory_caps:
            bd = breakdowns.get(cap, {})
            # Check if has career, project, or assessment evidence >= 30.0
            if bd.get("career_evidence", 0.0) >= 30.0 or bd.get("project_evidence", 0.0) >= 30.0 or bd.get("assessment_evidence", 0.0) >= 30.0:
                has_core_mandatory_evidence = True
                break

        has_important_evidence = False
        for cap in important_caps:
            bd = breakdowns.get(cap, {})
            if bd.get("career_evidence", 0.0) >= 30.0 or bd.get("project_evidence", 0.0) >= 30.0 or bd.get("assessment_evidence", 0.0) >= 30.0:
                has_important_evidence = True
                break

        is_catastrophic_fraud = is_ghost or is_multiple or is_fake_yoe or is_wrong_domain or (skill_proof.contradiction_severity == 2)

        # Core Capabilities verification & recurrence check
        has_core_verified_evidence = False
        has_core_recurrence = False

        core_caps = ["retrieval", "ranking", "recommendation", "search_infrastructure"]
        for cap in core_caps:
            bd = breakdowns.get(cap, {})
            career_ev = bd.get("career_evidence", 0.0)
            project_ev = bd.get("project_evidence", 0.0)
            assess_ev = bd.get("assessment_evidence", 0.0)
            num_jobs = bd.get("num_relevant_jobs", 0)

            has_career = career_ev > 0.0
            has_project = project_ev > 0.0
            has_assess = assess_ev > 0.0

            # Verified evidence must originate from:
            # - Career history OR Career + Project OR Career + Assessment
            has_valid_origin = has_career or (has_career and has_project) or (has_career and has_assess)
            
            # Meaningful ownership or implementation check
            has_ownership = (own >= 15.0)

            if has_valid_origin and has_ownership:
                has_core_verified_evidence = True

            # Recurrence check:
            # - multiple career roles
            # OR
            # - career + project
            # OR
            # - career + assessment
            if (num_jobs >= 2) or (has_career and has_project) or (has_career and has_assess):
                has_core_recurrence = True

        is_strong_match_eligible = has_core_verified_evidence and has_core_recurrence and (not is_catastrophic_fraud)

        restored_final_score = self._restored_recruiter_score(
            candidate=candidate,
            role_alignment_score=role_alignment.final_score,
            skill_proof_score=skill_proof.skill_proof_score,
            capability_score=capability_score,
            contradiction_penalty=skill_proof.contradiction_penalty,
            confidence_score=confidence_score,
        )
        role_alignment_contribution = round(0.70 * restored_final_score, 2)
        supporting_contribution = round(0.30 * restored_final_score, 2)

        # Technical background check
        engineer_role_count = sum(1 for job in candidate.career_history if re.search(r"\bengineers?\b", job.title.lower()))
        developer_role_count = sum(1 for job in candidate.career_history if re.search(r"\bdev(eloper)?s?\b", job.title.lower()))
        qa_role_count = sum(1 for job in candidate.career_history if re.search(r"\b(qa|quality assurance|testing|test)\b", job.title.lower()))
        cloud_role_count = sum(1 for job in candidate.career_history if re.search(r"\b(cloud|aws|azure|gcp)\b", job.title.lower()))
        devops_role_count = sum(1 for job in candidate.career_history if re.search(r"\b(devops|sre|infrastructure|platform)\b", job.title.lower()))
        data_role_count = sum(1 for job in candidate.career_history if re.search(r"\b(data|analytics|database|sql)\b", job.title.lower()))

        is_technical = (
            engineer_role_count > 0
            or developer_role_count > 0
            or qa_role_count > 0
            or cloud_role_count > 0
            or devops_role_count > 0
            or data_role_count > 0
        )
        non_technical_background = not is_technical

        jd_claim_strength = role_alignment.self_claim_score
        career_evidence_score = role_alignment.career_evidence_score
        contradiction_penalty = skill_proof.contradiction_penalty

        honeypot_case1 = (
            jd_claim_strength >= self.HIGH_CLAIM_THRESHOLD
            and career_evidence_score <= self.LOW_EVIDENCE_THRESHOLD
            and contradiction_penalty >= self.CONTRADICTION_THRESHOLD
            and not is_technical
        )
        honeypot_case2 = (
            non_technical_background
            and jd_claim_strength >= self.HIGH_CLAIM_THRESHOLD
            and career_evidence_score <= self.LOW_EVIDENCE_THRESHOLD
            and contradiction_penalty >= 5.0
        )
        is_honeypot_candidate = honeypot_case1 or honeypot_case2

        is_weak_signal_candidate = (
            is_technical
            and jd_claim_strength > 0.0
            and role_alignment.final_score >= self.MIN_ALIGNMENT
            and career_evidence_score < self.EVIDENCE_THRESHOLD
            and not is_honeypot_candidate
        )

        # Restored recruiter-realistic tiers: honeypots are reserved for
        # contradiction/fraud patterns, while ordinary low-fit candidates remain
        # Weak Signal or Not Qualified.
        # Final ordering remains driven by technical fit and proof.
        if is_strong_match_eligible and restored_final_score >= 35.0:
            qualification_tier = "Strong Match"
        elif self._is_restored_near_match(
            candidate=candidate,
            restored_final_score=restored_final_score,
            role_alignment_score=role_alignment.final_score,
            skill_proof_score=skill_proof.skill_proof_score,
            is_catastrophic_fraud=is_catastrophic_fraud,
        ):
            qualification_tier = "Near Match"
        elif is_honeypot_candidate:
            qualification_tier = "Honeypot"
        elif is_weak_signal_candidate:
            qualification_tier = "Weak Signal"
        else:
            qualification_tier = "Not Qualified"

        fraud_penalty = max(0.0, capability_score - original_final_score)

        score_breakdown = {
            "role_alignment": round(role_alignment.final_score, 2),
            "skill_proof": round(skill_proof.skill_proof_score, 2),
            "recruitability": round(recruitability.recruitability_score, 2),
            "hireability": round(recruitability.hireability_score, 2),
            "market_validation": round(market_validation.market_validation_score, 2),
            "career_consistency": round(career_consistency_score, 2),
        }

        # Build recruiter summary explanation
        matched_jobs = []
        for job in candidate.career_history:
            job_text = f"{job.title} at {job.company}. {job.description}"
            has_evidence = False
            for cap in mandatory_caps:
                try:
                    from scoring.role_alignment import CAPABILITY_DESCRIPTIONS
                except ImportError:
                    from src.scoring.role_alignment import CAPABILITY_DESCRIPTIONS
                cap_desc = CAPABILITY_DESCRIPTIONS[cap]
                emb_C = self.role_alignment_engine.embedding_manager.get_embedding(cap_desc)
                emb_job = self.role_alignment_engine.embedding_manager.get_embedding(job_text)
                if cosine_similarity(emb_job, emb_C) >= 0.38:
                    has_evidence = True
                    break
            if has_evidence:
                matched_jobs.append(f"{job.title} at {job.company}")

        if matched_jobs:
            career_phrase = f"demonstrated search/retrieval career history as {', '.join(matched_jobs[:2])}"
        elif role_alignment.career_relevance_score >= 30.0:
            career_phrase = "demonstrated strong career history in search/retrieval"
        else:
            career_phrase = "limited direct career history in search/retrieval"

        verified_skills = [skill.name for skill in candidate.skills[:4]]
        skills_phrase = f"supported by skills in {', '.join(verified_skills)}" if verified_skills else "with few claimed skills"

        flags_phrase = ""
        if confidence_score < 1.0:
            if is_behavioral_twin:
                flags_phrase = " (flagged for duplicate career descriptions)"
            elif is_fake_yoe:
                flags_phrase = " (flagged for experience inflation)"
            elif is_multiple:
                flags_phrase = " (flagged for multiple active jobs)"
            elif is_ghost:
                flags_phrase = " (flagged as inactive ghost profile)"
            elif is_wrong_domain:
                flags_phrase = " (flagged for wrong domain AI claims)"
            elif skill_proof.contradiction_severity > 0:
                flags_phrase = " (flagged for claim track contradiction)"

        notice = candidate.recruiter_signals.notice_period_days
        notice_phrase = f"available with {notice}-day notice" if notice is not None else "notice period unknown"

        explanation = (
            f"{candidate.anonymized_name} is classified as a {qualification_tier}. "
            f"Shows {career_phrase}, {skills_phrase}, and is {notice_phrase}{flags_phrase}."
        )

        return PRISMRankingResult(
            candidate_id=candidate.candidate_id,
            candidate_name=candidate.anonymized_name,
            role_alignment_score=score_breakdown["role_alignment"],
            skill_proof_score=score_breakdown["skill_proof"],
            recruitability_score=score_breakdown["recruitability"],
            final_score=round(restored_final_score, 2),
            hireability_score=score_breakdown["hireability"],
            market_validation_score=score_breakdown["market_validation"],
            score_breakdown=score_breakdown,
            technical_strength=round(cap_fit, 2),
            qualification_tier=qualification_tier,
            availability_multiplier=round(recruitability.availability_multiplier, 3),
            effective_availability_multiplier=round(recruitability.availability_multiplier, 3),
            rank=0,
            ranking_explanation=explanation,
            raw_semantic_score=role_alignment.raw_semantic_score,
            career_evidence_score=role_alignment.career_evidence_score,
            domain_gate_penalty=role_alignment.domain_gate_penalty,
            domain_gate_applied=role_alignment.domain_gate_applied,
            self_claim_score=role_alignment.self_claim_score,
            contradiction_severity=skill_proof.contradiction_severity,
            contradiction_penalty=skill_proof.contradiction_penalty,
            domain_relevance=role_alignment.domain_relevance,
            fraud_penalty=round(fraud_penalty, 2),
            degraded_confidence=role_alignment.degraded_confidence,
            capability_score=round(capability_score, 2),
            confidence_score=round(confidence_score, 3),
            ownership_score=role_alignment.ownership_score,
            capability_scores=role_alignment.capability_scores,
            capability_breakdowns=role_alignment.capability_breakdowns,
            role_alignment_contribution=role_alignment_contribution,
            supporting_contribution=supporting_contribution,
        )

    def _restored_recruiter_score(
        self,
        candidate: CandidateProfile,
        role_alignment_score: float,
        skill_proof_score: float,
        capability_score: float,
        contradiction_penalty: float,
        confidence_score: float,
    ) -> float:
        """Restore earlier evidence-first ordering while keeping V4 diagnostics."""
        title = candidate.title.lower()
        industry = candidate.current_industry.lower()
        companies = " ".join(job.company.lower() for job in candidate.career_history)

        score = (
            0.68 * role_alignment_score
            + 0.22 * skill_proof_score
            + 0.10 * capability_score
        )

        if any(term in title for term in ("data engineer", "machine learning", "ml engineer")):
            score += 3.0
        if "backend engineer" in title:
            score += 1.0
        if any(company in companies for company in ("ola", "swiggy", "flipkart", "uber", "zomato", "meesho")):
            score += 2.0
        if "it services" in industry:
            score -= 4.0
        if any(term in title for term in NON_AI_TITLES):
            score -= 4.0
        if any(term in title for term in ("frontend", "qa", "devops", "mobile")):
            score -= 2.0

        score -= min(12.0, contradiction_penalty * 0.45)
        if confidence_score < 0.75:
            score *= 0.75

        return min(100.0, max(0.0, score * 1.45))

    @staticmethod
    def _is_restored_near_match(
        candidate: CandidateProfile,
        restored_final_score: float,
        role_alignment_score: float,
        skill_proof_score: float,
        is_catastrophic_fraud: bool,
    ) -> bool:
        """Return whether a candidate deserves the restored Near Match tier."""
        if is_catastrophic_fraud:
            return False
        title = candidate.title.lower()
        industry = candidate.current_industry.lower()
        if "it services" in industry:
            return False
        is_adjacent_engineer = any(term in title for term in ("data engineer", "machine learning", "ml engineer"))
        return (
            is_adjacent_engineer
            and restored_final_score >= 10.0
            and role_alignment_score >= 5.0
            and skill_proof_score >= 5.0
        )

    @staticmethod
    def _has_duplicate_descriptions(candidate: CandidateProfile) -> bool:
        """Detect duplicate career descriptions (Jaccard similarity > 0.85)."""
        descriptions = [job.description.lower().strip() for job in candidate.career_history if job.description]
        if len(descriptions) < 2:
            return False
        for i in range(len(descriptions)):
            words_i = set(re.findall(r"\w+", descriptions[i]))
            if not words_i:
                continue
            for j in range(i + 1, len(descriptions)):
                words_j = set(re.findall(r"\w+", descriptions[j]))
                if not words_j:
                    continue
                intersection = words_i & words_j
                union = words_i | words_j
                jaccard = len(intersection) / len(union)
                if jaccard > 0.85:
                    return True
        return False

    @staticmethod
    def _term_matches(text: str, term: str) -> bool:
        """Word-aware matching."""
        if term == "rag":
            return re.search(r"\brag\b", text, re.IGNORECASE) is not None
        pattern = rf"(?<![a-z0-9]){re.escape(term)}s?(?![a-z0-9])"
        return re.search(pattern, text) is not None
