"""Skill Proof Engine for PRISM AI.

This module measures profile reliability: whether the skills that make a
candidate look aligned with the JD are actually supported by work history,
projects, Redrob assessments, and GitHub activity.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from candidate.candidate_parser import CandidateParser
    from candidate.candidate_schema import CandidateProfile
except ImportError:
    from src.candidate.candidate_parser import CandidateParser
    from src.candidate.candidate_schema import CandidateProfile


JD_RELEVANT_CONCEPTS: dict[str, tuple[str, ...]] = {
    "retrieval": (
        "retrieval", "information retrieval", "semantic search", "hybrid search",
        "retrieval augmented generation", "semantic retrieval", "dense retrieval",
        "hybrid retrieval", "vector retrieval", "retrieval pipeline",
        "elasticsearch", "opensearch", "bm25", "faiss", "pinecone", "qdrant",
        "milvus", "weaviate", "sparse retrieval", "vector search", "cross encoder",
        "reranker", "rag", "langchain", "llamaindex", "prompt engineering",
        "fine tuning", "fine-tuning", "lora"
    ),
    "ranking": (
        "ranking", "ranker", "learning-to-rank", "re-ranking", "reranking",
        "cross encoder", "reranker", "learning to rank", "ltr", "document ranking",
        "candidate ranking", "search relevance", "query understanding", "relevance tuning",
        "bm25", "recommendation systems", "personalization", "search ranking"
    ),
    "recommendation": (
        "recommendation", "recommendations", "recommender",
        "recommendation systems", "personalization", "candidate ranking", "search ranking"
    ),
    "embeddings": (
        "embedding", "embeddings", "sentence transformers", "sentence-transformers",
        "hugging face", "huggingface", "transformers", "langchain", "llamaindex",
        "prompt engineering", "rag", "fine tuning", "fine-tuning", "lora"
    ),
    "evaluation": (
        "evaluation", "a/b test", "offline-online", "ndcg", "mrr", "map", "relevance",
        "weights & biases", "wandb", "mlflow"
    ),
    "vector_database": (
        "vector database", "vector search", "faiss", "qdrant", "weaviate", "pinecone",
        "milvus", "bm25", "hybrid search", "elasticsearch", "opensearch"
    ),
    "python": (
        "python", "pyspark", "fastapi", "flask", "airflow", "django",
        "kubeflow", "mlflow", "bentoml", "weights & biases", "wandb"
    ),
}

ASSESSMENT_TO_CONCEPTS: dict[str, tuple[str, ...]] = {
    "nlp": ("embeddings",),
    "machine learning": ("ranking", "recommendation", "evaluation"),
    "information retrieval": ("retrieval", "ranking", "evaluation"),
    "recommendation systems": ("recommendation", "ranking"),
    "fine-tuning llms": ("embeddings", "evaluation"),
    "python": ("python",),
    "feature engineering": ("ranking", "evaluation"),
    "mlops": ("evaluation",),
    "mlflow": ("evaluation",),
    "faiss": ("vector_database", "retrieval"),
    "pinecone": ("vector_database", "retrieval"),
    "qdrant": ("vector_database", "retrieval"),
    "weaviate": ("vector_database", "retrieval"),
    "milvus": ("vector_database", "retrieval"),
    "elasticsearch": ("vector_database", "retrieval"),
    "opensearch": ("vector_database", "retrieval"),
    "hugging face": ("embeddings", "retrieval"),
    "huggingface": ("embeddings", "retrieval"),
    "kubeflow": ("python", "evaluation"),
    "transformers": ("embeddings",),
    "rag": ("retrieval", "embeddings"),
}

EVALUATION_CONTEXT_TERMS: tuple[str, ...] = (
    "ranking",
    "ranker",
    "retrieval",
    "recommendation",
    "recommender",
    "model",
    "models",
    "ml",
    "offline",
    "online",
    "a/b",
    "ndcg",
    "mrr",
    "map",
    "relevance labeling",
)

# Constants for contradiction checks
NON_TECH_TERMS = (
    "teacher", "sales", "designer", "customer support", "graphic designer",
    "brand designer", "marketing manager", "sales executive", "accountant",
    "hr manager", "mechanical engineer", "civil engineer", "operations manager",
    "project manager", "business analyst", "brand design", "mechanical engineering"
)

MILD_TERMS = (
    "frontend", "qa", "quality assurance", "devops", "site reliability", "sre",
    "test automation", "testing", "support engineer",
    "mobile developer", "android developer", "ios developer",
    "mobile engineer", "android engineer", "ios engineer",
    "full stack", "fullstack", "java developer", ".net developer",
    "dot net", "sap developer", "cloud engineer"
)

# Pre-compiled regex patterns for speed optimization
JD_RELEVANT_CONCEPTS_COMPILED = {
    concept: re.compile(
        r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in terms) + r")s?(?![a-z0-9])",
        re.IGNORECASE
    )
    for concept, terms in JD_RELEVANT_CONCEPTS.items()
}

EVALUATION_CONTEXT_COMPILED = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in EVALUATION_CONTEXT_TERMS) + r")s?(?![a-z0-9])",
    re.IGNORECASE
)

NON_TECH_TERMS_COMPILED = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in NON_TECH_TERMS) + r")s?(?![a-z0-9])",
    re.IGNORECASE
)

MILD_TERMS_COMPILED = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in MILD_TERMS) + r")s?(?![a-z0-9])",
    re.IGNORECASE
)


@dataclass(frozen=True)
class SkillProofResult:
    """Evidence-backed reliability score for a candidate's JD-relevant skills."""

    career_evidence_score: float
    project_evidence_score: float
    assessment_evidence_score: float
    github_evidence_score: float
    claim_consistency_score: float
    contradiction_penalty: float
    skill_proof_score: float
    explanation: str
    contradiction_severity: int

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable result."""
        return asdict(self)


class SkillProofEngine:
    """Evaluate whether claimed JD-relevant skills are supported by proof."""

    def score(self, candidate: CandidateProfile) -> SkillProofResult:
        """Score candidate skill proof across career, project, assessment, and GitHub evidence."""
        career_concepts = self._supported_concepts(self._career_text(candidate))
        project_concepts = self._supported_concepts(self._project_text(candidate))
        claimed_concepts = self._claimed_concepts(candidate)

        career_score = self._concept_coverage_score(career_concepts)
        project_score = self._concept_coverage_score(project_concepts)
        assessment_score = self._assessment_evidence_score(candidate)
        github_score = self._github_evidence_score(
            candidate=candidate,
            has_domain_evidence=bool(career_concepts or project_concepts),
        )
        consistency_multiplier = self._claim_consistency_multiplier(
            claimed_concepts=claimed_concepts,
            supported_concepts=career_concepts | project_concepts | self._assessment_concepts(candidate),
        )
        contradiction_severity, contradiction_penalty = self._claim_contradiction_penalty(
            candidate=candidate,
            claimed_concepts=claimed_concepts,
            career_concepts=career_concepts,
            project_concepts=project_concepts,
        )

        base_score = (
            0.40 * career_score
            + 0.25 * project_score
            + 0.20 * assessment_score
            + 0.15 * github_score
        )
        final_score = max(0.0, min(100.0, base_score * consistency_multiplier - contradiction_penalty))

        return SkillProofResult(
            career_evidence_score=round(career_score, 2),
            project_evidence_score=round(project_score, 2),
            assessment_evidence_score=round(assessment_score, 2),
            github_evidence_score=round(github_score, 2),
            claim_consistency_score=round(consistency_multiplier, 2),
            contradiction_penalty=round(contradiction_penalty, 2),
            skill_proof_score=round(final_score, 2),
            explanation=self._explain(
                candidate=candidate,
                career_concepts=career_concepts,
                project_concepts=project_concepts,
                claimed_concepts=claimed_concepts,
                assessment_score=assessment_score,
                contradiction_penalty=contradiction_penalty,
                final_score=final_score,
            ),
            contradiction_severity=contradiction_severity,
        )

    def _career_text(self, candidate: CandidateProfile) -> str:
        """Return text from work history (excluding summary)."""
        history = " ".join(
            f"{item.title} {item.company} {item.industry} {item.description}"
            for item in candidate.career_history
        )
        return self._normalize(history)

    def _project_text(self, candidate: CandidateProfile) -> str:
        """Return project evidence text when future schemas provide project fields."""
        projects = getattr(candidate, "projects", None)
        if projects is None:
            return ""
        if isinstance(projects, str):
            return self._normalize(projects)
        if isinstance(projects, Iterable):
            return self._normalize(" ".join(str(project) for project in projects))
        return self._normalize(str(projects))

    def _supported_concepts(self, text: str) -> set[str]:
        """Extract JD-relevant concepts supported by evidence text."""
        if not text:
            return set()
        concepts: set[str] = set()
        for concept, pattern in JD_RELEVANT_CONCEPTS_COMPILED.items():
            if not pattern.search(text):
                continue
            if concept == "evaluation" and not EVALUATION_CONTEXT_COMPILED.search(text):
                continue
            concepts.add(concept)
        return concepts

    def _claimed_concepts(self, candidate: CandidateProfile) -> set[str]:
        """Map claimed skills to JD-relevant concepts."""
        skill_text = self._normalize(" ".join(skill.name for skill in candidate.skills))
        return self._supported_concepts(skill_text)

    def _assessment_concepts(self, candidate: CandidateProfile) -> set[str]:
        """Map available Redrob assessments to JD concepts."""
        concepts: set[str] = set()
        for assessment_name, score in candidate.recruiter_signals.skill_assessment_scores.items():
            if score <= 0:
                continue
            normalized_name = self._normalize(assessment_name)
            for key, mapped_concepts in ASSESSMENT_TO_CONCEPTS.items():
                if key in normalized_name:
                    concepts.update(mapped_concepts)
        return concepts

    def _assessment_evidence_score(self, candidate: CandidateProfile) -> float:
        """Score relevant Redrob skill assessments."""
        relevant_scores: list[float] = []
        for assessment_name, score in candidate.recruiter_signals.skill_assessment_scores.items():
            normalized_name = self._normalize(assessment_name)
            if any(key in normalized_name for key in ASSESSMENT_TO_CONCEPTS):
                relevant_scores.append(float(score))

        if not relevant_scores:
            return 0.0

        average_score = sum(relevant_scores) / len(relevant_scores)
        breadth_bonus = min(15.0, len(relevant_scores) * 3.0)
        return min(100.0, average_score + breadth_bonus)

    def _github_evidence_score(
        self,
        candidate: CandidateProfile,
        has_domain_evidence: bool,
    ) -> float:
        """Score GitHub activity without making external API calls."""
        score = candidate.github_signals.github_activity_score
        if score is None or score < 0:
            return 0.0
        github_score = min(100.0, score)
        if not has_domain_evidence:
            github_score *= 0.3
        return github_score

    def _concept_coverage_score(self, concepts: set[str]) -> float:
        """Convert supported concept coverage into a 0-100 score."""
        if not concepts:
            return 0.0
        coverage = len(concepts) / len(JD_RELEVANT_CONCEPTS)
        return min(100.0, coverage * 100.0)

    def _claim_consistency_multiplier(
        self,
        claimed_concepts: set[str],
        supported_concepts: set[str],
    ) -> float:
        """Return a multiplier based on agreement between claims and proof."""
        if not claimed_concepts:
            return 1.0 if supported_concepts else 0.9

        supported_claims = claimed_concepts & supported_concepts
        support_ratio = len(supported_claims) / len(claimed_concepts)

        if support_ratio >= 0.8:
            return 1.15
        if support_ratio >= 0.5:
            return 1.0
        if support_ratio >= 0.25:
            return 0.85
        return 0.65

    def _claim_contradiction_penalty(
        self,
        candidate: CandidateProfile,
        claimed_concepts: set[str],
        career_concepts: set[str],
        project_concepts: set[str],
    ) -> tuple[int, float]:
        """Penalize AI skill stuffing when the career track contradicts the claims. Returns (severity, penalty)."""
        supported_concepts = career_concepts | project_concepts
        no_domain_proof = not supported_concepts

        title_lower = candidate.title.lower().strip()
        career_text = self._career_text(candidate)

        # 1. Level 3: Fraud/Severe anomalies (Ghost candidate, Multiple Jobs, Fake YOE)
        # We check these here to return Severity Level 3, but the actual capping is handled in ranker.
        from src.scoring.recruitability import RecruitabilityEngine
        re_eng = RecruitabilityEngine()
        days = re_eng._days_since_active(candidate.recruiter_signals.last_active_date)
        is_ghost = days is not None and days > 730
        current_jobs = sum(1 for job in candidate.career_history if job.is_current)
        is_multiple = current_jobs > 1
        total_duration_months = sum(job.duration_months for job in candidate.career_history)
        actual_years = total_duration_months / 12
        is_fake_yoe = candidate.years_of_experience > actual_years + 4

        if is_ghost or is_multiple or is_fake_yoe:
            return 3, 0.0

        if not claimed_concepts:
            return 0, 0.0

        unsupported_claims = claimed_concepts - supported_concepts
        if not unsupported_claims:
            return 0, 0.0

        # 2. Level 2: Strong contradiction (Non-technical roles claiming AI skills without evidence)
        is_non_tech = (
            NON_TECH_TERMS_COMPILED.search(title_lower) is not None or
            NON_TECH_TERMS_COMPILED.search(career_text) is not None
        )
        if is_non_tech and no_domain_proof:
            return 2, 30.0

        # 3. Level 1: Mild contradiction (Frontend/QA/DevOps engineers claiming advanced AI skills without career evidence)
        is_mild_role = (
            MILD_TERMS_COMPILED.search(title_lower) is not None or
            MILD_TERMS_COMPILED.search(career_text) is not None
        )
        if is_mild_role and no_domain_proof:
            return 1, 15.0

        # Backwards compatibility check for any unsupported claims when no domain proof
        if no_domain_proof and len(unsupported_claims) >= 2:
            return 1, 12.0

        return 0, 0.0

    def _explain(
        self,
        candidate: CandidateProfile,
        career_concepts: set[str],
        project_concepts: set[str],
        claimed_concepts: set[str],
        assessment_score: float,
        contradiction_penalty: float,
        final_score: float,
    ) -> str:
        """Generate a short human-readable skill-proof explanation."""
        supported = sorted(career_concepts | project_concepts)
        claimed = sorted(claimed_concepts)
        github_score = candidate.github_signals.github_activity_score
        assessment_count = len(candidate.recruiter_signals.skill_assessment_scores)

        if supported:
            evidence_phrase = f"career evidence supports {', '.join(supported[:4])}"
        else:
            evidence_phrase = "limited JD-relevant career or project evidence was found"

        if github_score is None or github_score < 0:
            github_phrase = "no linked GitHub activity is available"
        elif supported:
            github_phrase = "GitHub activity is available and supports technical claims"
        else:
            github_phrase = (
                "GitHub activity is available but is downweighted because no "
                "JD-domain career or project evidence was found"
            )

        if assessment_score > 0:
            assessment_phrase = f"{assessment_count} Redrob assessment(s) show JD-relevant evidence"
        elif assessment_count:
            assessment_phrase = "assessments are available but not relevant to JD requirements"
        else:
            assessment_phrase = "no Redrob assessments are available"
        consistency_phrase = (
            "claimed skills align with supporting evidence"
            if claimed and set(claimed).intersection(supported)
            else "claimed JD-relevant skills have limited supporting proof"
        )
        contradiction_phrase = (
            "a claim/career contradiction was flagged"
            if contradiction_penalty
            else "no claim/career contradiction was noted"
        )

        return (
            f"{candidate.anonymized_name} shows skill proof evidence: "
            f"{evidence_phrase}, {assessment_phrase}, {github_phrase}, {consistency_phrase}, "
            f"and {contradiction_phrase}."
        )

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for deterministic matching."""
        return re.sub(r"\s+", " ", text.lower()).strip()

    @staticmethod
    def _has_any(text: str, terms: Iterable[str]) -> bool:
        """Return whether any configured term appears with word-aware matching."""
        for term in terms:
            if term == "rag":
                if re.search(r"\brag\b", text, re.IGNORECASE):
                    return True
            else:
                if re.search(rf"(?<![a-z0-9]){re.escape(term)}s?(?![a-z0-9])", text):
                    return True
        return False


def main() -> None:
    """Load sample candidates and print Top 10 by skill-proof score."""
    engine = SkillProofEngine()
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
        key=lambda result: result["skill_proof_score"],
        reverse=True,
    )
    print(json.dumps(ranked[:10], indent=2))


if __name__ == "__main__":
    main()
