"use client";

import { useEffect, useMemo, useState } from "react";
import { getAudit, getRankings, screen, type Ranking } from "@/lib/api";
import { Card } from "@/components/ui/card";

export default function AuditPage() {
  const [rankings, setRankings] = useState<Ranking[]>([]);
  const [selected, setSelected] = useState("");
  const [audit, setAudit] = useState<any>(null);
  const [metadata, setMetadata] = useState<any>(null);

  useEffect(() => {
    getRankings().then((res) => {
      setRankings(res.rankings);
      setMetadata(res.metadata);
      setSelected(res.rankings[0]?.candidate_id ?? "");
    }).catch(console.error);
  }, []);

  useEffect(() => {
    if (selected) getAudit(selected).then(setAudit).catch(console.error);
  }, [selected]);

  const ranking = useMemo(() => rankings.find((item) => item.candidate_id === selected), [rankings, selected]);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold">Evidence Audit</h1>

      {metadata?.audit_report?.anomalies?.length > 0 && (
        <div className="rounded-card border border-red-900/30 bg-red-500/5 p-5 space-y-3">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-red-400 flex items-center gap-1.5 font-bold">
            ⚠️ Post-Ranking Sanity Check Audit Warnings ({metadata.audit_report.total_anomalies})
          </h3>
          <ul className="list-disc list-inside space-y-1.5 text-sm text-slate-300 opacity-90">
            {metadata.audit_report.anomalies.map((anomaly: any, i: number) => (
              <li key={i}>
                <span className="font-semibold text-slate-200">[{anomaly.type}]</span> {anomaly.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <select className="rounded-card border border-prism-line bg-prism-panel px-3 py-2" value={selected} onChange={(e) => setSelected(e.target.value)}>
        {rankings.map((r) => <option key={r.candidate_id} value={r.candidate_id}>{r.rank}. {r.candidate_name}</option>)}
      </select>
      {audit && ranking && (
        <div className="space-y-4">
          <Card>
            <h2 className="text-xl font-semibold">{audit.candidate_name}</h2>
            <p className="text-sm text-slate-400">{audit.current_title} · {audit.classification}</p>
            <p className="mt-3 text-slate-300">{audit.evidence_summary}</p>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <Metric label="Must-Haves" value={audit.matched_must_haves.length} />
              <Metric label="Good-To-Haves" value={audit.matched_good_to_haves.length} />
              <Metric label="Negative Signals" value={audit.negative_signals.length} />
            </div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-3">
            <ReasonCard title="Matched Must-Haves" items={audit.matched_must_haves} empty="No must-have evidence found." />
            <ReasonCard title="Matched Good-To-Haves" items={audit.matched_good_to_haves} empty="No good-to-have evidence found." />
            <ReasonCard title="Negative Signals" items={audit.negative_signals} empty="No negative signals found." />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <ReasonCard title="Career Evidence" items={audit.career_evidence} empty="No JD-domain career evidence found." />
            <ReasonCard title="Skill / Assessment Evidence" items={[...audit.skill_evidence, ...audit.assessment_evidence]} empty="No relevant skill or assessment evidence found." />
          </div>
          <Card>
            <details>
              <summary className="cursor-pointer text-sm font-medium">Raw structured audit payload</summary>
              <pre className="mt-4 overflow-auto rounded-card bg-slate-950 p-4 text-xs">{JSON.stringify(audit, null, 2)}</pre>
            </details>
          </Card>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div className="rounded-card border border-prism-line p-4"><div className="text-2xl font-semibold">{value}</div><div className="text-sm text-slate-400">{label}</div></div>;
}

function ReasonCard({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <Card>
      <h3 className="font-semibold">{title}</h3>
      {items.length ? (
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-slate-500">{empty}</p>
      )}
    </Card>
  );
}
