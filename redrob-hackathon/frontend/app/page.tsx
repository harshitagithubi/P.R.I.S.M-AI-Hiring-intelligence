"use client";

import Link from "next/link";
import { useState } from "react";
import { Card } from "@/components/ui/card";
import { screen, uploadCandidates, uploadJD } from "@/lib/api";

export default function LandingPage() {
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [candidateFile, setCandidateFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<any>(null);
  const [status, setStatus] = useState("Ready");

  async function runScreening() {
    setStatus("Running PRISM screening...");
    if (jdFile) await uploadJD(jdFile);
    if (candidateFile) await uploadCandidates(candidateFile);
    const result = await screen();
    setSummary(result);
    setStatus("Screening complete");
  }

  const counts = {
    strong: summary?.tier_counts?.strong ?? 0,
    near: summary?.tier_counts?.near ?? 0,
    weak: summary?.tier_counts?.weak ?? 0,
    not: summary?.tier_counts?.not_qualified ?? 0,
    flagged: summary?.tier_counts?.flagged ?? 0
  };

  return (
    <div className="space-y-8">
      <section className="min-h-[78vh] content-end rounded-card border border-prism-line bg-[radial-gradient(circle_at_25%_25%,rgba(56,189,248,0.22),transparent_32%),linear-gradient(135deg,#0f172a,#070b16)] p-8">
        <div className="max-w-3xl pb-10">
          <p className="text-sm uppercase tracking-[0.3em] text-prism-cyan">Hiring intelligence</p>
          <h1 className="mt-4 text-5xl font-semibold">P.R.I.S.M AI</h1>
          <p className="mt-2 text-lg text-slate-400 font-medium tracking-wide">Profile Reliability & Intelligent Skill Mapping</p>
          <div className="mt-6 space-y-4">
            <p className="text-2xl font-medium text-slate-200 leading-relaxed">Stop hiring keywords. P.R.I.S.M AI ranks candidates using career evidence, retrieval expertise, recruitability signals, and fraud detection.</p>
            <p className="text-base text-slate-400 leading-relaxed">Built to detect real expertise, expose resume inflation, and surface candidates who can actually be hired.</p>
          </div>
          <div className="mt-8 grid gap-3 md:grid-cols-2">
            <label className="rounded-card border border-prism-line bg-slate-950/50 px-4 py-3 text-sm text-slate-300">
              Upload JD
              <input className="mt-2 block w-full text-xs" type="file" accept=".docx,.txt,.md" onChange={(event) => setJdFile(event.target.files?.[0] ?? null)} />
            </label>
            <label className="rounded-card border border-prism-line bg-slate-950/50 px-4 py-3 text-sm text-slate-300">
              Upload Candidates
              <input className="mt-2 block w-full text-xs" type="file" accept=".json" onChange={(event) => setCandidateFile(event.target.files?.[0] ?? null)} />
            </label>
          </div>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button onClick={runScreening} className="rounded-card bg-prism-cyan px-4 py-2 font-medium text-slate-950">Run Screening</button>
            <Link href="/rankings" className="rounded-card border border-prism-line px-4 py-2 text-slate-200">Open Rankings</Link>
            <Link href="/audit" className="rounded-card border border-prism-line px-4 py-2 text-slate-200">Inspect Audit</Link>
          </div>
          <p className="mt-3 text-sm text-slate-400">{status}</p>
        </div>
      </section>
      {summary && (
        <div className="grid gap-4 md:grid-cols-5">
          <Card><div className="text-2xl font-semibold">{summary.total_candidates}</div><div className="text-sm text-slate-400">Total Candidates</div></Card>
          <Card><div className="text-2xl font-semibold text-prism-green">{counts.strong}</div><div className="text-sm text-slate-400">Strong Match</div></Card>
          <Card><div className="text-2xl font-semibold text-prism-yellow">{counts.near}</div><div className="text-sm text-slate-400">Near Match</div></Card>
          <Card><div className="text-2xl font-semibold text-prism-cyan">{counts.weak}</div><div className="text-sm text-slate-400">Weak Signal</div></Card>
          <Card><div className="text-2xl font-semibold text-slate-500">{counts.not}</div><div className="text-sm text-slate-400">Not Qualified</div></Card>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-3">
        {["Evidence over claims", "Recruitability-aware", "Explainable decisions"].map((item) => (
          <Card key={item}>
            <h2 className="text-lg font-semibold">{item}</h2>
            <p className="mt-2 text-sm text-slate-400">Built for recruiter review with score breakdowns, risk panels, and evidence snippets.</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
