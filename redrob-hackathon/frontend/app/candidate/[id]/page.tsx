"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getCandidate, getExplanation } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { ScoreRadar } from "@/components/score-radar";
import { CareerTimeline } from "@/components/career-timeline";
import { EvidenceHighlight } from "@/components/evidence-highlight";
import { RiskPanel } from "@/components/risk-panel";
import { ScoreBreakdown } from "@/components/score-breakdown";
import { ActionButtons } from "@/components/action-buttons";
import { decisionClass, tierClass } from "@/lib/utils";

export default function CandidateDetailPage() {
  const params = useParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [explanation, setExplanation] = useState<any>(null);
  const [decision, setDecision] = useState("Unreviewed");

  useEffect(() => {
    getCandidate(params.id).then(setData).catch(console.error);
    getExplanation(params.id).then(setExplanation).catch(console.error);
    setDecision(localStorage.getItem(`prism-decision-${params.id}`) ?? "Unreviewed");
  }, [params.id]);

  if (!data || !explanation) return <div>Loading candidate...</div>;
  const profile = data.profile;
  const ranking = data.ranking;
  const components = data.components;
  const signals = profile.recruiter_signals;

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <h1 className="text-3xl font-semibold">{profile.anonymized_name}</h1>
          <p className="text-slate-400">{profile.title} at {profile.current_company} · {profile.location}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-sm">
            <span className={tierClass(ranking.qualification_tier)}>{ranking.qualification_tier}</span>
            <span className={decisionClass(decision)}>{decision}</span>
          </div>
        </div>
        <ActionButtons candidateId={profile.candidate_id} value={decision} onChange={setDecision} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card>
          <h2 className="text-lg font-semibold">Profile Summary</h2>
          <p className="mt-3 text-slate-300"><EvidenceHighlight text={profile.summary} /></p>
          <h2 className="mt-6 text-lg font-semibold">Skills</h2>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {profile.skills.map((skill: any) => (
              <div key={skill.name} className="rounded-card border border-prism-line bg-slate-950/40 p-3 text-sm">
                <div className="font-medium"><EvidenceHighlight text={skill.name} /></div>
                <div className="text-xs text-slate-500">{skill.proficiency} · {skill.endorsements} endorsements</div>
              </div>
            ))}
          </div>
        </Card>
        <Card><ScoreRadar ranking={ranking} /></Card>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border border-prism-line bg-prism-panel/30">
          <h2 className="text-lg font-semibold">PRISM Match Decision</h2>
          <p className="mt-4 text-slate-300 whitespace-pre-line leading-relaxed"><EvidenceHighlight text={explanation.decision_reason} /></p>
        </Card>
        
        <Card className="border border-prism-line bg-prism-panel/30">
          <h2 className="text-lg font-semibold">Why Ranked Here</h2>
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <h3 className="text-xs uppercase font-semibold tracking-wider text-prism-green">Evidence & Strengths</h3>
              <ul className="space-y-1.5 text-sm text-slate-300">
                {explanation.strengths.map((str: string, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-prism-green font-bold select-none">+</span>
                    <span><EvidenceHighlight text={str} /></span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-2 pt-3 border-t border-prism-line/40">
              <h3 className="text-xs uppercase font-semibold tracking-wider text-prism-red">Risks & Missing Requirements</h3>
              <ul className="space-y-1.5 text-sm text-slate-300">
                {explanation.risks.filter((risk: string) => !risk.includes("No major PRISM reliability risk")).map((risk: string, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-prism-red font-bold select-none">-</span>
                    <span><EvidenceHighlight text={risk} /></span>
                  </li>
                ))}
                {explanation.missing_requirements.slice(0, 3).map((req: string, index: number) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-prism-red font-bold select-none">-</span>
                    <span>Missing {req}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Card>
          <h2 className="text-lg font-semibold">Career Timeline</h2>
          <CareerTimeline jobs={profile.career_history} />
        </Card>
        <Card>
          <h2 className="text-lg font-semibold">Behavioral Signals</h2>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Metric label="Open to Work" value={signals.open_to_work_flag ? "Yes" : "No"} />
            <Metric label="Notice" value={`${signals.notice_period_days ?? "?"} days`} />
            <Metric label="Response" value={`${Math.round((signals.recruiter_response_rate ?? 0) * 100)}%`} />
            <Metric label="Last Active" value={signals.last_active_date ?? "Unknown"} />
            <Metric label="Recruiter Saves" value={String(signals.saved_by_recruiters_30d)} />
            <Metric label="GitHub" value={String(profile.github_signals.github_activity_score ?? 0)} />
          </div>
        </Card>
      </div>
      <Card>
        <h2 className="text-lg font-semibold">Risk Panel</h2>
        <div className="mt-3"><RiskPanel risks={ranking.risks} /></div>
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">Score Breakdown</h2>
        <div className="mt-3"><ScoreBreakdown reasons={components.score_reasons} /></div>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <ListCard title="Strengths" items={explanation.strengths} />
        <ListCard title="Missing Requirements" items={explanation.missing_requirements} />
        <ListCard title="Risks" items={explanation.risks} />
        <ListCard title="Evidence Found" items={explanation.evidence_found} />
      </div>
      <Card>
        <h2 className="text-lg font-semibold">Career History</h2>
        {profile.career_history.map((job: any, index: number) => (
          <div key={index} className="mt-4 border-t border-prism-line pt-4">
            <div className="font-medium">{job.title} at {job.company}</div>
            <p className="mt-1 text-sm text-slate-400"><EvidenceHighlight text={job.description} /></p>
          </div>
        ))}
      </Card>
    </div>
  );
}

function ListCard({ title, items }: { title: string; items: string[] }) {
  return (
    <Card>
      <h2 className="text-lg font-semibold">{title}</h2>
      <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-300">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-card border border-prism-line bg-slate-950/40 p-3">
      <div className="text-base font-semibold">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  );
}
