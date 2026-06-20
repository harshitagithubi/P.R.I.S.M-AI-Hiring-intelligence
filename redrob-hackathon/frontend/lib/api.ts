export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type Ranking = {
  rank: number;
  candidate_id: string;
  candidate_name: string;
  title: string;
  current_company: string;
  role_alignment_score: number;
  skill_proof_score: number;
  recruitability_score: number;
  clearance_score?: number;
  hireability_score: number;
  market_validation_score: number;
  technical_strength: number;
  qualification_tier: string;
  final_score: number;
  ranking_explanation: string;
  flags: Flag[];
  risks: Risk[];
  score_reasons: ScoreReasons;
  current_industry: string;
  location: string;
  skills: string[];
  open_to_work: boolean;
  notice_period_days: number | null;
  years_of_experience: number;
  raw_semantic_score: number;
  career_evidence_score: number;
  domain_gate_penalty: number;
  domain_gate_applied: boolean;
  self_claim_score: number;
  contradiction_severity: number;
  contradiction_penalty: number;
  domain_relevance: number;
  fraud_penalty: number;
  degraded_confidence: boolean;
};

export type Flag = {
  type: string;
  severity: "red" | "amber" | "green" | "black";
  label: string;
  claimed_skills: string[];
  career_evidence: string;
  rule: string;
  detail: string;
};

export type Risk = {
  type: string;
  severity: "red" | "amber" | "green" | "black";
  detail: string;
};

export type ScoreReason = {
  score: number;
  summary: string;
  reasons: string[];
};

export type ScoreReasons = {
  role: ScoreReason;
  proof: ScoreReason;
  recruitability: ScoreReason;
  market: ScoreReason;
};

export type RankingsResponse = {
  rankings: Ranking[];
  metadata: {
    model_status: {
      loaded: boolean;
      status_message: string;
      running_degraded: boolean;
    };
    audit_report: {
      total_anomalies: number;
      anomalies: {
        type: string;
        severity: string;
        message: string;
      }[];
    };
  };
};

export async function screen() {
  const response = await fetch(`${API_BASE}/screen`, { method: "POST" });
  if (!response.ok) throw new Error("Screening failed");
  return response.json();
}

export async function uploadJD(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/upload-jd`, { method: "POST", body: formData });
  if (!response.ok) throw new Error("JD upload failed");
  return response.json();
}

export async function uploadCandidates(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/upload-candidates`, { method: "POST", body: formData });
  if (!response.ok) throw new Error("Candidate upload failed");
  return response.json();
}

export async function getRankings(): Promise<RankingsResponse> {
  const response = await fetch(`${API_BASE}/rankings`, { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load rankings");
  return response.json();
}

export async function getCandidate(id: string) {
  const response = await fetch(`${API_BASE}/candidate/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load candidate");
  return response.json();
}

export async function getExplanation(id: string) {
  const response = await fetch(`${API_BASE}/candidate/${id}/explanation`, { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load explanation");
  return response.json();
}

export async function getAudit(id: string) {
  const response = await fetch(`${API_BASE}/audit/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load audit");
  return response.json();
}
