"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Ranking } from "@/lib/api";

export function TopCandidatesChart({ rankings }: { rankings: Ranking[] }) {
  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rankings.slice(0, 20)}>
          <CartesianGrid stroke="#1f2937" />
          <XAxis dataKey="candidate_name" stroke="#94a3b8" hide />
          <YAxis stroke="#94a3b8" />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #243044" }} />
          <Bar dataKey="final_score" fill="#38bdf8" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
