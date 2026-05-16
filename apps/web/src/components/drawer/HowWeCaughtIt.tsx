"use client";

import type { AgentTag, CardEvidence, HowWeCaughtItEntry } from "@/lib/types";
import { SandboxReplay } from "./SandboxReplay";

interface Props {
  entries: HowWeCaughtItEntry[];
  screenshots: string[];
  evidence: CardEvidence;
}

export function HowWeCaughtIt({ entries, screenshots, evidence }: Props) {
  return (
    <section aria-labelledby="hwc-heading">
      <h3
        id="hwc-heading"
        className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400"
      >
        How we caught it
      </h3>

      <ul className="mt-4 space-y-3">
        {entries.map((entry, i) => (
          <li
            key={`${entry.agent}-${i}`}
            className="flex items-start gap-3 text-slate-200"
          >
            <AgentTagBadge agent={entry.agent} />
            <p className="leading-relaxed">{entry.finding}</p>
          </li>
        ))}
      </ul>

      {screenshots.length > 0 ? (
        <div className="mt-6">
          <SandboxReplay
            screenshots={screenshots}
            finalUrl={evidence.final_url ?? null}
          />
        </div>
      ) : null}
    </section>
  );
}

function AgentTagBadge({ agent }: { agent: AgentTag }) {
  const palette: Record<AgentTag, string> = {
    triage: "border-sky-700/60 bg-sky-950/60 text-sky-200",
    "domain-intel": "border-violet-700/60 bg-violet-950/60 text-violet-200",
    "sandbox-walker": "border-emerald-700/60 bg-emerald-950/60 text-emerald-200",
  };
  return (
    <span
      className={[
        "mt-0.5 inline-flex shrink-0 items-center rounded-md border px-2 py-0.5",
        "text-[10px] font-medium uppercase tracking-wider",
        palette[agent],
      ].join(" ")}
    >
      {agent}
    </span>
  );
}
