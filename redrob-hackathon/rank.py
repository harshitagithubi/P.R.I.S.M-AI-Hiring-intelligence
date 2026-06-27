#!/usr/bin/env python3
"""Runner script for PRISM AI V3 candidate ranking pipeline.

Loads the JD profile, parses candidate profiles in parallel using multiprocessing,
ranks them, validates that scores are monotonically non-increasing and properly tiebroken,
and outputs the top 100 candidates in CSV format.
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing
import sys
import time
from pathlib import Path

# Ensure project root is in the path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.candidate.candidate_parser import CandidateParser
    from src.candidate.candidate_schema import CandidateProfile
    from src.jd.jd_parser import JDParser
    from src.scoring.prism_ranker import PRISMRankingEngine, PRISMRankingResult
except ImportError:
    from candidate.candidate_parser import CandidateParser
    from candidate.candidate_schema import CandidateProfile
    from jd.jd_parser import JDParser
    from scoring.prism_ranker import PRISMRankingEngine, PRISMRankingResult


# Worker global state
_worker_jd = None
_worker_parser = None
_worker_ranker = None


def init_worker(jd_profile_dict: dict) -> None:
    """Initialize worker state once per process."""
    global _worker_jd, _worker_parser, _worker_ranker
    from src.candidate.candidate_parser import CandidateParser
    from src.jd.jd_schema import JDProfile
    from src.scoring.prism_ranker import PRISMRankingEngine

    _worker_jd = JDProfile(**jd_profile_dict)
    _worker_parser = CandidateParser()
    _worker_ranker = PRISMRankingEngine()


def score_candidate_line(line_str: str) -> dict | None:
    """Parse and score a candidate JSON string inside a worker process."""
    global _worker_jd, _worker_parser, _worker_ranker
    if not line_str or not line_str.strip():
        return None
    try:
        raw = json.loads(line_str)
        candidate = _worker_parser.parse_candidate(raw)
        result = _worker_ranker._score_candidate(_worker_jd, candidate)
        return result.to_dict()
    except Exception:
        return None


def validate_results_monotonicity(results: list[PRISMRankingResult]) -> None:
    """Ensure that scored ranks are strictly non-increasing by effective score.

    Raises an AssertionError if a lower rank has a lower effective score than a higher rank,
    or if tiebreakers (candidate_id ascending) are violated.
    """
    def get_effective_score(res):
        eff = res.final_score
        if res.qualification_tier == "Honeypot":
            eff -= 100.0
        return eff

    for i in range(len(results) - 1):
        r1 = results[i]
        r2 = results[i + 1]

        eff1 = get_effective_score(r1)
        eff2 = get_effective_score(r2)

        # Score must be non-increasing by rank
        if eff1 < eff2:
            raise AssertionError(
                f"Rank score inversion detected: Rank {i+1} (ID: {r1.candidate_id}, Effective Score: {eff1:.2f}) "
                f"< Rank {i+2} (ID: {r2.candidate_id}, Effective Score: {eff2:.2f})."
            )

        # Equal scores must break ties by candidate_id ascending
        if eff1 == eff2 and r1.candidate_id > r2.candidate_id:
            raise AssertionError(
                f"Tie-break ordering violation detected at effective score {eff1:.2f}: "
                f"Rank {i+1} (ID: {r1.candidate_id}) should come after Rank {i+2} (ID: {r2.candidate_id}) "
                f"according to candidate_id ascending rule."
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="PRISM AI V3 Candidate Ranking Engine")
    parser.add_argument(
        "--candidates",
        type=str,
        required=True,
        help="Path to candidates.json or candidates.jsonl file",
    )
    parser.add_argument(
        "--jd",
        type=str,
        default=str(
            Path(__file__).resolve().parent / "data" / "uploads" / "job_description.docx"
        ),
        help="Path to the Job Description docx or txt file",
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Path to save the output CSV",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of candidates to output (default: 100)",
    )

    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    jd_path = Path(args.jd)
    out_path = Path(args.out)

    print(f"[*] Loading JD from: {jd_path}")
    jd_profile = JDParser(jd_path).parse()
    jd_dict = jd_profile.to_dict()

    print(f"[*] Loading candidate records from: {candidates_path}")
    start_load = time.time()
    lines = []
    if candidates_path.suffix.lower() == ".jsonl":
        with open(candidates_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    lines.append(line)
    else:
        with open(candidates_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            lines = [json.dumps(data)]
        elif isinstance(data, list):
            lines = [json.dumps(cand) for cand in data]
        else:
            raise ValueError("Invalid candidate JSON format.")
    end_load = time.time()
    print(f"[+] Loaded {len(lines)} records in {end_load - start_load:.2f} seconds.")

    # Pre-encode all candidate and JD texts in main process
    print("[*] Pre-encoding all candidate and JD texts in main process...")
    texts_to_encode = []
    
    # JD texts
    jd_text = f"{jd_profile.title}. {' '.join(jd_profile.must_have)}. {' '.join(jd_profile.good_to_have)}"
    texts_to_encode.append(jd_text)
    texts_to_encode.append(f"{jd_profile.title} {' '.join(jd_profile.must_have)} {' '.join(jd_profile.good_to_have)}")

    # Capabilities
    from src.scoring.role_alignment import CAPABILITY_DESCRIPTIONS
    for cap_desc in CAPABILITY_DESCRIPTIONS.values():
        texts_to_encode.append(cap_desc)

    parser_obj = CandidateParser()
    for line in lines:
        try:
            raw = json.loads(line)
            candidate = parser_obj.parse_candidate(raw)
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
        except Exception:
            pass

    from src.utils.embedding_manager import EmbeddingManager
    emb_mgr = EmbeddingManager()
    emb_mgr.batch_encode(texts_to_encode)
    print(f"[+] Successfully pre-encoded and cached {len(texts_to_encode)} texts.")

    # Multiprocessing pool execution
    num_workers = max(1, multiprocessing.cpu_count())
    print(f"[*] Scoring all candidates using {num_workers} processes...")
    start_score = time.time()
    
    results = []
    with multiprocessing.Pool(processes=num_workers, initializer=init_worker, initargs=(jd_dict,)) as pool:
        chunksize = max(1, len(lines) // (num_workers * 10))
        chunksize = min(500, chunksize)
        for res_dict in pool.imap_unordered(score_candidate_line, lines, chunksize=chunksize):
            if res_dict is not None:
                results.append(PRISMRankingResult(**res_dict))
                
    end_score = time.time()
    print(f"[+] Scored {len(results)} candidates in {end_score - start_score:.2f} seconds.")

    print("[*] Sorting candidates...")
    # Sort strictly by effective_score DESC, with candidate_id ASC as a tiebreaker
    def get_sort_key(res):
        effective_score = res.final_score
        if res.qualification_tier == "Honeypot":
            effective_score -= 100.0
        return (-effective_score, res.candidate_id)

    sorted_results = sorted(
        results,
        key=get_sort_key,
    )

    ranked_results = [
        PRISMRankingResult(
            candidate_id=res.candidate_id,
            candidate_name=res.candidate_name,
            role_alignment_score=res.role_alignment_score,
            skill_proof_score=res.skill_proof_score,
            recruitability_score=res.recruitability_score,
            final_score=res.final_score,
            hireability_score=res.hireability_score,
            market_validation_score=res.market_validation_score,
            score_breakdown=res.score_breakdown,
            technical_strength=res.technical_strength,
            qualification_tier=res.qualification_tier,
            availability_multiplier=res.availability_multiplier,
            effective_availability_multiplier=res.effective_availability_multiplier,
            rank=index,
            ranking_explanation=res.ranking_explanation,
            raw_semantic_score=res.raw_semantic_score,
            career_evidence_score=res.career_evidence_score,
            domain_gate_penalty=res.domain_gate_penalty,
            domain_gate_applied=res.domain_gate_applied,
            self_claim_score=res.self_claim_score,
            contradiction_severity=res.contradiction_severity,
            contradiction_penalty=res.contradiction_penalty,
            domain_relevance=res.domain_relevance,
            fraud_penalty=res.fraud_penalty,
            degraded_confidence=res.degraded_confidence,
            capability_score=res.capability_score,
            confidence_score=res.confidence_score,
            ownership_score=res.ownership_score,
            capability_scores=res.capability_scores,
            capability_breakdowns=res.capability_breakdowns,
            role_alignment_contribution=res.role_alignment_contribution,
            supporting_contribution=res.supporting_contribution,
        )
        for index, res in enumerate(sorted_results[:args.limit], start=1)
    ]

    # Validate sort order and tiebreakers
    print("[*] Verifying output compliance (monotonicity & tiebreaker rules)...")
    validate_results_monotonicity(ranked_results)
    print("[+] Results validated successfully.")

    # Write output to CSV
    print(f"[*] Exporting results to: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for res in ranked_results:
            writer.writerow([
                res.candidate_id,
                res.rank,
                f"{res.final_score:.2f}",
                res.ranking_explanation,
            ])

    print(f"[+] Successfully exported {len(ranked_results)} rows to {out_path}.")

    try:
        from src.scoring.sanity_checks import run_post_ranking_audit
    except ImportError:
        from scoring.sanity_checks import run_post_ranking_audit
    
    audit_report = run_post_ranking_audit(ranked_results)
    print(f"[+] Post-ranking audit completed. Anomalies detected: {audit_report['total_anomalies']}")


if __name__ == "__main__":
    main()
