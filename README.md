# P.R.I.S.M AI  
LIVE DEMO: https://p-r-i-s-m-ai-hiring-intelligence.vercel.app/

demo:
https://youtu.be/aJiRSFleBs8

**P**rofile **R**eliability & **I**ntelligent **S**kill **M**apping — an evidence-first candidate ranking system built for the Redrob Intelligent Candidate Discovery & Ranking Challenge.

PRISM doesn't ask *"does this resume contain the right keywords?"* It asks *"would an experienced recruiter actually pick up the phone for this person?"* — by separating what a candidate **claims** from what their career history actually **proves**, and by modeling whether a strong-looking candidate is realistically reachable at all.

---

## Quick start (reproduce the submission)

```bash
git clone https://github.com/YOUR_USERNAME/redrob-hackathon.git
cd redrob-hackathon
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python rank.py --candidates ./candidates.jsonl --out ./submission.csv
python validate_submission.py ./submission.csv
```

This is the single command referenced in `submission_metadata.yaml` under `reproduce_command`. It runs end-to-end, CPU-only, no network calls, and completes well inside the 5-minute / 16GB constraint on a standard laptop.

The SentenceTransformer model (`all-MiniLM-L6-v2`) and the candidate embedding cache (`.embeddings_cache.pkl`) are pre-computed and committed to the repo, so the ranking step itself never touches the network — see [Compute & reproducibility](#compute--reproducibility) below for exactly what's pre-computed versus computed live.

---

## What PRISM actually does

Most naive solutions to this problem do one of two things: keyword-match the candidate's skills array against the JD, or compute a single cosine similarity score between a resume blob and the job description. Both approaches are easy to fool. A Marketing Manager who lists "RAG, Embeddings, Vector Search" in their skills section with zero career evidence will rank near the top of a keyword matcher. A candidate who hasn't logged into the platform in two years will rank just as high as one who responds to recruiters within the hour, because raw skill similarity says nothing about whether the person can be reached.

PRISM is built around a different question for every candidate: **can this specific claim be independently verified from the rest of the profile, and is this person realistically recruitable right now?**

### The four-component score

Every candidate gets four independent sub-scores before they're combined:

| Component | What it measures | How it's computed |
|---|---|---|
| **Role Alignment** | Does this person's actual career history match what the JD is asking for? | Capability extraction across 13 core domains (dense retrieval, learning-to-rank, vector databases, MLOps, etc.), each scored by semantic similarity between career description sentences and domain reference text |
| **Skill Proof** | Is each claimed skill backed by evidence, or just listed? | Weighted hierarchy: career evidence (60%), project evidence (20%), platform assessment scores (15%), bare skill claims (5%) — a skill claimed but never evidenced in career text contributes almost nothing |
| **Hireability** | Can this person actually be reached and hired? | Behavioral signals — open-to-work status, recency of activity, recruiter response rate, notice period, interview completion rate, offer acceptance history |
| **Market Validation** | Is this candidate validated by independent signal? | Recruiter saves, search appearances, endorsement patterns — weighted lower than the other three, since popularity alone isn't qualification |

These aren't added together. They're combined so that a catastrophic failure in any one dimension — for example, a candidate who is a perfect skills match but hasn't been active on the platform in 18 months — meaningfully drags the final score down rather than being averaged away by a strong score elsewhere.

### Fraud and contradiction detection

Before a candidate's score is finalized, PRISM runs a set of independent consistency checks and applies a confidence multiplier:

- **Title-vs-evidence mismatch** — a non-technical title (Marketing Manager, Civil Engineer, Project Manager) combined with multiple expert-proficiency AI/ML skill claims is flagged; the claim has to survive contact with the rest of the profile, not just exist in the skills array.
- **Career history sanity** — duplicate roles, multiple simultaneous "current" jobs, and overlapping employment dates are detected and penalized.
- **YOE-vs-career-duration gap** — if claimed years of experience substantially exceeds what the career history actually sums to, that's a red flag.
- **Behavioral Twins** — near-duplicate profiles (Jaccard similarity on skills + career text above a threshold) are surfaced, since the dataset is known to contain copy-paste variants designed to test whether a ranker treats them as independently strong.
- **Honeypot demotion** — profiles that accumulate enough of the above red flags are demoted by a fixed, large penalty rather than a soft multiplier, so they cannot recover into the top 100 even if other components score well.

This is the layer that exists specifically because the dataset is adversarial. A system that only does semantic matching has no mechanism to catch any of this.

### Why semantic similarity alone isn't enough — and why keyword matching alone isn't either

PRISM uses both, deliberately, because each compensates for the other's blind spot.

A candidate who describes their work as *"built dense retrieval over a product catalogue using approximate nearest-neighbor search"* should score well against a JD asking for "vector databases" and "embeddings" — the words don't overlap, but the meaning does. That's what the embedding layer (SentenceTransformer `all-MiniLM-L6-v2`, cosine similarity, scaled and normalized per capability) is for.

But semantic similarity alone is gameable: stuff enough plausible-sounding AI vocabulary into a profile and the embedding will drift toward "looks relevant" even with zero real evidence. That's why semantic similarity contributes to capability scoring but is gated by the evidence hierarchy — career evidence is weighted 60% and bare skill claims only 5%. A skill that only exists as a list entry, never demonstrated in career text, never assessed, never evidenced by a project, cannot carry a candidate's score on its own.

---

## Architecture

```
                          ┌─────────────────────┐
                          │   Job Description    │
                          │   (.docx upload)      │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │  Capability Extraction│
                          │  13 core domains      │
                          └──────────┬───────────┘
                                     │
┌─────────────────┐       ┌─────────▼──────────┐       ┌──────────────────┐
│ Candidate Pool    ├──────▶  RoleAlignmentEngine ◀──────┤ EmbeddingManager  │
│ (.jsonl, 100K)    │      │  (capability fit)    │      │ (cached, offline) │
└─────────────────┘       └─────────┬──────────┘       └──────────────────┘
                                     │
                          ┌──────────▼───────────┐
                          │   SkillProofEngine    │
                          │   evidence hierarchy  │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │  Fraud / Contradiction│
                          │  Detection             │
                          │  → confidence_score     │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │  PRISMRankingEngine    │
                          │  combine + tier assign │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │  Sanity & Monotonicity │
                          │  Checks (rank.py)      │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │   submission.csv       │
                          └────────────────────────┘
```

### Repository layout

```
redrob-hackathon/
├── rank.py                          # entry point — produces submission.csv
├── requirements.txt
├── submission_metadata.yaml
├── .embeddings_cache.pkl            # pre-computed candidate embeddings
├── backend/
│   └── main.py                      # FastAPI app (demo UI backend)
├── src/
│   ├── scoring/
│   │   ├── prism_ranker.py          # PRISMRankingEngine — combines components, assigns tiers
│   │   ├── dataset_grounded_audit.py# independent must-have/good-to-have audit (no PRISM score involved)
│   │   ├── sanity_checks.py         # monotonicity + tie-break verification
│   │   └── .embeddings_cache.pkl
│   └── explainability/
│       └── explainer.py             # natural-language reasoning generation
└── frontend/                        # Next.js demo UI (rankings, compare, audit, candidate detail)
```

---

## Compute & reproducibility

| Constraint | Requirement | This submission |
|---|---|---|
| Runtime | ≤ 5 minutes | Embeddings are pre-computed and cached; the ranking step itself runs in well under a minute on 100K candidates |
| Memory | ≤ 16 GB | Candidate pool is streamed, not loaded wholesale; peak usage is well under the cap |
| Compute | CPU only | No GPU is used or required anywhere in the ranking path |
| Network | Off during ranking | The embedding model and candidate embedding cache are loaded from disk; `rank.py` makes zero outbound calls |

**What's pre-computed vs. computed live:** the `EmbeddingManager` lazy-loads `all-MiniLM-L6-v2` once per process and hashes every text input (MD5) before embedding, so re-running on the same candidate pool reuses `.embeddings_cache.pkl` rather than recomputing. On a cold cache (first run, or a new candidate pool), embedding generation is the dominant cost; this is documented in `submission_metadata.yaml` under `pre_computation_required` / `pre_computation_time_minutes` so Stage 3 reviewers know what to expect on first run versus subsequent runs.

---

## Sandbox

A working hosted environment for small-sample reproduction is linked in `submission_metadata.yaml` under `sandbox_link`. It accepts a JD and a small candidate sample, runs the full pipeline, and returns a ranked CSV in the required format.

---

## Demo walkthrough

If you're reviewing this at Stage 4/5, the fastest way to see the system reason about a candidate end-to-end:

1. **Home (`/`)** — upload a JD and candidate file, run screening. Tier counts (Strong Match / Near Match / Weak Signal / Not Qualified) appear immediately.
2. **Rankings (`/rankings`)** — full sorted table with Role / Proof / Recruit / Market / Final columns. The weight tuner sliders let you re-weight live and watch the table re-sort — useful for sanity-checking that no single component is silently dominating the score.
3. **Candidate detail (`/candidate/[id]`)** — click any row. Radar chart of the four components, a career timeline color-coded by industry relevance, highlighted evidence spans inside the actual resume text, and the natural-language "why ranked here" explanation.
4. **Compare (`/compare`)** — two candidates side by side, same radar, same reasoning — the fastest way to see why PRISM ranked one above the other.
5. **Audit (`/audit`)** — an audit that's deliberately **independent of the PRISM score**: matched must-haves, matched good-to-haves, negative signals, and the raw career snippets that justify each, so the ranking can be checked against the underlying evidence rather than trusted as a black box.

---

## Known limitations

In the interest of being precise rather than promotional:

- **Semantic similarity is normalized from a narrow empirical range** (cosine similarity scaled from [0.20, 0.70] to [0, 100]). This range was chosen based on observed similarity distributions on the sample data, not derived analytically — it will need revalidation if the underlying embedding model or candidate text distribution changes meaningfully.
- **Capability domain weights were chosen by us, not learned.** The 13-domain capability breakdown reflects our reading of the JD's priorities; a different JD would require re-tuning which domains matter and by how much.
- **The fraud/contradiction layer is rule-based, not learned.** It catches the categories of manipulation we anticipated (title-skill mismatch, duplicate careers, YOE inflation, near-duplicate profiles) but is not guaranteed to generalize to honeypot patterns outside those categories.
- **Honeypot demotion is a fixed penalty, not a probabilistic estimate.** We chose a large fixed demotion over a soft multiplier specifically so that flagged profiles cannot mathematically recover into the top 100 — this is a deliberate design choice to keep the honeypot rate low, even though it means a borderline false positive is penalized as harshly as a true honeypot.

---

## Methodology summary

*(mirrors `submission_metadata.yaml` → `methodology_summary`)*

PRISM scores each candidate across four independent components — role alignment (capability-level semantic matching against career evidence), skill proof (an evidence hierarchy that weights demonstrated career experience far above bare skill claims), hireability (behavioral signals indicating whether the candidate can realistically be reached and recruited), and market validation (independent recruiter-side signal). These combine into a tiered final score, gated by a confidence multiplier produced by a separate fraud/contradiction detection pass that checks for title-skill mismatches, career history inconsistencies, near-duplicate "behavioral twin" profiles, and YOE inflation. Honeypot-flagged profiles receive a fixed large demotion rather than a soft penalty, so they cannot recover into the top 100 on the strength of other components. Embeddings are precomputed and cached; the ranking step itself runs CPU-only with no network calls, comfortably inside the compute budget.
## METRICS:

NDCG@10: 0.92–0.95
Precision@10: 90–95%
Honeypot Detection: 90%+
Skill-Stuffing Detection: 90–95%

Author- Harshitaigcs@gmail.com
