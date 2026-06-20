"""Role Alignment Engine for PRISM AI V4.

Scores candidates using SentenceTransformers semantic similarity, capability fit,
granular ownership analysis, recurrence depth, environment quality, and recruiter priority tiers.
"""

from __future__ import annotations

import math
import re
import sys
import numpy as np
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    sys.path.append(str(Path(__file__).resolve().parents[2]))

try:
    from candidate.candidate_parser import CandidateParser
    from candidate.candidate_schema import CandidateProfile
    from jd.jd_parser import JDParser
    from jd.jd_schema import JDProfile
    from scoring.skill_proof import SkillProofEngine
    from utils.embedding_manager import EmbeddingManager
except ImportError:
    from src.candidate.candidate_parser import CandidateParser
    from src.candidate.candidate_schema import CandidateProfile
    from src.jd.jd_parser import JDParser
    from src.jd.jd_schema import JDProfile
    from src.scoring.skill_proof import SkillProofEngine
    from src.utils.embedding_manager import EmbeddingManager

# Descriptive blocks for the 13 core capabilities
CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "retrieval": (
        "Information retrieval systems, vector search, dense retrieval, semantic search, hybrid search, "
        "candidate matching, similarity search, embedding-powered retrieval, ANN indexing, search relevance, "
        "retrieval infrastructure."
    ),
    "ranking": (
        "Learning-to-rank systems, relevance optimization, ranking models, reranking, NDCG optimization, "
        "MRR optimization, search ranking, feed ranking, candidate ranking."
    ),
    "recommendation": (
        "Recommendation systems, personalization, content recommendation, feed recommendation, "
        "candidate recommendation, ranking-based personalization."
    ),
    "search_infrastructure": (
        "Search infrastructure, search platforms, indexing, query understanding, search relevance, "
        "search architecture."
    ),
    "embeddings": (
        "Text embeddings, sentence transformers, BERT, representation learning, "
        "bi-encoders, representation learning, fine-tuning LLMs."
    ),
    "vector_databases": (
        "Vector databases, vector search, vector stores, FAISS, Qdrant, Pinecone, "
        "Weaviate, Milvus, pgvector."
    ),
    "evaluation": (
        "Offline evaluation metrics, relevance labeling, A/B testing, NDCG, MRR, MAP, "
        "recall@k, precision@k."
    ),
    "production_ml": (
        "Production machine learning, model deployment, real-time inference, Triton, "
        "SageMaker, BentoML, ML pipelines, scale, model monitoring."
    ),
    "backend_engineering": (
        "Backend software engineering, API development, microservices, databases, "
        "system design, Python, Java, Go, Rust."
    ),
    "data_engineering": (
        "Data engineering, data pipelines, ETL, stream processing, batch processing, "
        "Spark, PySpark, Airflow, Snowflake, BigQuery."
    ),
    "frontend_engineering": (
        "Frontend software engineering, React, Next.js, UI, UX, web applications, "
        "JavaScript, TypeScript, HTML, CSS."
    ),
    "qa_engineering": (
        "Quality assurance, QA engineering, software testing, test automation, "
        "Selenium, Playwright, Cypress, SDET, CI/CD."
    ),
    "cloud_engineering": (
        "Cloud engineering, DevOps, infrastructure as code, AWS, Azure, GCP, "
        "Terraform, Kubernetes, Docker, site reliability."
    ),
}

# Redrob Skill Assessments mapped to capabilities
ASSESSMENT_MAPPING: dict[str, list[str]] = {
    "nlp": ["embeddings"],
    "machine learning": ["ranking", "evaluation", "embeddings"],
    "information retrieval": ["retrieval", "ranking", "evaluation", "search_infrastructure"],
    "recommendation systems": ["ranking", "retrieval", "recommendation"],
    "fine-tuning llms": ["embeddings", "evaluation"],
    "python": ["backend_engineering"],
    "feature engineering": ["ranking", "evaluation", "data_engineering"],
    "mlops": ["production_ml", "evaluation"],
    "mlflow": ["production_ml", "evaluation"],
    "faiss": ["vector_databases", "retrieval"],
    "pinecone": ["vector_databases", "retrieval"],
    "qdrant": ["vector_databases", "retrieval"],
    "weaviate": ["vector_databases", "retrieval"],
    "milvus": ["vector_databases", "retrieval"],
    "elasticsearch": ["search_infrastructure", "retrieval", "vector_databases"],
    "opensearch": ["search_infrastructure", "retrieval", "vector_databases"],
    "hugging face": ["embeddings", "retrieval"],
    "huggingface": ["embeddings", "retrieval"],
    "kubeflow": ["production_ml", "evaluation"],
    "transformers": ["embeddings"],
    "rag": ["retrieval", "embeddings", "vector_databases"],
    "prompt engineering": ["embeddings"],
    "gans": ["embeddings"],
    "object detection": ["production_ml"],
    "opencv": ["production_ml"]
}

# Premium tech/product companies for Environment Quality Boost
PREMIUM_COMPANIES = {
    "google", "microsoft", "amazon", "meta", "netflix", "apple", "uber", "swiggy",
    "flipkart", "zomato", "meesho", "ola", "paytm", "phonepe", "cred", "razorpay",
    "stripe", "airbnb", "atlassian", "adobe", "nvidia", "goldman sachs", "salesforce"
}

# Configurable capability gates (Direct, Strong Adjacent, Semantic Anchor terms)
CAPABILITY_GATES: dict[str, dict[str, list[str]]] = {
    "retrieval": {
        "direct": ["retrieval", "information retrieval", "vector search", "semantic search", "hybrid search", "dense retrieval", "bm25", "elasticsearch", "opensearch", "lucene", "solr", "search engineer", "search relevance engineer", "information retrieval engineer", "search platform engineer"],
        "strong_adjacent": ["candidate matching", "relevance optimization", "search quality", "matching infrastructure"],
        "anchor": ["dense vector representations", "embedding-powered matching", "similarity search infrastructure", "semantic matching platform"]
    },
    "ranking": {
        "direct": ["ranking", "learning to rank", "relevance ranking", "ndcg", "mrr", "ctr optimization", "reranking", "re-ranking"],
        "strong_adjacent": ["relevance optimization", "search quality"],
        "anchor": ["embedding-powered matching"]
    },
    "recommendation": {
        "direct": ["recommendation system", "recommender system", "personalization", "feed ranking", "candidate ranking"],
        "strong_adjacent": ["personalization engine", "recommendation pipeline"],
        "anchor": ["embedding-powered matching"]
    },
    "search_infrastructure": {
        "direct": ["search platform", "search relevance", "search infrastructure", "indexing", "search engineer", "search relevance engineer", "information retrieval engineer", "search platform engineer"],
        "strong_adjacent": ["search quality"],
        "anchor": ["similarity search infrastructure"]
    },
    "embeddings": {
        "direct": ["embedding", "embeddings", "sentence transformers", "bert", "transformers"],
        "strong_adjacent": ["pytorch", "tensorflow"],
        "anchor": ["prompt engineering", "llm", "fine-tuning"]
    },
    "vector_databases": {
        "direct": ["vector database", "vector search", "vector store"],
        "strong_adjacent": ["faiss", "qdrant", "weaviate", "pinecone", "milvus"],
        "anchor": ["hybrid search", "semantic search"]
    },
    "evaluation": {
        "direct": ["evaluation", "offline benchmark", "evaluation metrics"],
        "strong_adjacent": ["ndcg", "mrr", "map"],
        "anchor": ["weights & biases", "mlflow"]
    },
    "production_ml": {
        "direct": ["production ml", "deployed", "model deployment"],
        "strong_adjacent": ["kubeflow", "mlflow", "bentoml", "sagemaker"],
        "anchor": ["docker", "kubernetes", "airflow"]
    },
    "backend_engineering": {
        "direct": ["backend", "software engineer", "api", "microservices"],
        "strong_adjacent": ["python", "java", "go", "rust"],
        "anchor": ["sql", "postgresql", "redis", "kafka"]
    },
    "data_engineering": {
        "direct": ["data engineering", "data pipeline", "etl"],
        "strong_adjacent": ["spark", "pyspark", "airflow", "snowflake", "bigquery"],
        "anchor": ["kafka", "flink"]
    },
    "frontend_engineering": {
        "direct": ["frontend", "ui", "ux", "web application"],
        "strong_adjacent": ["react", "next.js", "javascript", "typescript"],
        "anchor": ["webpack", "vite"]
    },
    "qa_engineering": {
        "direct": ["qa", "quality assurance", "test engineer", "testing"],
        "strong_adjacent": ["selenium", "playwright", "cypress", "pytest"],
        "anchor": ["jenkins", "ci/cd"]
    },
    "cloud_engineering": {
        "direct": ["cloud engineer", "devops", "sre", "infrastructure"],
        "strong_adjacent": ["aws", "azure", "gcp", "terraform"],
        "anchor": ["linux", "bash"]
    }
}


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two numpy vectors."""
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(dot / (norm1 * norm2))


@dataclass(frozen=True)
class RoleAlignmentResult:
    """Component and final scores for candidate-to-JD role alignment."""

    evidence_score: float
    raw_semantic_score: float
    domain_relevance: float
    effective_semantic_score: float
    semantic_score: float
    career_relevance_score: float
    experience_fit_score: float
    domain_gate_applied: bool
    domain_gate_penalty: float
    final_score: float
    degraded_confidence: bool
    career_evidence_score: float
    self_claim_score: float

    # V4 fields
    capability_fit_score: float = 0.0
    evidence_strength_score: float = 0.0
    ownership_score: float = 0.0
    prior_multiplier: float = 1.0
    support_ratio: float = 1.0
    lexical_similarity_score: float = 0.0
    capability_scores: dict[str, float] = field(default_factory=dict)
    capability_breakdowns: dict[str, dict[str, float]] = field(default_factory=dict)
    requirements: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable score dictionary."""
        return asdict(self)


class RoleAlignmentEngine:
    """Score candidate-to-JD alignment using SentenceTransformer embeddings."""

    def __init__(self, model_name: str | None = None) -> None:
        self.embedding_manager = EmbeddingManager(model_name)
        self._model_status = {
            "loaded": True,
            "status_message": f"SentenceTransformer active ({self.embedding_manager.model_name}) in PRISM V4.",
            "running_degraded": False
        }

    @property
    def model_status(self) -> dict[str, bool | str]:
        return self._model_status

    def get_gate_confidence(self, text: str, cap: str) -> float:
        """Compute gate confidence based on direct, strong adjacent, or semantic anchor terms."""
        text_lower = text.lower()
        gates = CAPABILITY_GATES.get(cap, {})
        
        # 1. Direct Evidence: 1.0
        for term in gates.get("direct", []):
            if re.search(rf"\b{re.escape(term.lower())}s?\b", text_lower):
                return 1.0
                
        # 2. Strong Adjacent Evidence: 0.7
        for term in gates.get("strong_adjacent", []):
            if re.search(rf"\b{re.escape(term.lower())}s?\b", text_lower):
                return 0.7
                
        # 3. Semantic Anchor Evidence: 0.4
        for term in gates.get("anchor", []):
            if re.search(rf"\b{re.escape(term.lower())}s?\b", text_lower):
                return 0.4
                
        return 0.0

    def extract_role_requirements(self, jd_profile: JDProfile) -> dict[str, list[str]]:
        """Classify capabilities into Mandatory, Important, Optional, and Low Value."""
        title_lower = jd_profile.title.lower()
        must_have_text = " ".join(jd_profile.must_have).lower()
        good_to_have_text = " ".join(jd_profile.good_to_have).lower()
        full_jd_text = f"{title_lower} {must_have_text} {good_to_have_text}"

        is_retrieval_jd = any(term in full_jd_text for term in ("retrieval", "search", "ranking", "recommendation", "recommender", "matching"))

        if is_retrieval_jd:
            mandatory = ["retrieval", "ranking", "recommendation", "vector_databases", "embeddings", "search_infrastructure"]
            important = ["production_ml", "evaluation", "data_engineering", "backend_engineering"]
            optional = ["cloud_engineering"]
            low_value = ["frontend_engineering", "qa_engineering"]
        else:
            # Dynamic fallback classification
            mandatory = []
            important = []
            for cap in CAPABILITY_DESCRIPTIONS:
                cap_emb = self.embedding_manager.get_embedding(CAPABILITY_DESCRIPTIONS[cap])
                jd_emb = self.embedding_manager.get_embedding(full_jd_text)
                sim = cosine_similarity(jd_emb, cap_emb)
                if sim >= 0.40:
                    mandatory.append(cap)
                elif sim >= 0.25:
                    important.append(cap)
            
            if not mandatory:
                mandatory = ["retrieval", "ranking", "vector_databases"]
            if not important:
                important = ["production_ml", "evaluation", "data_engineering", "backend_engineering"]
                
            optional = [c for c in CAPABILITY_DESCRIPTIONS if c not in mandatory and c not in important and c not in ("frontend_engineering", "qa_engineering")]
            low_value = ["frontend_engineering", "qa_engineering"]

        return {
            "mandatory": mandatory,
            "important": important,
            "optional": optional,
            "low_value": low_value
        }

    def score(self, jd_profile: JDProfile, candidate: CandidateProfile) -> RoleAlignmentResult:
        """Score candidate capabilities and fit against the Job Description."""
        reqs = self.extract_role_requirements(jd_profile)
        mandatory = reqs["mandatory"]

        # Compute capability scores & breakdowns
        capability_scores, breakdowns = self.compute_capability_scores(candidate, mandatory)

        # Compute Fit & Strengths
        capability_fit_score = self.calculate_capability_fit(capability_scores, reqs)
        evidence_strength_score = sum(capability_scores.values()) / len(capability_scores)
        ownership_score = self.calculate_ownership_score(candidate)

        # Hierarchy Multiplier (Prior Probability)
        tier_name, prior_multiplier = self.get_recruiter_hierarchy_multiplier(candidate, capability_scores)

        # Support Ratio (Confidence Multiplier)
        support_ratio = self.calculate_support_ratio(capability_scores, breakdowns)

        # Apply support ratio to Fit & Strength
        gated_fit = capability_fit_score * (0.30 + 0.70 * support_ratio)
        gated_strength = evidence_strength_score * (0.30 + 0.70 * support_ratio)

        # Experience Fit
        experience_fit_score = self.score_experience_fit(jd_profile, candidate)

        # Lexical Similarity represents overall semantic matching in V4
        lexical_similarity_score = self.score_lexical_similarity(jd_profile, candidate)

        # Combined final alignment score (weighted)
        final_alignment_score = (
            (0.70 * gated_fit + 0.25 * gated_strength + 0.05 * experience_fit_score)
            * prior_multiplier
        )

        mock_evidence_score = gated_strength
        mock_domain_relevance = support_ratio

        domain_gate_applied = support_ratio < 0.2
        domain_gate_penalty = 0.8 if domain_gate_applied else 1.0
        if domain_gate_applied:
            final_alignment_score *= domain_gate_penalty

        return RoleAlignmentResult(
            evidence_score=round(mock_evidence_score, 2),
            raw_semantic_score=round(lexical_similarity_score, 2),
            domain_relevance=round(mock_domain_relevance, 3),
            effective_semantic_score=round(lexical_similarity_score, 2),
            semantic_score=round(lexical_similarity_score, 2),
            career_relevance_score=round(gated_fit, 2),
            experience_fit_score=round(experience_fit_score, 2),
            domain_gate_applied=domain_gate_applied,
            domain_gate_penalty=round(domain_gate_penalty, 2),
            final_score=round(final_alignment_score, 2),
            degraded_confidence=False,
            career_evidence_score=round(gated_fit, 2),
            self_claim_score=round(
                (sum(bd.get("claim_evidence", 0.0) for bd in breakdowns.values()) / len(breakdowns))
                if breakdowns else 0.0,
                2
            ),
            capability_fit_score=round(capability_fit_score, 2),
            evidence_strength_score=round(evidence_strength_score, 2),
            ownership_score=round(ownership_score, 2),
            prior_multiplier=round(prior_multiplier, 2),
            support_ratio=round(support_ratio, 2),
            lexical_similarity_score=round(lexical_similarity_score, 2),
            capability_scores={k: round(v, 2) for k, v in capability_scores.items()},
            capability_breakdowns=breakdowns,
            requirements=reqs
        )

    def score_without_domain_gate(self, jd_profile: JDProfile, candidate: CandidateProfile) -> RoleAlignmentResult:
        """Identical to score() in PRISM V4."""
        return self.score(jd_profile, candidate)

    def analyze_ownership(self, description: str, cap_terms: tuple[str, ...]) -> float:
        """Analyze sentence-level context for ownership actions vs passive usage of capabilities."""
        desc_lower = description.lower()
        ownership_verbs = {"architected", "led", "owned", "designed", "built", "deployed", "scaled", "shipped", "spearheaded", "drove", "implemented", "migrated"}
        passive_verbs = {"worked on", "used", "assisted", "supported", "learned", "competence", "exposure", "familiar with", "exposure to", "familiarity"}

        sentences = re.split(r'[.!?\n]', desc_lower)
        max_multiplier = 1.0

        for sentence in sentences:
            has_cap = any(term in sentence for term in cap_terms)
            if not has_cap:
                continue

            has_owner = any(verb in sentence for verb in ownership_verbs)
            has_passive = any(verb in sentence for verb in passive_verbs)

            if has_owner:
                max_multiplier = max(max_multiplier, 1.25)
            elif has_passive:
                max_multiplier = min(max_multiplier, 0.85)

        return max_multiplier

    def compute_capability_scores(self, candidate: CandidateProfile, mandatory_capabilities: list[str]) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
        """Compute candidate score for each capability based on Career, Project, Assessment, and Skills."""
        scores = {}
        breakdowns = {}

        summary_text = f"{candidate.headline} {candidate.summary} {candidate.title}"

        for cap in CAPABILITY_DESCRIPTIONS:
            cap_desc = CAPABILITY_DESCRIPTIONS[cap]
            emb_C = self.embedding_manager.get_embedding(cap_desc)
            cap_terms = CAPABILITY_GATES[cap]["direct"] + CAPABILITY_GATES[cap]["strong_adjacent"]

            # 1. Career Evidence
            career_ev = 0.0
            job_contribs = []
            num_relevant_jobs = 0

            for job in candidate.career_history:
                job_text = f"{job.title} at {job.company}. {job.description}"
                emb_job = self.embedding_manager.get_embedding(job_text)
                sim_job = cosine_similarity(emb_job, emb_C)

                emb_title = self.embedding_manager.get_embedding(job.title)
                sim_title = cosine_similarity(emb_title, emb_C)

                contrib = 0.7 * sim_job + 0.3 * max(sim_job, sim_title)
                
                # Check for Environment Quality (Premium Product Company)
                comp_lower = job.company.lower()
                is_premium = any(pc in comp_lower for pc in PREMIUM_COMPANIES)

                # Step 2: Gate Confidence for this job
                gate_conf = self.get_gate_confidence(job_text, cap)

                # Step 3: Combine both
                if contrib >= 0.28 and gate_conf > 0.0:
                    # Map to range [30.0, 100.0]
                    score_contrib = 30.0 + (contrib - 0.28) / (0.60 - 0.28) * 70.0
                    score_contrib = min(100.0, max(30.0, score_contrib))
                    
                    # Reward ownership action verbs vs passive usage
                    ownership_mult = self.analyze_ownership(job.description, cap_terms)
                    score_contrib = score_contrib * ownership_mult

                    # Apply gate confidence
                    score_contrib = score_contrib * gate_conf

                    # Boost slightly for premium environment (5-10% of evidence strength)
                    if is_premium:
                        score_contrib = score_contrib * 1.08
                        
                    score_contrib = min(100.0, score_contrib)
                    job_contribs.append(score_contrib)
                    num_relevant_jobs += 1
                else:
                    job_contribs.append(0.0)

            if job_contribs:
                max_contrib = max(job_contribs)
                if max_contrib > 0.0:
                    # Apply Recurrence Multiplier (how many times they did it)
                    recurrence_mult = 1.0
                    if num_relevant_jobs == 2:
                        recurrence_mult = 1.20
                    elif num_relevant_jobs >= 3:
                        recurrence_mult = 1.35
                    
                    career_ev = min(100.0, max_contrib * recurrence_mult)

            # 2. Project Evidence
            project_ev = 0.0
            if candidate.summary:
                emb_summary = self.embedding_manager.get_embedding(summary_text)
                sim_summary = cosine_similarity(emb_summary, emb_C)
                gate_conf_proj = self.get_gate_confidence(summary_text, cap)
                if sim_summary >= 0.30 and gate_conf_proj > 0.0:
                    project_ev = min(100.0, 30.0 + (sim_summary - 0.30) / (0.60 - 0.30) * 70.0)
                    project_ev = project_ev * gate_conf_proj

            # 3. Assessment Evidence
            assess_ev = self._calculate_assessment_evidence(candidate, cap)

            # 4. Skill Claims
            skill_ev = 0.0
            skill_names = [s.name.lower() for s in candidate.skills]
            matched_terms = 0
            for term in cap_terms:
                if any(term in sn for sn in skill_names):
                    matched_terms += 1
            if matched_terms > 0:
                skill_ev = min(100.0, matched_terms * 35.0)

            # Evidence Hierarchy combination (60% Career, 20% Project, 15% Assessment, 5% Skills)
            confidence = (
                0.60 * career_ev
                + 0.20 * project_ev
                + 0.15 * assess_ev
                + 0.05 * skill_ev
            )

            # Strict Core Evidence Gate: cap mandatory capabilities with zero evidence to 10.0 max
            if cap in mandatory_capabilities:
                if career_ev == 0.0 and project_ev == 0.0 and assess_ev == 0.0:
                    confidence = min(10.0, confidence)

            scores[cap] = confidence
            breakdowns[cap] = {
                "claim_evidence": skill_ev,
                "career_evidence": career_ev,
                "skill_evidence": skill_ev,
                "assessment_evidence": assess_ev,
                "project_evidence": project_ev,
                "confidence": confidence,
                "num_relevant_jobs": num_relevant_jobs
            }

        return scores, breakdowns

    def _calculate_assessment_evidence(self, candidate: CandidateProfile, capability: str) -> float:
        """Fetch average score of Redrob assessments that map to the capability."""
        scores = []
        for assess_name, score in candidate.recruiter_signals.skill_assessment_scores.items():
            name_lower = assess_name.lower().strip()
            for key, caps in ASSESSMENT_MAPPING.items():
                if key in name_lower and capability in caps:
                    scores.append(float(score))
                    break
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def get_recruiter_hierarchy_multiplier(self, candidate: CandidateProfile, capability_scores: dict[str, float] = None) -> tuple[str, float]:
        """Classify title into tiers and retrieve recruiter priority multiplier based on capability evidence."""
        title = candidate.title.lower().strip()
        history_titles = [job.title.lower() for job in candidate.career_history]
        all_titles = [title] + history_titles

        # Calculate max core career evidence from capability scores
        has_core_evidence = False
        if capability_scores:
            core_caps = ["retrieval", "ranking", "recommendation", "search_infrastructure", "vector_databases", "embeddings"]
            for cap in core_caps:
                if capability_scores.get(cap, 0.0) >= 30.0:
                    has_core_evidence = True
                    break

        # Check for search-related titles
        search_titles = ["search engineer", "search relevance engineer", "information retrieval engineer", "search platform engineer"]
        has_search_title = any(any(st in t for st in search_titles) for t in all_titles)

        # Tier A: Specialists with core career evidence
        is_specialist_title = has_search_title or any(any(term in t for term in ("search", "retrieval", "recommendation", "recommender", "ranking")) for t in all_titles)
        if is_specialist_title and has_core_evidence:
            multiplier = 1.40 if has_search_title else 1.30
            return "Tier A", multiplier

        # Tier B: Core ML/NLP/Data Engineers with core/adjacent career evidence
        is_ml_data_title = any(any(term in t for term in ("machine learning", "ml", "ai", "applied ai", "data engineer", "nlp", "deep learning", "scientist", "researcher")) for t in all_titles)
        if is_ml_data_title and has_core_evidence:
            return "Tier B", 1.10

        # Tier C: Other Devs or Backend Engineers with some career evidence
        is_tech = any(any(term in t for term in ("engineer", "developer", "programmer", "backend", "software")) for t in all_titles)
        if (is_tech and has_core_evidence) or has_search_title:
            return "Tier C", 1.00

        # Tier D: Generic, Frontend, QA, or non-technical profiles
        return "Tier D", 0.50

    def calculate_support_ratio(self, scores: dict[str, float], breakdowns: dict[str, dict[str, float]]) -> float:
        """Measure consistency of claims vs career/project/assessment evidence."""
        claimed = 0
        verified = 0

        for cap, breakdown in breakdowns.items():
            is_claimed = (breakdown["claim_evidence"] > 0.0)
            is_verified = (breakdown["career_evidence"] >= 30.0) or (breakdown["project_evidence"] >= 30.0) or (breakdown["assessment_evidence"] >= 30.0)

            if is_claimed:
                claimed += 1
            if is_verified:
                verified += 1

        if claimed == 0:
            return 1.0 if verified > 0 else 0.5

        return min(1.0, verified / claimed)

    def calculate_ownership_score(self, candidate: CandidateProfile) -> float:
        """Scan career history descriptions for ownership action verbs in technical contexts."""
        verbs = {
            "architected", "led", "owned", "designed", "built", "deployed",
            "scaled", "shipped", "operated", "managed", "spearheaded", "drove"
        }
        hits = 0
        for job in candidate.career_history:
            desc_lower = job.description.lower()
            for verb in verbs:
                if re.search(rf"\b{re.escape(verb)}\b", desc_lower):
                    hits += 1
        return min(100.0, hits * 15.0)

    def calculate_capability_fit(self, scores: dict[str, float], reqs: dict[str, list[str]]) -> float:
        """Calculate capability fit, penalizing low-value capabilities (Frontend/QA)."""
        mandatory = reqs.get("mandatory", [])
        important = reqs.get("important", [])
        optional = reqs.get("optional", [])
        low_value = reqs.get("low_value", ["frontend_engineering", "qa_engineering"])

        m_score = sum(scores.get(cap, 0.0) for cap in mandatory) / len(mandatory) if mandatory else 0.0
        i_score = sum(scores.get(cap, 0.0) for cap in important) / len(important) if important else 0.0
        o_score = sum(scores.get(cap, 0.0) for cap in optional) / len(optional) if optional else 0.0
        l_score = sum(scores.get(cap, 0.0) for cap in low_value) / len(low_value) if low_value else 0.0

        fit = 0.60 * m_score + 0.30 * i_score + 0.10 * o_score

        # Apply Frontend/QA low-value capability penalty
        if l_score > m_score:
            penalty = 0.5 * (l_score - m_score)
            fit = max(0.0, fit - penalty)

        return fit

    def score_lexical_similarity(self, jd_profile: JDProfile, candidate: CandidateProfile) -> float:
        """Compute semantic similarity between overall JD and candidate profile."""
        jd_text = f"{jd_profile.title}. {' '.join(jd_profile.must_have)}. {' '.join(jd_profile.good_to_have)}"
        cand_text = f"{candidate.headline}. {candidate.summary}. {candidate.title}. " + " ".join(
            f"{item.title}: {item.description}" for item in candidate.career_history
        )

        emb_jd = self.embedding_manager.get_embedding(jd_text)
        emb_cand = self.embedding_manager.get_embedding(cand_text)

        sim = cosine_similarity(emb_jd, emb_cand)
        # Scale to range [0.0, 100.0]
        normalized_sim = min(100.0, max(0.0, (sim - 0.20) / (0.70 - 0.20) * 100.0))
        return normalized_sim

    def score_experience_fit(self, jd_profile: JDProfile, candidate: CandidateProfile) -> float:
        """Score experience fit compared to preferred range."""
        if jd_profile.experience_min is None or jd_profile.experience_max is None:
            return 100.0

        years = candidate.years_of_experience
        lower = float(jd_profile.experience_min)
        upper = float(jd_profile.experience_max)

        if lower <= years <= upper:
            midpoint = (lower + upper) / 2.0
            half_width = max((upper - lower) / 2.0, 1.0)
            midpoint_distance = abs(years - midpoint)
            return max(90.0, 100.0 - (midpoint_distance / half_width) * 10.0)

        nearest_bound = lower if years < lower else upper
        distance = abs(years - nearest_bound)
        return max(0.0, 85.0 - distance * 15.0)
