"use client";

import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from "recharts";
import type { Ranking } from "@/lib/api";

export function ScoreRadar({ ranking }: { ranking: Ranking }) {
  const data = [
    { metric: "Role", score: ranking.role_alignment_score },
    { metric: "Proof", score: ranking.skill_proof_score },
    { metric: "Hire", score: ranking.hireability_score },
    { metric: "Market", score: ranking.market_validation_score }
  ];

  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data}>
          <PolarGrid stroke="#334155" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: "#cbd5e1", fontSize: 12 }} />
          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 10 }} />
          <Radar dataKey="score" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.35} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
