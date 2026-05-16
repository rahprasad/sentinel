"use client";

const TRENDING = [
  { label: "Fake USPS texts", change: "+300%" },
  { label: "Pig butchering DMs", change: "+120%" },
  { label: "Fake Coinbase login", change: "+85%" },
];

export default function TrendingStrip() {
  return (
    <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5">
      <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-3">
        Trending This Week
      </h2>
      <div className="space-y-2">
        {TRENDING.map((item) => (
          <div
            key={item.label}
            className="flex items-center justify-between"
          >
            <span className="text-sm">{item.label}</span>
            <span className="text-sm font-mono text-[var(--danger)]">
              {item.change}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
