import type { ScoreReasons } from "@/lib/api";

const labels: Record<string, string> = {
  role: "Role Alignment",
  proof: "Skill Proof",
  recruitability: "Hireability",
  market: "Market Validation"
};

export function ScoreBreakdown({ reasons }: { reasons: ScoreReasons }) {
  return (
    <div className="space-y-3">
      {Object.entries(reasons).map(([key, value]) => (
        <details key={key} className="rounded-card border border-prism-line bg-slate-950/40 p-3">
          <summary className="cursor-pointer text-sm font-medium">
            {labels[key]} · {value.score.toFixed(1)}
          </summary>
          <p className="mt-2 text-sm text-slate-400">{value.summary}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
            {value.reasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        </details>
      ))}
    </div>
  );
}
