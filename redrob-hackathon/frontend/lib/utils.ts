import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function tierClass(tier: string) {
  if (tier === "Strong Match") return "text-prism-green font-medium";
  if (tier === "Near Match") return "text-prism-yellow font-medium";
  if (tier === "Weak Signal") return "text-prism-cyan font-medium";
  if (tier === "Honeypot" || tier === "Flagged") return "text-red-500 font-bold tracking-wider";
  return "text-slate-500";
}

export function riskClass(severity: string) {
  if (severity === "green") return "border-prism-green/40 bg-prism-green/10 text-prism-green";
  if (severity === "amber") return "border-prism-yellow/40 bg-prism-yellow/10 text-prism-yellow";
  return "border-prism-red/40 bg-prism-red/10 text-prism-red";
}

export function decisionClass(decision: string) {
  if (decision === "Interview") return "text-prism-green";
  if (decision === "Screen") return "text-prism-cyan";
  if (decision === "Reserve") return "text-prism-yellow";
  if (decision === "Rejected") return "text-prism-red";
  return "text-slate-400";
}
