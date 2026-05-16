"use client";

import { usePolling } from "@/hooks/use-polling";
import { fetchStats } from "@/lib/api";

const POLL_MS = 5000;

function formatCurrency(amount: number): string {
  if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}k`;
  return `$${amount}`;
}

export default function HeroStats() {
  const { data } = usePolling(() => fetchStats(), POLL_MS);

  const blocked = data?.blocked_count ?? 0;
  const savings = data?.estimated_savings_usd ?? 0;
  const scanned = data?.scanned_today ?? 0;

  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5 text-center">
        <p className="text-3xl font-bold text-[var(--accent)]">{blocked}</p>
        <p className="text-sm text-[var(--muted)] mt-1">Scams Blocked</p>
      </div>
      <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5 text-center">
        <p className="text-3xl font-bold text-[var(--success)]">
          {formatCurrency(savings)}
        </p>
        <p className="text-sm text-[var(--muted)] mt-1">Estimated Savings</p>
      </div>
      <div className="rounded-xl border border-[var(--card-border)] bg-[var(--card)] p-5 text-center">
        <p className="text-3xl font-bold text-[var(--foreground)]">
          {scanned}
        </p>
        <p className="text-sm text-[var(--muted)] mt-1">Messages Scanned</p>
      </div>
    </div>
  );
}
