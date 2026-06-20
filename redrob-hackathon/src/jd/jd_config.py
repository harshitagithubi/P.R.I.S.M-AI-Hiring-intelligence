"""Role-specific configuration for parsing the Redrob AI hackathon JD."""

from __future__ import annotations


MUST_HAVE_KEYWORDS: list[str] = [
    "Senior AI Engineer judgment with hands-on production ownership",
    "Production experience with embeddings-based retrieval systems",
    "Operational experience with vector databases or hybrid search infrastructure",
    "Strong Python and production code quality",
    "Hands-on evaluation frameworks for ranking systems",
    "Experience shipping ranking, search, recommendation, retrieval, or matching systems",
    "Ability to own candidate-JD matching intelligence at scale",
    "Scrappy product-engineering mindset with willingness to ship quickly",
    "Applied ML/AI experience in product-company environments",
    "Recent hands-on production coding experience",
]

GOOD_TO_HAVE_KEYWORDS: list[str] = [
    "LLM fine-tuning with LoRA, QLoRA, PEFT, or similar methods",
    "Learning-to-rank models such as XGBoost-based or neural rankers",
    "HR-tech, recruiting-tech, marketplace, or talent-intelligence exposure",
    "Distributed systems or large-scale inference optimization background",
    "Open-source contributions in AI or ML",
    "Experience mentoring engineers in a growing AI engineering organization",
    "Strong written async communication",
    "Active job-market or Redrob-platform signal",
]

NEGATIVE_SIGNALS: list[str] = [
    "Pure research background without production deployment experience",
    "AI experience limited to under 12 months of LangChain or OpenAI wrapper projects",
    "Senior engineer without production coding in the last 18 months",
    "Career optimized mainly for title progression through frequent job switching",
    "Entire career only in consulting or services companies without product-company experience",
    "Primary expertise only in computer vision, speech, or robotics without NLP or IR depth",
    "Closed-source proprietary work for 5+ years without external validation",
    "Preference for stable, mature, narrowly scoped roles over ambiguous startup ownership",
    "Keyword-heavy profile without evidence of real ranking, retrieval, or recommendation systems",
    "Low recruitability signals such as stale platform activity or poor recruiter response rate",
]

DEFAULT_WEIGHTS: dict[str, float] = {
    "role_alignment": 0.35,
    "must_have": 0.25,
    "production_ml_depth": 0.15,
    "evaluation_depth": 0.10,
    "product_startup_fit": 0.07,
    "location_fit": 0.04,
    "recruitability": 0.04,
}
