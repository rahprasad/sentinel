"use client";

import { describeField } from "@/lib/harvested";

interface Props {
  what_they_wanted: string;
  harvested: string[];
}

export function WhatTheyWanted({ what_they_wanted, harvested }: Props) {
  return (
    <section aria-labelledby="wtw-heading">
      <h3
        id="wtw-heading"
        className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400"
      >
        What they wanted
      </h3>
      <p className="mt-3 text-2xl font-semibold leading-snug text-slate-50">
        {what_they_wanted}
      </p>

      {harvested.length > 0 ? (
        <ul className="mt-5 flex flex-wrap gap-2">
          {harvested.map((field) => {
            const presentation = describeField(field);
            return (
              <li
                key={field}
                className={[
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm",
                  presentation.severity === "high"
                    ? "border-rose-700/60 bg-rose-950/40 text-rose-200"
                    : presentation.severity === "medium"
                    ? "border-amber-700/60 bg-amber-950/30 text-amber-200"
                    : "border-slate-700 bg-slate-900/60 text-slate-200",
                ].join(" ")}
              >
                <span aria-hidden>{presentation.icon}</span>
                {presentation.label}
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
