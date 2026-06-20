"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Job = {
  company: string;
  title: string;
  duration_months: number;
  industry: string;
};

function colorForIndustry(industry: string, title: string) {
  const text = `${industry} ${title}`.toLowerCase();
  if (text.includes("ai") || text.includes("machine learning") || text.includes("data") || text.includes("internet") || text.includes("software")) return "#22c55e";
  if (text.includes("it services") || text.includes("saas") || text.includes("fintech") || text.includes("e-commerce")) return "#facc15";
  return "#f87171";
}

export function CareerTimeline({ jobs }: { jobs: Job[] }) {
  const data = jobs.map((job) => ({
    ...job,
    label: `${job.title} · ${job.company}`,
    fill: colorForIndustry(job.industry, job.title)
  }));

  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 32, right: 16 }}>
          <XAxis type="number" stroke="#94a3b8" />
          <YAxis type="category" dataKey="label" stroke="#cbd5e1" width={180} tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #243044" }} />
          <Bar dataKey="duration_months" radius={[0, 4, 4, 0]}>
            {data.map((entry) => <Cell key={entry.label} fill={entry.fill} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
