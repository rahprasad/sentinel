"use client";

import type { ReactNode } from "react";
import type { IncidentSource, Tell, WhatTheySent as WhatTheySentData } from "@/lib/types";

interface Props {
  data: WhatTheySentData;
  source: IncidentSource;
}

export function WhatTheySent({ data, source }: Props) {
  return (
    <section aria-labelledby="wts-heading">
      <SectionHeading id="wts-heading">
        What they sent you
        <SourceBadge source={source} />
      </SectionHeading>
      <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60 px-5 py-4">
        <p className="whitespace-pre-wrap text-slate-200 leading-relaxed">
          {renderWithTells(data.raw, data.tells)}
        </p>
      </div>
    </section>
  );
}

function SectionHeading({ id, children }: { id: string; children: ReactNode }) {
  return (
    <h3
      id={id}
      className="flex items-center justify-between gap-3 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400"
    >
      {children}
    </h3>
  );
}

function SourceBadge({ source }: { source: IncidentSource }) {
  const label =
    source === "email_imap" || source === "email_webhook"
      ? "email"
      : source === "screenshot"
      ? "screenshot"
      : "message";
  return (
    <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] tracking-wider text-slate-300">
      {label}
    </span>
  );
}

/**
 * Walk through `raw`, splitting on each tell.span occurrence so we can wrap
 * those spans in <mark>. Overlapping tells skip past the cursor. We never
 * dangerouslySetInnerHTML — every output is plain text or a real element.
 */
function renderWithTells(raw: string, tells: Tell[]): ReactNode {
  if (!tells.length) return raw;

  const positions = tells
    .map((tell) => ({ tell, start: raw.indexOf(tell.span) }))
    .filter((p) => p.start >= 0 && p.tell.span.length > 0)
    .sort((a, b) => a.start - b.start);

  const out: ReactNode[] = [];
  let cursor = 0;
  positions.forEach((p, i) => {
    if (p.start < cursor) return; // skip overlapping tells
    if (p.start > cursor) {
      out.push(<span key={`t${i}`}>{raw.slice(cursor, p.start)}</span>);
    }
    out.push(
      <mark
        key={`m${i}`}
        title={p.tell.why}
        className={[
          "rounded-sm bg-amber-500/10 px-0.5 text-amber-200",
          "decoration-amber-400/70 underline decoration-wavy underline-offset-4",
          "cursor-help",
        ].join(" ")}
      >
        {p.tell.span}
      </mark>,
    );
    cursor = p.start + p.tell.span.length;
  });
  if (cursor < raw.length) out.push(<span key="tail">{raw.slice(cursor)}</span>);
  return out;
}
