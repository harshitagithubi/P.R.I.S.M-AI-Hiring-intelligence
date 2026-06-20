import type { Risk } from "@/lib/api";
import { riskClass } from "@/lib/utils";

export function RiskPanel({ risks }: { risks: Risk[] }) {
  return (
    <div className="space-y-2">
      {risks.map((risk, index) => (
        <div key={`${risk.type}-${index}`} className={`rounded-card border px-3 py-2 text-sm ${riskClass(risk.severity)}`}>
          <span className="font-medium capitalize">{risk.type}</span>
          <span className="text-slate-300"> · {risk.detail}</span>
        </div>
      ))}
    </div>
  );
}
