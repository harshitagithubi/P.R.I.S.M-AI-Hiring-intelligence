"use client";

import { useEffect, useMemo, useState } from "react";
import { getExplanation, getRankings, screen, type Ranking } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { ScoreRadar } from "@/components/score-radar";

export default function ComparePage() {
  const [rankings, setRankings] = useState<Ranking[]>([]);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [explanations, setExplanations] = useState<Record<string, any>>({});

  useEffect(() => {
    screen().then(() => getRankings()).then((res) => {
      setRankings(res.rankings);
      setLeft(res.rankings[0]?.candidate_id ?? "");
      setRight(res.rankings[1]?.candidate_id ?? "");
    }).catch(console.error);
  }, []);

  useEffect(() => {
    [left, right].filter(Boolean).forEach((id) => getExplanation(id).then((e) => setExplanations((prev) => ({ ...prev, [id]: e }))));
  }, [left, right]);

  const leftRanking = useMemo(() => rankings.find((r) => r.candidate_id === left), [rankings, left]);
  const rightRanking = useMemo(() => rankings.find((r) => r.candidate_id === right), [rankings, right]);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Candidate Comparison</h1>
      <div className="grid gap-3 md:grid-cols-2">
        <Select rankings={rankings} value={left} onChange={setLeft} />
        <Select rankings={rankings} value={right} onChange={setRight} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {leftRanking && <CompareCard ranking={leftRanking} explanation={explanations[left]} />}
        {rightRanking && <CompareCard ranking={rightRanking} explanation={explanations[right]} />}
      </div>
    </div>
  );
}

function Select({ rankings, value, onChange }: { rankings: Ranking[]; value: string; onChange: (v: string) => void }) {
  return <select className="rounded-card border border-prism-line bg-prism-panel px-3 py-2" value={value} onChange={(e) => onChange(e.target.value)}>{rankings.map((r) => <option key={r.candidate_id} value={r.candidate_id}>{r.candidate_name}</option>)}</select>;
}

function CompareCard({ ranking, explanation }: { ranking: Ranking; explanation?: any }) {
  return (
    <Card>
      <h2 className="text-xl font-semibold">{ranking.candidate_name}</h2>
      <p className="text-sm text-slate-400">{ranking.qualification_tier}</p>
      <ScoreRadar ranking={ranking} />
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>Final: {ranking.final_score.toFixed(1)}</div>
        <div>Role: {ranking.role_alignment_score.toFixed(1)}</div>
        <div>Proof: {ranking.skill_proof_score.toFixed(1)}</div>
        <div>Recruit: {ranking.recruitability_score.toFixed(1)}</div>
      </div>
      <h3 className="mt-4 font-medium">Recommendation</h3>
      <p className="mt-2 text-sm text-slate-300">{explanation?.decision_reason ?? "Loading explanation..."}</p>
    </Card>
  );
}
