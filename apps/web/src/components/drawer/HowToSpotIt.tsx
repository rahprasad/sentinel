"use client";

interface Props {
  rules: string[];
}

export function HowToSpotIt({ rules }: Props) {
  if (rules.length === 0) return null;

  return (
    <section aria-labelledby="hts-heading">
      <h3
        id="hts-heading"
        className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400"
      >
        How to spot it next time
      </h3>
      <div className="mt-3 rounded-xl border border-emerald-800/60 bg-emerald-950/30 px-5 py-4">
        <ul className="space-y-2.5">
          {rules.map((rule, i) => (
            <li key={i} className="flex gap-3 text-slate-100">
              <span
                aria-hidden
                className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400"
              />
              <span className="leading-relaxed">{rule}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
