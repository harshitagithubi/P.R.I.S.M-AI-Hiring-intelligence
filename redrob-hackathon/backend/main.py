"""FastAPI backend for P.R.I.S.M AI."""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from candidate.candidate_parser import CandidateParser
from explainability.explainer import ExplainabilityEngine
from jd.jd_parser import DEFAULT_JD_PATH, JDParser
from scoring.dataset_grounded_audit import audit_candidate
from scoring.market_validation import MarketValidationEngine
from scoring.prism_ranker import PRISMRankingEngine
from scoring.recruitability import RecruitabilityEngine
from scoring.role_alignment import RoleAlignmentEngine
from scoring.skill_proof import SkillProofEngine
from scoring.sanity_checks import run_post_ranking_audit


import tempfile

try:
    UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    UPLOAD_DIR = Path(tempfile.gettempdir()) / "prism_uploads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_CANDIDATES_PATH = UPLOAD_DIR / "sample_candidates.json"

app = FastAPI(title="P.R.I.S.M AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE: dict[str, Any] = {
    "jd_path": DEFAULT_JD_PATH,
    "candidate_path": DEFAULT_CANDIDATES_PATH,
    "cache": None,
}


@app.post("/upload-jd")
async def upload_jd(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a JD file."""
    path = await save_upload(file)

    STATE["jd_path"] = path
    STATE["cache"] = None

    print("=" * 60)
    print("JD UPLOADED")
    print("Filename:", file.filename)
    print("Saved Path:", path)
    print("Current STATE jd_path:", STATE["jd_path"])
    print("=" * 60)

    return {"status": "ok", "path": str(path)}


@app.post("/upload-candidates")
async def upload_candidates(file: UploadFile = File(...)) -> dict[str, str]:
    """Upload a candidate JSON file."""
    path = await save_upload(file)

    STATE["candidate_path"] = path
    STATE["cache"] = None

    print("=" * 60)
    print("CANDIDATE FILE UPLOADED")
    print("Filename:", file.filename)
    print("Saved Path:", path)
    print("Current STATE candidate_path:", STATE["candidate_path"])
    print("=" * 60)

    return {"status": "ok", "path": str(path)}


@app.post("/screen")
def screen() -> dict[str, Any]:
    """Run PRISM screening."""
    import time
    print("[API Response Serialization] START")
    t0 = time.time()
    STATE["cache"] = run_screening(Path(STATE["jd_path"]), Path(STATE["candidate_path"]))
    tier_counts = count_tiers(STATE["cache"]["rankings"])
    response = {
        "status": "ok",
        "total_candidates": len(STATE["cache"]["candidates"]),
        "tier_counts": tier_counts,
        "rankings": STATE["cache"]["rankings"][:20],
        "metadata": {
            "model_status": STATE["cache"].get("model_status"),
            "audit_report": STATE["cache"].get("audit_report"),
        }
    }
    t_api = time.time() - t0
    print(f"[API Response Serialization] END. ELAPSED TIME: {t_api:.4f}s")
    print(f"Candidate count processed: {len(STATE['cache']['candidates'])}")
    if t_api > 5.0:
        print("[SLOW STAGE DETECTED] API Response Serialization exceeded 5 seconds")
    return response


@app.get("/rankings")
def rankings() -> dict[str, Any]:
    """Return rankings along with metadata."""
    cache = ensure_cache()
    return {
        "rankings": cache["rankings"],
        "metadata": {
            "model_status": cache.get("model_status"),
            "audit_report": cache.get("audit_report"),
        }
    }


@app.get("/candidate/{candidate_id}")
def candidate_detail(candidate_id: str) -> dict[str, Any]:
    """Return candidate profile and score components."""
    cache = ensure_cache()
    candidate = cache["candidate_by_id"].get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {
        "profile": candidate.to_dict(),
        "ranking": cache["ranking_by_id"].get(candidate_id),
        "components": cache["components"].get(candidate_id),
    }


@app.get("/candidate/{candidate_id}/explanation")
def candidate_explanation(candidate_id: str) -> dict[str, Any]:
    """Return candidate explanation."""
    cache = ensure_cache()
    explanation = cache["explanation_by_id"].get(candidate_id)
    if explanation is None:
        raise HTTPException(status_code=404, detail="Explanation not found")
    return explanation


@app.get("/audit/{candidate_id}")
def candidate_audit(candidate_id: str) -> dict[str, Any]:
    """Return raw dataset audit for a candidate."""
    cache = ensure_cache()
    raw = cache["raw_candidate_by_id"].get(candidate_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return audit_candidate(raw).to_dict()


async def save_upload(file: UploadFile) -> Path:
    """Save uploaded file safely and completely with fallback path handling."""
    import os, tempfile
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        path = UPLOAD_DIR / file.filename
    except Exception:
        fallback = Path(tempfile.gettempdir()) / "prism_uploads"
        fallback.mkdir(parents=True, exist_ok=True)
        path = fallback / file.filename

    await file.seek(0)
    content = await file.read()
    with path.open("wb") as handle:
        handle.write(content)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    return path


def ensure_cache() -> dict[str, Any]:
    """Return screening cache, running if needed."""
    if STATE["cache"] is None:
        STATE["cache"] = run_screening(Path(STATE["jd_path"]), Path(STATE["candidate_path"]))
    return STATE["cache"]


def run_screening(jd_path: Path, candidate_path: Path) -> dict[str, Any]:
    """Run all PRISM modules and persist outputs."""
    import time

    print("=" * 60)
    print("RUN SCREENING")
    print("JD PATH USED:", jd_path)
    print("CANDIDATE PATH USED:", candidate_path)
    print("=" * 60)

    # 1. JD parsing
    print("[JD Parsing] START")
    t0_jd = time.time()
    jd = JDParser(jd_path).parse()
    t_jd = time.time() - t0_jd
    print(f"[JD Parsing] END. ELAPSED TIME: {t_jd:.4f}s")
    if t_jd > 5.0:
        print("[SLOW STAGE DETECTED] JD Parsing exceeded 5 seconds")

    
    # 2. Candidate loading
    print("[Candidate Loading] START")
    t0_load = time.time()

    candidates = CandidateParser(candidate_path).parse_all()

    print("FIRST 3 CANDIDATE IDS:")
    for c in candidates[:3]:
        print(c.candidate_id)

    raw_candidates = json.loads(
        candidate_path.read_text(encoding="utf-8")
    )

    # Create lookup dictionaries for fast access
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    raw_candidate_by_id = {candidate["candidate_id"]: candidate for candidate in raw_candidates}

    # Initialize result containers
    rankings_payload: list[dict[str, Any]] = []
    components: dict[str, Any] = {}
    explanations: list[dict[str, Any]] = []

    t_load = time.time() - t0_load

    print(f"[Candidate Loading] END. ELAPSED TIME: {t_load:.4f}s")
    print(f"Candidate count processed: {len(candidates)}")

    if t_load > 5.0:
        print("[SLOW STAGE DETECTED] Candidate Loading exceeded 5 seconds")# 2. Candidate loading
    # print("[Candidate Loading] START")
    # candidates = CandidateParser(candidate_path).parse_all()

    # print("FIRST 3 CANDIDATE IDS:")
    # for c in candidates[:3]:
    #     print(c.candidate_id)
    # raw_candidates = json.loads(candidate_path.read_text(encoding="utf-8"))
    # t_load = time.time() - t0_load
    # print(f"[Candidate Loading] END. ELAPSED TIME: {t_load:.4f}s")
    # print(f"Candidate count processed: {len(candidates)}")
    # if t_load > 5.0:
    #     print("[SLOW STAGE DETECTED] Candidate Loading exceeded 5 seconds")

    # 3. Scoring loop
    print("[Scoring Loop] START")
    t0_score = time.time()

    role = RoleAlignmentEngine()
    skill = SkillProofEngine()
    recruitability = RecruitabilityEngine()
    market = MarketValidationEngine()

    ranker = PRISMRankingEngine(
        role,
        skill,
        recruitability,
        market,
    )

    explainer = ExplainabilityEngine()

    ranking_results = ranker.rank_candidates(
        jd,
        candidates,
        limit=100,
   )

    print("TOP 5 RANKED:")
    for r in ranking_results[:5]:
        print(r.candidate_id)

    t_score = time.time() - t0_score

    print(f"[Scoring Loop] END. ELAPSED TIME: {t_score:.4f}s")
    print(f"Candidate count processed: {len(candidates)}")

    if t_score > 5.0:
        print("[SLOW STAGE DETECTED] Scoring Loop exceeded 5 seconds")

    # 4. Fraud detection
    print("[Fraud Detection] START")
    t0_fraud = time.time()
    for ranking in ranking_results:
        candidate = candidate_by_id[ranking.candidate_id]
        role_result = role.score(jd, candidate)
        skill_result = skill.score(candidate)
        recruitability_result = recruitability.score(candidate)
        market_result = market.score(candidate)
        raw_candidate = raw_candidate_by_id[candidate.candidate_id]
        audit_result = audit_candidate(raw_candidate)
        flags = build_flags(candidate, skill_result.to_dict(), audit_result.to_dict())
        risks = build_risks(candidate, role_result.to_dict(), skill_result.to_dict(), recruitability_result.to_dict(), flags)
        score_reasons = build_score_reasons(
            role_result.to_dict(),
            skill_result.to_dict(),
            recruitability_result.to_dict(),
            market_result.to_dict(),
        )
        record = ranking.to_dict()
        record["title"] = candidate.title
        record["current_company"] = candidate.current_company
        record["current_industry"] = candidate.current_industry
        record["location"] = candidate.location
        record["skills"] = [skill.name for skill in candidate.skills]
        record["open_to_work"] = candidate.recruiter_signals.open_to_work_flag
        record["notice_period_days"] = candidate.recruiter_signals.notice_period_days
        record["years_of_experience"] = candidate.years_of_experience
        record["flags"] = flags
        record["risks"] = risks
        record["score_reasons"] = score_reasons
        rankings_payload.append(record)
        components[candidate.candidate_id] = {
            "role_alignment": role_result.to_dict(),
            "skill_proof": skill_result.to_dict(),
            "recruitability": recruitability_result.to_dict(),
            "market_validation": market_result.to_dict(),
            "score_reasons": score_reasons,
            "flags": flags,
            "risks": risks,
            "audit": audit_result.to_dict(),
        }
    t_fraud = time.time() - t0_fraud
    print(f"[Fraud Detection] END. ELAPSED TIME: {t_fraud:.4f}s")
    print(f"Candidate count processed: {len(ranking_results)}")
    if t_fraud > 5.0:
        print("[SLOW STAGE DETECTED] Fraud Detection exceeded 5 seconds")

    # 5. Explanation generation
    print("[Explanation Generation] START")
    t0_explain = time.time()
    for ranking in ranking_results:
        candidate = candidate_by_id[ranking.candidate_id]
        explanations.append(explainer.explain_candidate(jd, candidate, ranking).to_dict())
    t_explain = time.time() - t0_explain
    print(f"[Explanation Generation] END. ELAPSED TIME: {t_explain:.4f}s")
    print(f"Candidate count processed: {len(ranking_results)}")
    if t_explain > 5.0:
        print("[SLOW STAGE DETECTED] Explanation Generation exceeded 5 seconds")

    audit_report = run_post_ranking_audit(ranking_results)

    cache = {
        "jd": jd.to_dict(),
        "candidates": candidates,
        "candidate_by_id": candidate_by_id,
        "raw_candidate_by_id": raw_candidate_by_id,
        "rankings": rankings_payload,
        "ranking_by_id": {item["candidate_id"]: item for item in rankings_payload},
        "components": components,
        "explanations": explanations,
        "explanation_by_id": {item["candidate_id"]: item for item in explanations},
        "model_status": role.model_status,
        "audit_report": audit_report,
    }
    write_outputs(cache)
    return cache


def write_outputs(cache: dict[str, Any]) -> None:
    """Persist API outputs."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "jd": cache["jd"],
        "rankings": cache["rankings"],
        "components": cache["components"],
        "explanations": cache["explanations"],
    }
    (OUTPUT_DIR / "final_rankings.json").write_text(json.dumps(cache["rankings"], indent=2), encoding="utf-8")
    (OUTPUT_DIR / "top20_candidates.json").write_text(json.dumps(cache["rankings"][:20], indent=2), encoding="utf-8")
    (OUTPUT_DIR / "explanations.json").write_text(json.dumps(cache["explanations"], indent=2), encoding="utf-8")
    (OUTPUT_DIR / "dashboard_cache.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def count_tiers(rankings: list[dict[str, Any]]) -> dict[str, int]:
    """Count qualification tiers across all ranked candidates."""
    return {
        "strong": sum(1 for item in rankings if item["qualification_tier"] == "Strong Match"),
        "near": sum(1 for item in rankings if item["qualification_tier"] == "Near Match"),
        "weak": sum(1 for item in rankings if item["qualification_tier"] == "Weak Signal"),
        "flagged": sum(1 for item in rankings if item["qualification_tier"] == "Honeypot"),
        "not_qualified": sum(1 for item in rankings if item["qualification_tier"] == "Not Qualified"),
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

NON_AI_CAREER_TERMS = (
    "brand design",
    "graphic designer",
    "customer support",
    "sales executive",
    "marketing manager",
    "accountant",
    "hr manager",
    "mechanical engineering",
    "civil engineer",
    "operations manager",
    "project manager",
    "business analyst",
)


def build_flags(
    candidate: Any,
    skill_result: dict[str, Any],
    audit_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build honeypot and contradiction flags for the UI."""
    claimed = claimed_ai_skills(candidate)
    career_text = career_evidence_text(candidate)
    career_preview = career_chain(candidate)
    flags: list[dict[str, Any]] = []

    # 1. Multiple Current Jobs
    current_jobs = sum(1 for job in candidate.career_history if job.is_current)
    if current_jobs > 1:
        flags.append({
            "type": "multiple_current_jobs",
            "severity": "black",
            "label": "Fraud/Honeypot",
            "claimed_skills": claimed,
            "career_evidence": career_preview,
            "rule": "Multiple Current Jobs Detected",
            "detail": f"{candidate.anonymized_name} currently has {current_jobs} current jobs active at the same time."
        })

    # 2. Fake Experience Detection
    total_duration_months = sum(job.duration_months for job in candidate.career_history)
    actual_years = total_duration_months / 12
    claimed_yoe = candidate.years_of_experience
    if claimed_yoe > actual_years + 4:
        flags.append({
            "type": "fake_experience",
            "severity": "black",
            "label": "Fraud/Honeypot",
            "claimed_skills": claimed,
            "career_evidence": career_preview,
            "rule": "Resume Inflation / Fake Experience",
            "detail": f"{candidate.anonymized_name} claims {claimed_yoe:.1f} YOE, but work history shows only {actual_years:.1f} YOE."
        })

    # 3. Wrong Domain Professional
    retrieval_skills = len(claimed)
    title_lower = candidate.title.lower().strip()
    if title_lower in NON_AI_CAREER_TERMS and retrieval_skills > 5:
        flags.append({
            "type": "wrong_domain_professional",
            "severity": "black",
            "label": "Fraud/Honeypot",
            "claimed_skills": claimed,
            "career_evidence": career_preview,
            "rule": "Wrong Domain Professional",
            "detail": f"{candidate.anonymized_name} is a {candidate.title} but claims {retrieval_skills} AI/retrieval skills."
        })

    # 4. Ghost Candidate Detection
    from datetime import datetime, date
    last_active_date = candidate.recruiter_signals.last_active_date
    days_since_active = None
    if last_active_date:
        try:
            parsed = datetime.strptime(last_active_date, "%Y-%m-%d").date()
            days_since_active = (date(2026, 6, 15) - parsed).days
        except ValueError:
            pass
    if days_since_active is not None and days_since_active > 730:
        flags.append({
            "type": "ghost_candidate",
            "severity": "black",
            "label": "Fraud/Honeypot",
            "claimed_skills": claimed,
            "career_evidence": career_preview,
            "rule": "Ghost Candidate (Inactive > 2 years)",
            "detail": f"{candidate.anonymized_name} was last active {days_since_active} days ago."
        })

    has_non_ai_career = any(term in career_text for term in NON_AI_CAREER_TERMS)
    unsupported_claims = bool(claimed) and skill_result["career_evidence_score"] < 10
    if unsupported_claims and (has_non_ai_career or skill_result.get("contradiction_penalty", 0) > 0):
        flags.append(
            {
                "type": "claim_without_proof",
                "severity": "red",
                "label": "High Risk",
                "claimed_skills": claimed,
                "career_evidence": career_preview,
                "rule": (
                    "AI/retrieval skills are claimed, but career history does not show "
                    "matching production retrieval, ranking, recommendation, or vector-search work."
                ),
                "detail": (
                    f"{candidate.anonymized_name} claims {', '.join(claimed[:6])}, "
                    f"but career history reads as {career_preview}."
                ),
            }
        )
    for signal in audit_result.get("negative_signals", []):
        if "claimed" in signal.lower() and not flags:
            flags.append(
                {
                    "type": "audit_negative_signal",
                    "severity": "amber",
                    "label": "Review",
                    "claimed_skills": claimed,
                    "career_evidence": career_preview,
                    "rule": signal,
                    "detail": signal,
                }
            )
    return flags


def build_risks(
    candidate: Any,
    role_result: dict[str, Any],
    skill_result: dict[str, Any],
    recruitability_result: dict[str, Any],
    flags: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build recruiter-readable risk traffic lights."""
    risks: list[dict[str, str]] = []
    if role_result["final_score"] < 15:
        risks.append({
            "type": "fit",
            "severity": "red",
            "detail": "Role alignment is below 15; recruitability is not allowed to rescue this profile.",
        })
    if skill_result.get("contradiction_penalty", 0) > 0:
        risks.append({
            "type": "proof",
            "severity": "red",
            "detail": f"Skill stuffing contradiction penalty applied: -{skill_result['contradiction_penalty']:.0f}.",
        })
    if flags:
        risks.append({
            "type": "honeypot",
            "severity": flags[0]["severity"],
            "detail": flags[0]["detail"],
        })
    notice = candidate.recruiter_signals.notice_period_days
    if notice is not None and notice > 60:
        risks.append({
            "type": "notice",
            "severity": "amber",
            "detail": f"{notice}-day notice period; role likely prefers faster availability.",
        })
    response = candidate.recruiter_signals.recruiter_response_rate
    if response is not None and response < 0.35:
        risks.append({
            "type": "response",
            "severity": "red",
            "detail": f"{response * 100:.0f}% recruiter response rate is low.",
        })
    if recruitability_result["activity_score"] < 35:
        risks.append({
            "type": "activity",
            "severity": "amber",
            "detail": "Platform activity is stale or weak.",
        })
    return risks or [{"type": "overall", "severity": "green", "detail": "No major risk flags detected."}]


def build_score_reasons(
    role_result: dict[str, Any],
    skill_result: dict[str, Any],
    recruitability_result: dict[str, Any],
    market_result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return one-sentence explanations and reason bullets per score component."""
    return {
        "role": {
            "score": role_result["final_score"],
            "summary": "Role alignment is driven by evidence, gated semantic similarity, career relevance, and experience fit.",
            "reasons": [
                f"Evidence score {role_result['evidence_score']:.1f} from career/project text.",
                f"Semantic score gated from {role_result['raw_semantic_score']:.1f} to {role_result['effective_semantic_score']:.1f}.",
                f"Domain relevance {role_result['domain_relevance']:.2f}; career relevance {role_result['career_relevance_score']:.1f}.",
            ],
        },
        "proof": {
            "score": skill_result["skill_proof_score"],
            "summary": "Skill proof checks whether claimed JD skills are backed by career, projects, assessments, and GitHub.",
            "reasons": [
                f"Career evidence {skill_result['career_evidence_score']:.1f}; assessment evidence {skill_result['assessment_evidence_score']:.1f}.",
                f"GitHub evidence {skill_result['github_evidence_score']:.1f} after domain gating.",
                f"Claim consistency multiplier {skill_result['claim_consistency_score']:.2f}; contradiction penalty -{skill_result.get('contradiction_penalty', 0):.0f}.",
            ],
        },
        "recruitability": {
            "score": recruitability_result["hireability_score"],
            "summary": "Hireability captures activity, responsiveness, availability, logistics, and market interest.",
            "reasons": [
                f"Activity {recruitability_result['activity_score']:.1f}; responsiveness {recruitability_result['responsiveness_score']:.1f}.",
                f"Availability {recruitability_result['availability_score']:.1f}; logistics {recruitability_result['logistics_score']:.1f}.",
                f"Availability multiplier {recruitability_result['availability_multiplier']:.2f}.",
            ],
        },
        "market": {
            "score": market_result["market_validation_score"],
            "summary": "Market validation is capped so recruiter popularity cannot outweigh technical fit.",
            "reasons": [
                f"Recruiter interest {market_result['recruiter_interest_score']:.1f}.",
                f"Discoverability {market_result['discoverability_score']:.1f}; demand {market_result['demand_score']:.1f}.",
            ],
        },
    }


def claimed_ai_skills(candidate: Any) -> list[str]:
    """Return claimed AI/retrieval skills with safe word-aware matching."""
    skills = [skill.name for skill in candidate.skills]
    claimed: list[str] = []
    for skill in skills:
        normalized = skill.lower()
        if any(term_matches(normalized, term) for term in AI_CLAIM_TERMS):
            claimed.append(skill)
    return claimed


def career_evidence_text(candidate: Any) -> str:
    """Return normalized career-history text."""
    return " ".join(
        f"{item.title} {item.industry} {item.description}".lower()
        for item in candidate.career_history
    )


def career_chain(candidate: Any) -> str:
    """Return a compact career trajectory for contradiction panels."""
    return " -> ".join(
        f"{item.title} at {item.company}"
        for item in candidate.career_history[:5]
    )


def term_matches(text: str, term: str) -> bool:
    """Word-aware term matching; RAG must be a standalone token."""
    if term == "rag":
        return re.search(r"\brag\b", text, re.IGNORECASE) is not None
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
