"use client";

import Link from "next/link";
import { Fragment, useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { getRankings, screen, type Ranking } from "@/lib/api";
import { decisionClass, tierClass } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { TopCandidatesChart } from "@/components/top-candidates-chart";

export default function RankingsPage() {
  const [rankings, setRankings] = useState<Ranking[]>([]);
  const [, setMetadata] = useState<any>(null);
  const [query, setQuery] = useState("");
  const [tier, setTier] = useState("All");
  const [status, setStatus] = useState("All");
  const [decisions, setDecisions] = useState<Record<string, string>>({});
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
  const [sortBy, setSortBy] = useState<"prism" | "tuned">("prism");
  const [weights, setWeights] = useState({ role: 0.55, proof: 0.25, recruit: 0.12, market: 0.08 });

  // Custom filters
  const [minYoe, setMinYoe] = useState<number | "">("");
  const [maxYoe, setMaxYoe] = useState<number | "">("");
  const [locationQuery, setLocationQuery] = useState("");
  const [noticePeriod, setNoticePeriod] = useState("All");

  useEffect(() => {
    screen().then(() => getRankings()).then((res) => {
      setRankings(res.rankings);
      setMetadata(res.metadata);
      const items = res.rankings;
      const stored: Record<string, string> = {};
      for (const item of items) {
        stored[item.candidate_id] = localStorage.getItem(`prism-decision-${item.candidate_id}`) ?? "Unreviewed";
      }
      setDecisions(stored);
    }).catch(console.error);
  }, []);

  const filtered = useMemo(() => {
    console.log("[Frontend Rankings Rendering] START");
    const t0 = performance.now();
    const parsed = parseNaturalQuery(query);
    const result = rankings
      .filter((item) => tier === "All" || item.qualification_tier === tier)
      .filter((item) => status === "All" || decisions[item.candidate_id] === status)
      .filter((item) => matchesQuery(item, parsed))
      .filter((item) => {
        // YOE Filter
        if (minYoe !== "" && item.years_of_experience < minYoe) return false;
        if (maxYoe !== "" && item.years_of_experience > maxYoe) return false;

        // Location Filter
        if (locationQuery && !item.location.toLowerCase().includes(locationQuery.toLowerCase())) return false;

        // Notice Period Filter
        if (noticePeriod !== "All") {
          const maxDays = Number(noticePeriod);
          if (item.notice_period_days === null || item.notice_period_days > maxDays) return false;
        }

        return true;
      })
      .map((item) => ({ ...item, tuned_score: tunedScore(item, weights) }))
      .sort((a, b) => {
        if (sortBy === "prism") {
          return a.rank - b.rank;
        } else {
          const tierDiff = tierValue(b.qualification_tier) - tierValue(a.qualification_tier);
          if (tierDiff !== 0) return tierDiff;
          return b.tuned_score - a.tuned_score;
        }
      });
    const t1 = performance.now();
    const elapsed = (t1 - t0) / 1000;
    console.log(`[Frontend Rankings Rendering] END. ELAPSED TIME: ${elapsed.toFixed(4)}s`);
    console.log(`Candidate count processed: ${result.length}`);
    if (elapsed > 5.0) {
      console.log("[SLOW STAGE DETECTED] Frontend Rankings Rendering exceeded 5 seconds");
    }
    return result;
  }, [rankings, query, tier, status, decisions, weights, minYoe, maxYoe, locationQuery, noticePeriod, sortBy]);

  const counts = useMemo(() => {
    return {
      strong: rankings.filter((r) => r.qualification_tier === "Strong Match").length,
      near: rankings.filter((r) => r.qualification_tier === "Near Match").length,
      weak: rankings.filter((r) => r.qualification_tier === "Weak Signal").length,
      not: rankings.filter((r) => r.qualification_tier === "Not Qualified").length,
      flagged: rankings.filter((r) => r.qualification_tier === "Honeypot" || r.qualification_tier === "Flagged").length,
    };
  }, [rankings]);

  const insights = useMemo(() => {
    console.log("[Dataset Insights Generation] START");
    const t0 = performance.now();
    let contradiction = 0;
    let ghost = 0;
    let fakeYoe = 0;
    let multipleJobs = 0;

    for (const r of rankings) {
      for (const flag of r.flags || []) {
        if (flag.type === "claim_without_proof" || flag.type === "wrong_domain_professional") {
          contradiction++;
        }
        if (flag.type === "ghost_candidate") {
          ghost++;
        }
        if (flag.type === "fake_experience") {
          fakeYoe++;
        }
        if (flag.type === "multiple_current_jobs") {
          multipleJobs++;
        }
      }
    }
    const t1 = performance.now();
    const elapsed = (t1 - t0) / 1000;
    console.log(`[Dataset Insights Generation] END. ELAPSED TIME: ${elapsed.toFixed(4)}s`);
    console.log(`Candidate count processed: fontend dataset size is ${rankings.length}`);
    if (elapsed > 5.0) {
      console.log("[SLOW STAGE DETECTED] Dataset Insights Generation exceeded 5 seconds");
    }
    return { contradiction, ghost, fakeYoe, multipleJobs };
  }, [rankings]);

  const exportToCSV = () => {
    console.log("[CSV Generation] START");
    const t0 = performance.now();
    const headers = ["Rank", "Name", "Final Score", "Tier", "Reason"];
    const rows = filtered.map(item => [
      item.rank,
      item.candidate_name,
      item.final_score.toFixed(1),
      item.qualification_tier,
      item.ranking_explanation.replace(/"/g, '""')
    ]);
    
    const csvContent = [
      headers.join(","),
      ...rows.map(e => e.map(val => `"${val}"`).join(","))
    ].join("\n");
    
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "prism_candidate_rankings.csv");
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    const t1 = performance.now();
    const elapsed = (t1 - t0) / 1000;
    console.log(`[CSV Generation] END. ELAPSED TIME: ${elapsed.toFixed(4)}s`);
    console.log(`Candidate count processed: ${filtered.length}`);
    if (elapsed > 5.0) {
      console.log("[SLOW STAGE DETECTED] CSV Generation exceeded 5 seconds");
    }
  };

  const exportToPDF = async () => {
    console.log("[PDF Generation] START");
    const t0 = performance.now();
    const { jsPDF } = await import("jspdf");
    const doc = new jsPDF();
    
    doc.setFont("Helvetica", "bold");
    doc.setFontSize(20);
    doc.text("P.R.I.S.M AI Candidate Screening Report", 14, 20);
    
    doc.setFontSize(12);
    doc.setFont("Helvetica", "normal");
    doc.text("Position: Senior AI Engineer", 14, 28);
    doc.text(`Generated on: ${new Date().toLocaleDateString()}`, 14, 34);
    
    doc.setDrawColor(200, 200, 200);
    doc.line(14, 40, 196, 40);
    
    doc.setFont("Helvetica", "bold");
    doc.setFontSize(14);
    doc.text("Top Candidates", 14, 50);
    
    doc.setFont("Helvetica", "normal");
    doc.setFontSize(10);
    let y = 58;
    
    doc.setFillColor(240, 240, 240);
    doc.rect(14, y, 182, 8, "F");
    doc.setFont("Helvetica", "bold");
    doc.text("Rank", 16, y + 6);
    doc.text("Name", 30, y + 6);
    doc.text("Score", 80, y + 6);
    doc.text("Tier", 100, y + 6);
    doc.text("Verdict", 140, y + 6);
    
    y += 8;
    doc.setFont("Helvetica", "normal");
    
    const topCandidates = filtered.slice(0, 10);
    for (const item of topCandidates) {
      if (y > 270) {
        doc.addPage();
        y = 20;
      }
      doc.text(String(item.rank), 16, y + 5);
      doc.text(item.candidate_name, 30, y + 5);
      doc.text(item.final_score.toFixed(1), 80, y + 5);
      doc.text(item.qualification_tier, 100, y + 5);
      doc.text(item.qualification_tier, 140, y + 5);
      y += 8;
    }
    
    y += 10;
    if (y > 250) {
      doc.addPage();
      y = 20;
    }
    
    doc.setFont("Helvetica", "bold");
    doc.setFontSize(14);
    doc.text("Candidate Fit Reasons", 14, y);
    y += 8;
    doc.setFont("Helvetica", "normal");
    doc.setFontSize(9);
    
    for (const item of topCandidates) {
      const text = `${item.candidate_name} (Rank ${item.rank}): ${item.ranking_explanation}`;
      const lines = doc.splitTextToSize(text, 180);
      if (y + lines.length * 5 > 280) {
        doc.addPage();
        y = 20;
      }
      doc.text(lines, 14, y);
      y += lines.length * 5 + 4;
    }
    
    y += 6;
    if (y > 250) {
      doc.addPage();
      y = 20;
    }
    
    doc.setFont("Helvetica", "bold");
    doc.setFontSize(14);
    doc.text("Risk Summary", 14, y);
    y += 8;
    doc.setFont("Helvetica", "normal");
    doc.setFontSize(9);
    
    const candidatesWithRisks = filtered.filter(item => item.risks?.length);
    if (candidatesWithRisks.length === 0) {
      doc.text("No significant risks detected across the candidates list.", 14, y);
    } else {
      for (const item of candidatesWithRisks.slice(0, 15)) {
        const riskText = item.risks?.map(r => r.detail).join("; ") || "";
        const text = `${item.candidate_name}: Verdict: [${item.qualification_tier}]. Risks: ${riskText}`;
        const lines = doc.splitTextToSize(text, 180);
        if (y + lines.length * 5 > 280) {
          doc.addPage();
          y = 20;
        }
        doc.text(lines, 14, y);
        y += lines.length * 5 + 4;
      }
    }
    
    doc.save("prism_candidate_screening_report.pdf");
    
    const t1 = performance.now();
    const elapsed = (t1 - t0) / 1000;
    console.log(`[PDF Generation] END. ELAPSED TIME: ${elapsed.toFixed(4)}s`);
    console.log(`Candidate count processed: ${filtered.length}`);
    if (elapsed > 5.0) {
      console.log("[SLOW STAGE DETECTED] PDF Generation exceeded 5 seconds");
    }
  };

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-semibold">Candidate Rankings</h1>
          <p className="text-slate-400">Evidence-first ranking for the Senior AI Engineer JD.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={exportToCSV} className="rounded-card bg-slate-800 border border-prism-line px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 transition">
            Export CSV
          </button>
          <button onClick={exportToPDF} className="rounded-card bg-prism-cyan px-4 py-2 text-sm font-medium text-slate-950 hover:opacity-90 transition">
            Export PDF Report
          </button>
        </div>
      </div>
      
      <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-4">
        <Card><div className="text-2xl font-semibold text-prism-green">{counts.strong}</div><div className="text-sm text-slate-400">Strong Match</div></Card>
        <Card><div className="text-2xl font-semibold text-prism-yellow">{counts.near}</div><div className="text-sm text-slate-400">Near Match</div></Card>
        <Card><div className="text-2xl font-semibold text-prism-cyan">{counts.weak}</div><div className="text-sm text-slate-400">Weak Signal</div></Card>
        <Card><div className="text-2xl font-semibold text-slate-400">{counts.not}</div><div className="text-sm text-slate-400">Not Qualified</div></Card>
      </div>

      {/* Dataset Insights Headline Card */}
      <Card className="p-6 border border-prism-line bg-prism-panel/40">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400">Dataset Insights</h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 md:grid-cols-5">
          <div className="flex items-center gap-3">
            <span className="text-2xl text-prism-green font-bold">✓</span>
            <div>
              <div className="text-xl font-bold text-slate-200">{counts.strong}</div>
              <div className="text-xs text-slate-400">Strong Matches Found</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <div className="text-xl font-bold text-prism-yellow">{insights.contradiction}</div>
              <div className="text-xs text-slate-400">Skill-Career Contradictions</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <div className="text-xl font-bold text-red-400">{insights.ghost}</div>
              <div className="text-xs text-slate-400">Ghost Candidates</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <div className="text-xl font-bold text-red-400">{insights.fakeYoe}</div>
              <div className="text-xs text-slate-400">Experience Inflation Cases</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <div className="text-xl font-bold text-red-400">{insights.multipleJobs}</div>
              <div className="text-xs text-slate-400">Multiple Current Jobs</div>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <TopCandidatesChart rankings={rankings} />
      </Card>

      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Scoring Weight Tuner</h2>
            <p className="mt-1 text-sm text-slate-400">Adjust parameters and re-sort the table live.</p>
          </div>
          <div className="flex gap-2">
            <button 
              onClick={() => setSortBy(sortBy === "prism" ? "tuned" : "prism")}
              className={`rounded-card px-4 py-1.5 text-xs font-semibold uppercase tracking-wider transition ${sortBy === "tuned" ? "bg-prism-cyan text-slate-950" : "bg-slate-800 text-slate-300 hover:bg-slate-700"}`}
            >
              {sortBy === "tuned" ? "Sort: Tuned Active" : "Sort: PRISM Default"}
            </button>
            <button 
              onClick={() => {
                setWeights({ role: 0.55, proof: 0.25, recruit: 0.12, market: 0.08 });
                setSortBy("prism");
              }} 
              className="rounded-card bg-slate-900 border border-prism-line px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-800 transition"
            >
              Reset Weights
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-4 md:grid-cols-4">
          <WeightSlider label="Role Alignment" value={weights.role} onChange={(value) => { setWeights((prev) => ({ ...prev, role: value })); setSortBy("tuned"); }} />
          <WeightSlider label="Skill Proof" value={weights.proof} onChange={(value) => { setWeights((prev) => ({ ...prev, proof: value })); setSortBy("tuned"); }} />
          <WeightSlider label="Hireability" value={weights.recruit} onChange={(value) => { setWeights((prev) => ({ ...prev, recruit: value })); setSortBy("tuned"); }} />
          <WeightSlider label="Market Validation" value={weights.market} onChange={(value) => { setWeights((prev) => ({ ...prev, market: value })); setSortBy("tuned"); }} />
        </div>
      </Card>

      {/* Advanced Filters Panel */}
      <Card className="space-y-4">
        <h2 className="text-base font-semibold text-slate-300">Natural Language Search & Advanced Filters</h2>
        
        <div className="flex flex-col gap-3 md:flex-row">
          <label className="flex flex-1 items-center gap-2 rounded-card border border-prism-line bg-prism-panel px-3">
            <Search size={18} className="text-slate-500" />
            <input className="w-full bg-transparent py-2 outline-none" placeholder="Try: Elasticsearch open to work under 60 days notice" value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          
          <select className="rounded-card border border-prism-line bg-prism-panel px-3 py-2" value={tier} onChange={(e) => setTier(e.target.value)}>
            <option value="All">All Tiers</option>
            {["Strong Match", "Near Match", "Weak Signal", "Honeypot", "Not Qualified"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          
          <select className="rounded-card border border-prism-line bg-prism-panel px-3 py-2" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="All">All Statuses</option>
            {["Unreviewed", "Interview", "Screen", "Reserve", "Rejected"].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 pt-2 border-t border-prism-line">
          <label className="space-y-1 block">
            <span className="text-xs text-slate-400">Location</span>
            <input className="w-full rounded-card border border-prism-line bg-prism-panel px-3 py-1.5 text-sm outline-none text-slate-200" placeholder="e.g. Pune, Noida" value={locationQuery} onChange={(e) => setLocationQuery(e.target.value)} />
          </label>
          
          <label className="space-y-1 block">
            <span className="text-xs text-slate-400">Notice Period</span>
            <select className="w-full rounded-card border border-prism-line bg-prism-panel px-3 py-1.5 text-sm outline-none text-slate-200" value={noticePeriod} onChange={(e) => setNoticePeriod(e.target.value)}>
              <option value="All">Any Notice Period</option>
              <option value="0">Immediate Availability</option>
              <option value="30">&lt;= 30 Days</option>
              <option value="60">&lt;= 60 Days</option>
              <option value="90">&lt;= 90 Days</option>
            </select>
          </label>

          <label className="space-y-1 block">
            <span className="text-xs text-slate-400">Min YOE</span>
            <input className="w-full rounded-card border border-prism-line bg-prism-panel px-3 py-1.5 text-sm outline-none text-slate-200" type="number" min="0" max="30" placeholder="e.g. 2" value={minYoe} onChange={(e) => setMinYoe(e.target.value === "" ? "" : Number(e.target.value))} />
          </label>

          <label className="space-y-1 block">
            <span className="text-xs text-slate-400">Max YOE</span>
            <input className="w-full rounded-card border border-prism-line bg-prism-panel px-3 py-1.5 text-sm outline-none text-slate-200" type="number" min="0" max="30" placeholder="e.g. 10" value={maxYoe} onChange={(e) => setMaxYoe(e.target.value === "" ? "" : Number(e.target.value))} />
          </label>
        </div>
      </Card>

      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-slate-400">
            <tr className="border-b border-prism-line">
              <th className="py-3 px-4">Rank</th>
              <th>Candidate</th>
              <th>Company</th>
              <th>Final Score</th>
              <th>Tier</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((item, index) => {
              return (
                <Fragment key={item.candidate_id}>
                  <tr 
                    onClick={() => toggleRow(item.candidate_id)}
                    className="border-t border-prism-line hover:bg-slate-900/35 transition cursor-pointer select-none"
                  >
                    <td className="py-4 px-4 font-semibold text-slate-400">
                      {sortBy === "prism" ? item.rank : index + 1}
                    </td>
                    <td>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">
                          {expandedRows[item.candidate_id] ? "▼" : "▶"}
                        </span>
                        <div>
                          <Link 
                            className="font-bold text-prism-cyan hover:underline" 
                            href={`/candidate/${item.candidate_id}`}
                            onClick={(e) => e.stopPropagation()}
                          >
                            {item.candidate_name}
                          </Link>
                          <div className="text-xs text-slate-500 font-medium">{item.title || "Software Engineer"}</div>
                        </div>
                      </div>
                    </td>
                    <td>{item.current_company || "Unknown"}</td>
                    <td className="font-mono font-semibold">{item.final_score.toFixed(1)}</td>
                    <td className={tierClass(item.qualification_tier)}>{item.qualification_tier}</td>
                    <td onClick={(e) => e.stopPropagation()}>
                      <select 
                        value={decisions[item.candidate_id] ?? "Unreviewed"} 
                        onChange={(e) => {
                          const val = e.target.value;
                          localStorage.setItem(`prism-decision-${item.candidate_id}`, val);
                          setDecisions((prev) => ({ ...prev, [item.candidate_id]: val }));
                        }}
                        className={`bg-transparent border-b border-transparent hover:border-slate-500 py-1 outline-none text-sm font-semibold ${decisionClass(decisions[item.candidate_id] ?? "Unreviewed")}`}
                      >
                        {["Unreviewed", "Interview", "Screen", "Reserve", "Rejected"].map((opt) => (
                          <option key={opt} value={opt} className="bg-slate-950 text-slate-200">{opt}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                  {expandedRows[item.candidate_id] && (
                    <tr className="bg-slate-950/45 border-t border-prism-line">
                      <td colSpan={6} className="p-5">
                        <div className="grid gap-6 md:grid-cols-5 text-sm">
                          <div className="rounded-card border border-prism-line bg-slate-900/40 p-4">
                            <div className="text-xs uppercase font-semibold text-slate-500">Role Alignment</div>
                            <div className="mt-2 text-xl font-bold text-slate-200">{item.role_alignment_score.toFixed(1)}</div>
                            <div className="mt-1 text-xs text-slate-400">Semantic & context match to JD</div>
                          </div>
                          <div className="rounded-card border border-prism-line bg-slate-900/40 p-4">
                            <div className="text-xs uppercase font-semibold text-slate-500">Skill Proof</div>
                            <div className="mt-2 text-xl font-bold text-slate-200">{item.skill_proof_score.toFixed(1)}</div>
                            <div className="mt-1 text-xs text-slate-400">Evidence of claimed skills in text</div>
                          </div>
                          <div className="rounded-card border border-prism-line bg-slate-900/40 p-4">
                            <div className="text-xs uppercase font-semibold text-slate-500">Hireability</div>
                            <div className="mt-2 text-xl font-bold text-slate-200">{(item.hireability_score ?? item.recruitability_score).toFixed(1)}</div>
                            <div className="mt-1 text-xs text-slate-400">Notice, activity & responsiveness</div>
                          </div>
                          <div className="rounded-card border border-prism-line bg-slate-900/40 p-4">
                            <div className="text-xs uppercase font-semibold text-slate-500">Market Validation</div>
                            <div className="mt-2 text-xl font-bold text-slate-200">{item.market_validation_score.toFixed(1)}</div>
                            <div className="mt-1 text-xs text-slate-400">Recruiter interest & demand</div>
                          </div>
                          <div className="rounded-card border border-prism-line bg-slate-900/40 p-4 border-prism-cyan/30 bg-prism-cyan/[0.03]">
                            <div className="text-xs uppercase font-semibold text-prism-cyan">Tuned Score</div>
                            <div className="mt-2 text-xl font-bold text-prism-cyan">{item.tuned_score.toFixed(1)}</div>
                            <div className="mt-1 text-xs text-prism-cyan/80">Weighted client-side score</div>
                          </div>
                        </div>

                        <div className="mt-4 rounded-card border border-prism-line bg-slate-900/25 p-4 space-y-4">
                          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">PRISM Scorer Detailed Diagnostics</div>
                          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-5 text-sm">
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Raw Semantic Score</div>
                              <div className="mt-1 font-bold text-slate-200 font-mono">{item.raw_semantic_score !== undefined ? item.raw_semantic_score.toFixed(1) : "N/A"}</div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Career Evidence Score</div>
                              <div className="mt-1 font-bold text-slate-200 font-mono">{item.career_evidence_score !== undefined ? item.career_evidence_score.toFixed(1) : "N/A"}</div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Self-Claim Score</div>
                              <div className="mt-1 font-bold text-slate-200 font-mono">{item.self_claim_score !== undefined ? item.self_claim_score.toFixed(1) : "N/A"}</div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Domain Relevance</div>
                              <div className="mt-1 font-bold text-slate-200 font-mono">{item.domain_relevance !== undefined ? item.domain_relevance.toFixed(2) : "N/A"}</div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Domain Gate Penalty</div>
                              <div className="mt-1 font-bold text-slate-200 font-mono">
                                {item.domain_gate_applied 
                                  ? `${Math.round((1 - (item.domain_gate_penalty ?? 0.5)) * 100)}%` 
                                  : "None (1.0x)"}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Confidence Status</div>
                              <div className="mt-1 font-bold font-mono">
                                {item.degraded_confidence 
                                  ? <span className="text-amber-400">Degraded (Lexical)</span> 
                                  : <span className="text-emerald-400">High (Embeddings)</span>}
                              </div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Contradiction Severity</div>
                              <div className="mt-1 font-bold text-slate-200 font-mono">Level {item.contradiction_severity ?? 0}</div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Contradiction Penalty</div>
                              <div className="mt-1 font-bold text-red-400 font-mono">-{item.contradiction_penalty !== undefined ? item.contradiction_penalty.toFixed(1) : "0.0"} pts</div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium">Fraud Penalty</div>
                              <div className="mt-1 font-bold text-red-500 font-mono">-{item.fraud_penalty !== undefined ? item.fraud_penalty.toFixed(1) : "0.0"} pts</div>
                            </div>
                            <div>
                              <div className="text-xs text-slate-500 font-medium font-semibold font-bold">Final Score</div>
                              <div className="mt-1 font-bold text-prism-cyan font-mono">{item.final_score.toFixed(1)}</div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function WeightSlider({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="text-sm text-slate-300">
      <div className="flex justify-between"><span>{label}</span><span>{value.toFixed(2)}</span></div>
      <input className="mt-2 w-full" type="range" min="0" max="1" step="0.01" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function tunedScore(item: Ranking, weights: { role: number; proof: number; recruit: number; market: number }) {
  const total = Math.max(0.01, weights.role + weights.proof + weights.recruit + weights.market);
  return (
    item.role_alignment_score * weights.role +
    item.skill_proof_score * weights.proof +
    (item.hireability_score ?? item.recruitability_score) * weights.recruit +
    item.market_validation_score * weights.market
  ) / total;
}

function tierValue(tier: string) {
  if (tier === "Strong Match") return 4;
  if (tier === "Near Match") return 3;
  if (tier === "Weak Signal") return 2;
  if (tier === "Not Qualified") return 1;
  return 0; // Honeypot / Flagged
}

function parseNaturalQuery(query: string) {
  const text = query.toLowerCase();
  const notice = text.match(/(?:under|below|less than)\s+(\d+)\s+days?/);
  const skillTerms = ["elasticsearch", "faiss", "pinecone", "qdrant", "weaviate", "python", "kafka", "spark", "airflow", "retrieval", "recommendation", "embeddings", "bm25", "rag"];
  return {
    raw: text.trim(),
    skills: skillTerms.filter((term) => text.includes(term)),
    openToWork: text.includes("open to work"),
    maxNotice: notice ? Number(notice[1]) : null
  };
}

function matchesQuery(item: Ranking, parsed: { raw: string; skills: string[]; openToWork: boolean; maxNotice: number | null }) {
  if (!parsed.raw) return true;
  const haystack = `${item.candidate_name} ${item.title} ${item.current_company} ${item.current_industry} ${item.location} ${item.skills?.join(" ")} ${item.ranking_explanation}`.toLowerCase();
  if (parsed.skills.length && !parsed.skills.some((skill) => haystack.includes(skill) || item.flags?.some((flag) => flag.claimed_skills.join(" ").toLowerCase().includes(skill)))) return false;
  if (parsed.openToWork && !item.open_to_work) return false;
  if (parsed.maxNotice !== null && (item.notice_period_days === null || item.notice_period_days > parsed.maxNotice)) return false;
  if (!parsed.skills.length && !parsed.openToWork && parsed.maxNotice === null) return haystack.includes(parsed.raw);
  return true;
}
