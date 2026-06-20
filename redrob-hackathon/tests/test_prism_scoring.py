from __future__ import annotations

import datetime
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.candidate.candidate_schema import CandidateProfile, CandidateExperience, CandidateSkill, RecruiterSignals, SalaryRange, GithubSignals
from src.jd.jd_schema import JDProfile
from src.scoring.prism_ranker import PRISMRankingEngine
from src.scoring.recruitability import RecruitabilityEngine

def create_mock_candidate(
    candidate_id="CAND_MOCK",
    anonymized_name="Mock Candidate",
    title="ML Engineer",
    years_of_experience=5.0,
    skills=None,
    career_history=None,
    last_active_date=None,
    open_to_work_flag=True,
    notice_period_days=30,
    recruiter_response_rate=0.8,
    interview_completion_rate=0.9,
    company="Mock Inc"
) -> CandidateProfile:
    if skills is None:
        skills = [CandidateSkill(name="Python", proficiency="advanced", endorsements=10, duration_months=36)]
    if career_history is None:
        career_history = [
            CandidateExperience(
                company=company,
                title="ML Engineer",
                start_date="2023-01-01",
                end_date=None,
                duration_months=36,
                is_current=True,
                industry="Tech",
                company_size="100-500",
                description="Built recommendation engines and ranking systems using Python."
            )
        ]
    if last_active_date is None:
        last_active_date = datetime.date.today().strftime("%Y-%m-%d")

    return CandidateProfile(
        candidate_id=candidate_id,
        anonymized_name=anonymized_name,
        headline="Mock Headline",
        summary="Mock Summary with RAG and vector database",
        location="Pune",
        country="India",
        title=title,
        current_company=company,
        current_company_size="100-500",
        current_industry="Tech",
        years_of_experience=years_of_experience,
        skills=skills,
        education=[],
        certifications=[],
        languages=[],
        recruiter_signals=RecruiterSignals(
            profile_completeness_score=90.0,
            signup_date="2022-01-01",
            last_active_date=last_active_date,
            open_to_work_flag=open_to_work_flag,
            profile_views_received_30d=5,
            applications_submitted_30d=1,
            recruiter_response_rate=recruiter_response_rate,
            avg_response_time_hours=24.0,
            connection_count=100,
            endorsements_received=10,
            notice_period_days=notice_period_days,
            expected_salary_range_inr_lpa=SalaryRange(min=10, max=20),
            preferred_work_mode="hybrid",
            willing_to_relocate=True,
            search_appearance_30d=50,
            saved_by_recruiters_30d=2,
            interview_completion_rate=interview_completion_rate,
            offer_acceptance_rate=0.8,
            verified_email=True,
            verified_phone=True,
            linkedin_connected=True,
            skill_assessment_scores={}
        ),
        github_signals=GithubSignals(
            github_activity_score=40.0,
            has_github_activity=True
        ),
        career_history=career_history
    )

def test_ghost_candidate_detection():
    print("Testing Ghost Candidate Detection...")
    # Inactive for 3 years (1095 days)
    ghost_date = (datetime.date.today() - datetime.timedelta(days=1095)).strftime("%Y-%m-%d")
    candidate_ghost = create_mock_candidate(last_active_date=ghost_date)
    candidate_active = create_mock_candidate()
    
    jd = JDProfile(
        title="Senior AI Engineer",
        must_have=["Python", "retrieval", "vector database"],
        good_to_have=[],
        negative_signals=[],
        experience_min=2,
        experience_max=10,
        preferred_locations=["Pune"]
    )
    
    ranker = PRISMRankingEngine()
    result_ghost = ranker._score_candidate(jd, candidate_ghost)
    result_active = ranker._score_candidate(jd, candidate_active)
    
    # Verify that ghost is penalized compared to active
    assert result_ghost.final_score < result_active.final_score, f"Expected penalized score, got {result_ghost.final_score} vs {result_active.final_score}"
    assert result_ghost.final_score > 5.0, f"Expected candidate to not be completely destroyed, got {result_ghost.final_score}"
    print("Ghost Candidate Detection Passed!")

def test_multiple_current_jobs():
    print("Testing Multiple Current Jobs Penalty...")
    career_history_multiple = [
        CandidateExperience(
            company="Company A", title="ML Engineer", start_date="2023-01-01", end_date=None,
            duration_months=12, is_current=True, industry="Tech", company_size="Large", description="ML Work"
        ),
        CandidateExperience(
            company="Company B", title="Consultant", start_date="2023-01-01", end_date=None,
            duration_months=12, is_current=True, industry="Tech", company_size="Large", description="Consultant Work"
        )
    ]
    candidate_multiple = create_mock_candidate(career_history=career_history_multiple)
    candidate_single = create_mock_candidate()
    
    jd = JDProfile(
        title="Senior AI Engineer", must_have=["Python"], good_to_have=[], negative_signals=[],
        experience_min=2, experience_max=10, preferred_locations=["Pune"]
    )
    ranker = PRISMRankingEngine()
    result_multiple = ranker._score_candidate(jd, candidate_multiple)
    result_single = ranker._score_candidate(jd, candidate_single)
    
    # Multiple current jobs should result in lower score
    assert result_multiple.final_score < result_single.final_score
    print("Multiple Current Jobs Penalty Passed!")

def test_fake_experience():
    print("Testing Fake Experience Detection...")
    # Claims 15 years, but career history total is 2 years
    career_history_short = [
        CandidateExperience(
            company="Company A", title="Developer", start_date="2022-01-01", end_date=None,
            duration_months=24, is_current=True, industry="Tech", company_size="Large", description="Dev Work"
        )
    ]
    candidate_fake = create_mock_candidate(years_of_experience=15.0, career_history=career_history_short)
    candidate_true = create_mock_candidate(years_of_experience=2.0, career_history=career_history_short)
    
    jd = JDProfile(
        title="Senior AI Engineer", must_have=["Python"], good_to_have=[], negative_signals=[],
        experience_min=2, experience_max=10, preferred_locations=["Pune"]
    )
    ranker = PRISMRankingEngine()
    result_fake = ranker._score_candidate(jd, candidate_fake)
    result_true = ranker._score_candidate(jd, candidate_true)
    
    # Fake experience claims should lead to score reduction
    assert result_fake.final_score < result_true.final_score
    print("Fake Experience Detection Passed!")

def test_wrong_domain_professional():
    print("Testing Wrong Domain Professional Contradiction Penalty...")
    # Marketing manager claiming 6 AI skills without career evidence
    skills = [
        CandidateSkill(name="FAISS", proficiency="advanced", endorsements=10),
        CandidateSkill(name="RAG", proficiency="advanced", endorsements=10),
        CandidateSkill(name="Qdrant", proficiency="advanced", endorsements=10),
        CandidateSkill(name="Vector Search", proficiency="advanced", endorsements=10),
        CandidateSkill(name="Pinecone", proficiency="advanced", endorsements=10),
        CandidateSkill(name="LangChain", proficiency="advanced", endorsements=10),
    ]
    career_history_non_tech = [
        CandidateExperience(
            company="Marketing Agency", title="Marketing Manager", start_date="2020-01-01", end_date=None,
            duration_months=72, is_current=True, industry="Marketing", company_size="Small", description="Managed campaigns."
        )
    ]
    candidate = create_mock_candidate(title="Marketing Manager", skills=skills, career_history=career_history_non_tech)
    jd = JDProfile(
        title="Senior AI Engineer", must_have=["Python"], good_to_have=[], negative_signals=[],
        experience_min=2, experience_max=10, preferred_locations=["Pune"]
    )
    ranker = PRISMRankingEngine()
    result = ranker._score_candidate(jd, candidate)
    
    # Since they lack technical career evidence, they should be classified as Honeypot
    assert result.qualification_tier == "Honeypot", f"Expected Honeypot, got {result.qualification_tier}"
    print("Wrong Domain Professional Contradiction Penalty Passed!")

def test_product_company_bonus():
    print("Testing Product Company Bonus...")
    jd = JDProfile(
        title="Senior AI Engineer", must_have=["Python"], good_to_have=[], negative_signals=[],
        experience_min=2, experience_max=10, preferred_locations=["Pune"]
    )
    ranker = PRISMRankingEngine()
    
    # Flipkart experience
    candidate_flipkart = create_mock_candidate(company="Flipkart")
    score_with_bonus = ranker._score_candidate(jd, candidate_flipkart).final_score
    
    # Non-product company
    candidate_other = create_mock_candidate(company="Mock Inc")
    score_without_bonus = ranker._score_candidate(jd, candidate_other).final_score
    
    assert score_with_bonus > score_without_bonus or score_with_bonus == 100.0, f"Expected {score_with_bonus} > {score_without_bonus}"
    print("Product Company Bonus Passed!")

def run_all_tests():
    try:
        test_ghost_candidate_detection()
        test_multiple_current_jobs()
        test_fake_experience()
        test_wrong_domain_professional()
        test_product_company_bonus()
        print("ALL TESTS PASSED SUCCESSFULLY!")
    except AssertionError as e:
        print("TEST FAILURE:", e)
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
