import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";

export const metadata: Metadata = {
  title: "P.R.I.S.M AI",
  description: "Profile Reliability & Intelligent Skill Mapping"
};

const nav = [
  ["Home", "/"],
  ["Rankings", "/rankings"],
  ["Compare", "/compare"],
  ["Audit", "/audit"]
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <div className="min-h-screen bg-prism-bg">
          <aside className="fixed inset-y-0 left-0 hidden w-56 border-r border-prism-line bg-prism-panel p-6 md:block">
            <div className="text-2xl font-semibold tracking-wide">P.R.I.S.M AI</div>
            <p className="mt-2 text-sm text-slate-400">Profile Reliability & Intelligent Skill Mapping</p>
            <nav className="mt-8 space-y-2">
              {nav.map(([label, href]) => (
                <Link key={href} href={href} className="block rounded-card px-3 py-2 text-sm text-slate-300 hover:bg-slate-800">
                  {label}
                </Link>
              ))}
            </nav>
          </aside>
          <main className="px-4 py-6 md:ml-56 md:px-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
