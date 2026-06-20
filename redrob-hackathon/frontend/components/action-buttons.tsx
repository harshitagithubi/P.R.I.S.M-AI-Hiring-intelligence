"use client";

const ACTIONS = ["Interview", "Screen", "Reserve", "Rejected"] as const;

export function ActionButtons({ candidateId, value, onChange }: { candidateId: string; value: string; onChange: (value: string) => void }) {
  function choose(action: string) {
    localStorage.setItem(`prism-decision-${candidateId}`, action);
    onChange(action);
  }

  return (
    <div className="flex flex-wrap gap-2">
      {ACTIONS.map((action) => (
        <button
          key={action}
          onClick={() => choose(action)}
          className={`rounded-card border px-3 py-2 text-sm ${value === action ? "border-prism-cyan bg-prism-cyan text-slate-950" : "border-prism-line text-slate-300 hover:bg-slate-800"}`}
        >
          {action}
        </button>
      ))}
    </div>
  );
}
